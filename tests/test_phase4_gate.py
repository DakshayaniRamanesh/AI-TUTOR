import pytest
import uuid
import json
from datetime import datetime

from shared.contracts.common import CanvasBBox
from shared.contracts.context import (
    ContextRequest, ContextBundle, ContextScope, SemanticBlock, SemanticBlockType,
    CanvasContext, RetrievedEvidence, GraphContext, GraphConceptDTO, LearnerObservationDTO
)
from shared.contracts.tutoring import (
    TutorMode, TutorResponse, TutorFeedback, FeedbackSeverity, CitationChip
)
from shared.contracts.reasoning import ValidationVerdict, CanvasAnchor
from app.services.reasoning.math_parser import parse_math
from app.services.reasoning.math_validator import validate_transition
from app.services.reasoning.context_builder import ContextBuilder
from app.services.tutoring.orchestrator import TutorOrchestrator
from app.services.memory.repositories import MemoryRepository
from app.services.recognition.semantic_canvas_builder import SemanticCanvasBuilder
from app.services.tutoring.voice_service import clean_text_for_speech, VoiceNarrationService
from backend.workspace.subject_search_service import SubjectSearchService
from app.storage.database import get_engine, Base, User, Subject, Notebook, Material, SubjectChunk, ConceptNode, ConceptEdge
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def phase4_db():
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    yield Session
    Base.metadata.drop_all(bind=engine)

# ===========================================================================
# 21.1 Contracts
# ===========================================================================

def test_context_contracts_roundtrip():
    bbox = CanvasBBox(x=10.0, y=20.0, width=100.0, height=50.0)
    block = SemanticBlock(
        block_id="b1",
        block_type=SemanticBlockType.MATH,
        stroke_ids=["s1", "s2"],
        item_ids=["it1"],
        bbox=bbox,
        recognized_text="2x + 6 = 10",
        confidence=0.95
    )
    req = ContextRequest(
        request_id="req-123",
        subject_id="subj-1",
        notebook_id="nb-1",
        session_id="sess-1",
        attempt_id="att-1",
        canvas_revision=1,
        scope=ContextScope.SELECTION,
        canvas_context=CanvasContext(
            board_id="board-1",
            semantic_blocks=[block],
            active_block_id="b1"
        ),
        user_query="2x + 6 = 10",
        tutor_mode="CHECK_STEP"
    )

    data = req.model_dump()
    req_restored = ContextRequest.model_validate(data)
    assert req_restored.request_id == "req-123"
    assert req_restored.canvas_context.semantic_blocks[0].recognized_text == "2x + 6 = 10"

    chip = CitationChip(
        chunk_id="chk-1",
        material_id="mat-1",
        document_title="Tutorial 1",
        chapter="Chapter 2",
        section="2.1",
        page_number=3,
        snippet="Solve linear equations by distribution."
    )
    resp = TutorResponse(
        request_id="req-123",
        tutor_mode=TutorMode.CHECK_STEP,
        verdict=ValidationVerdict.VALID,
        feedback_text="Correct! 2x + 6 = 10 is a valid step.",
        socratic_hints=["What is the next step to isolate x?"],
        severity=FeedbackSeverity.INFO,
        citations=[chip],
        spoken_text="Correct! 2x plus 6 equals 10 is a valid step.",
        source_mode="OFFLINE_LOCAL"
    )
    resp_data = resp.model_dump()
    resp_restored = TutorResponse.model_validate(resp_data)
    assert resp_restored.verdict == ValidationVerdict.VALID
    assert resp_restored.citations[0].document_title == "Tutorial 1"

# ===========================================================================
# 21.2 Semantic Block Building & Classification
# ===========================================================================

def test_semantic_block_classification():
    assert SemanticCanvasBuilder.classify_block_type("2x + 6 = 10") == SemanticBlockType.MATH
    assert SemanticCanvasBuilder.classify_block_type("2(x + 3) = 10") == SemanticBlockType.MATH
    assert SemanticCanvasBuilder.classify_block_type("Explain the distributive property for linear equations") == SemanticBlockType.TEXT
    assert SemanticCanvasBuilder.classify_block_type("") == SemanticBlockType.UNKNOWN

# ===========================================================================
# 21.4 Mathematical Reasoning & Operation Inference
# ===========================================================================

def test_reasoning_step_validations():
    # 1. 2x = 4 -> x = 2: VALID
    p1 = parse_math("2x = 4")
    c1 = parse_math("x = 2")
    res1 = validate_transition(p1, c1)
    assert res1.verdict == ValidationVerdict.VALID

    # 2. 2x = 4 -> x = 3: INVALID
    c2 = parse_math("x = 3")
    res2 = validate_transition(p1, c2)
    assert res2.verdict == ValidationVerdict.INVALID

    # 3. Distribution error: 2(x + 3) = 10 -> 2x + 3 = 10: INVALID with concise hint
    p_dist = parse_math("2(x + 3) = 10")
    c_err = parse_math("2x + 3 = 10")
    res_dist = validate_transition(p_dist, c_err)
    assert res_dist.verdict == ValidationVerdict.INVALID
    assert "distribute" in res_dist.explanation.lower()
    assert "2 × 3" in res_dist.explanation or "2 * 3" in res_dist.explanation

    # 4. Correct distribution: 2(x + 3) = 10 -> 2x + 6 = 10: VALID
    c_ok = parse_math("2x + 6 = 10")
    res_ok = validate_transition(p_dist, c_ok)
    assert res_ok.verdict == ValidationVerdict.VALID

    # 5. Multivariable unsupported -> UNKNOWN
    p_multi = parse_math("x + y = 5")
    c_multi = parse_math("x = 5 - y")
    res_multi = validate_transition(p_multi, c_multi)
    assert res_multi.verdict == ValidationVerdict.UNKNOWN

# ===========================================================================
# 21.3 ContextBuilder & Exact Material Retrieval
# ===========================================================================

def test_context_builder_exact_title_and_subject_isolation(phase4_db):
    session = phase4_db()
    user = User(id="u1", username="student1")
    s1 = Subject(id="s1", user_id="u1", name="Algebra Essentials")
    s2 = Subject(id="s2", user_id="u1", name="Physics 101")
    nb1 = Notebook(id="nb-alg", subject_id="s1")
    session.add_all([user, s1, s2, nb1])

    mat1 = Material(id="m1", subject_id="s1", filename="Tutorial_1.pdf", file_path="Tutorial_1.pdf")
    mat2 = Material(id="m2", subject_id="s2", filename="Physics_Notes.pdf", file_path="Physics_Notes.pdf")
    session.add_all([mat1, mat2])

    chunk1 = SubjectChunk(
        id="chk1", subject_id="s1", material_id="m1", chunk_index=0,
        text="When solving linear equations, distribute factors across brackets first.",
        document_title="Tutorial 1", page_number=3
    )
    chunk2 = SubjectChunk(
        id="chk2", subject_id="s2", material_id="m2", chunk_index=0,
        text="Newton's laws of motion govern kinematics.",
        document_title="Physics Notes", page_number=1
    )
    session.add_all([chunk1, chunk2])
    session.commit()

    repo = MemoryRepository(session_factory=phase4_db)
    search_service = SubjectSearchService()
    builder = ContextBuilder(repository=repo, search_service=search_service)

    # Query asking about Tutorial 1 in subject s1
    req = ContextRequest(
        request_id="req-tut",
        subject_id="s1",
        notebook_id="nb-alg",
        attempt_id="att-1",
        user_query="Explain this using Tutorial 1",
        tutor_mode="EXPLAIN"
    )
    bundle = builder.build_context(req)

    # Must find Tutorial 1 from s1
    assert len(bundle.retrieved_evidence) > 0
    assert bundle.retrieved_evidence[0].document_title == "Tutorial 1"
    assert bundle.retrieved_evidence[0].page_number == 3
    # Must NOT leak chunks from s2
    for ev in bundle.retrieved_evidence:
        assert "Newton" not in ev.snippet

# ===========================================================================
# 21.5 Session Lifecycle & Scoped Memory
# ===========================================================================

def test_session_lifecycle_and_attempt_isolation(phase4_db):
    session = phase4_db()
    user = User(id="u1", username="student1")
    subj = Subject(id="s1", user_id="u1", name="Algebra Essentials")
    nb1 = Notebook(id="nb1", subject_id="s1")
    nb2 = Notebook(id="nb2", subject_id="s1")
    session.add_all([user, subj, nb1, nb2])
    session.commit()

    repo = MemoryRepository(session_factory=phase4_db)

    # Opening notebook nb1 creates session
    sess1 = repo.get_or_create_active_session(notebook_id="nb1", user_id="u1", subject_id="s1")
    att1 = repo.get_or_create_active_attempt(sess1)

    # Reopening nb1 resumes same session and attempt without duplication
    sess1_again = repo.get_or_create_active_session(notebook_id="nb1", user_id="u1", subject_id="s1")
    att1_again = repo.get_or_create_active_attempt(sess1)
    assert sess1 == sess1_again
    assert att1 == att1_again

    # Opening different notebook nb2 creates separate session and attempt
    sess2 = repo.get_or_create_active_session(notebook_id="nb2", user_id="u1", subject_id="s1")
    att2 = repo.get_or_create_active_attempt(sess2)
    assert sess2 != sess1
    assert att2 != att1

    # Steps in att1 are isolated from att2
    repo.append_reasoning_step(attempt_id=att1, recognized_text="2x = 4")
    steps1 = repo.get_recent_steps(att1)
    steps2 = repo.get_recent_steps(att2)
    assert len(steps1) == 1
    assert len(steps2) == 0

# ===========================================================================
# 21.9 Voice Narration Speech Conversion
# ===========================================================================

def test_voice_text_cleaning_and_speech_translation():
    raw_math = "Correct! 2(x + 3) = 10 distributes to 2x + 6 = 10 [1]."
    cleaned = clean_text_for_speech(raw_math)

    # Must convert LaTeX / symbols to conversational English
    assert "equals 10" in cleaned
    assert "plus" in cleaned
    # Must strip bracket citations like [1]
    assert "[1]" not in cleaned

# ===========================================================================
# 21.11 End-to-End Tutor Orchestration Pipeline
# ===========================================================================

def test_tutor_orchestrator_e2e_pipeline(phase4_db):
    session = phase4_db()
    user = User(id="u1", username="student1")
    subj = Subject(id="s1", user_id="u1", name="Algebra Essentials")
    nb = Notebook(id="nb-demo", subject_id="s1")
    session.add_all([user, subj, nb])

    # Uploaded material fixture
    mat = Material(id="m1", subject_id="s1", filename="Tutorial_1.pdf", file_path="Tutorial_1.pdf")
    session.add(mat)
    chunk = SubjectChunk(
        id="chk1", subject_id="s1", material_id="m1", chunk_index=0,
        text="Rule: The number outside multiplies every term inside the parentheses.",
        document_title="Tutorial 1", page_number=2
    )
    session.add(chunk)
    session.commit()

    repo = MemoryRepository(session_factory=phase4_db)
    search_service = SubjectSearchService()
    builder = ContextBuilder(repository=repo, search_service=search_service)
    orchestrator = TutorOrchestrator(repository=repo, context_builder=builder)

    sess_id = repo.get_or_create_active_session(notebook_id="nb-demo", user_id="u1", subject_id="s1")
    att_id = repo.get_or_create_active_attempt(sess_id)

    # 1. First step: 2(x + 3) = 10
    req1 = ContextRequest(
        request_id="req-1",
        subject_id="s1",
        notebook_id="nb-demo",
        attempt_id=att_id,
        user_query="2(x + 3) = 10",
        tutor_mode="CHECK_STEP"
    )
    resp1 = orchestrator.process_request(req1)
    assert resp1.verdict == ValidationVerdict.VALID

    # 2. Next step with distribution mistake: 2x + 3 = 10
    req2 = ContextRequest(
        request_id="req-2",
        subject_id="s1",
        notebook_id="nb-demo",
        attempt_id=att_id,
        user_query="2x + 3 = 10",
        tutor_mode="CHECK_STEP"
    )
    resp2 = orchestrator.process_request(req2)
    assert resp2.verdict == ValidationVerdict.INVALID
    assert "distribute" in resp2.feedback_text.lower()
    assert resp2.spoken_text is not None

    # Check that a learner observation was registered for repeated/verified error
    obs = repo.get_learner_observations(user_id="u1", subject_id="s1")
    assert len(obs) >= 1
    assert obs[0].observation_type == "DISTRIBUTIVE_PROPERTY_ERROR"

    # 3. Ask AI: Explain this using Tutorial 1
    req3 = ContextRequest(
        request_id="req-3",
        subject_id="s1",
        notebook_id="nb-demo",
        attempt_id=att_id,
        user_query="Explain this using Tutorial 1",
        tutor_mode="EXPLAIN"
    )
    resp3 = orchestrator.process_request(req3)
    assert len(resp3.citations) > 0
    assert resp3.citations[0].document_title == "Tutorial 1"
    assert resp3.citations[0].page_number == 2
    assert "outside multiplies every term" in resp3.feedback_text

    # 4. Corrected step: 2x + 6 = 10
    req4 = ContextRequest(
        request_id="req-4",
        subject_id="s1",
        notebook_id="nb-demo",
        attempt_id=att_id,
        user_query="2x + 6 = 10",
        tutor_mode="CHECK_STEP"
    )
    resp4 = orchestrator.process_request(req4)
    assert resp4.verdict == ValidationVerdict.VALID
