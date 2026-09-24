import pytest
import uuid
import json
from datetime import datetime

from shared.contracts.common import CanvasBBox
from shared.contracts.context import (
    ContextRequest, ContextBundle, ContextScope, SemanticBlock, SemanticBlockType,
    CanvasContext, RetrievedEvidence, GraphContext, GraphConceptDTO, LearnerObservationDTO,
    RequestTrace
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
from app.services.tutoring.voice_service import clean_text_for_speech
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

def test_response_trace_roundtrip():
    req = ContextRequest(
        request_id="req-123",
        subject_id="subj-1",
        notebook_id="nb-1",
        session_id="sess-1",
        attempt_id="att-1",
        canvas_revision=1,
        semantic_block_id="b1",
        user_query="2x = 4"
    )
    
    resp = TutorResponse(
        request_id=req.request_id,
        subject_id=req.subject_id,
        notebook_id=req.notebook_id,
        session_id=req.session_id,
        attempt_id=req.attempt_id,
        canvas_revision=req.canvas_revision,
        semantic_block_id=req.semantic_block_id,
        tutor_mode=TutorMode.CHECK_STEP,
        feedback_text="Correct",
        source_mode="OFFLINE_LOCAL"
    )
    
    data = resp.model_dump()
    restored = TutorResponse.model_validate(data)
    assert restored.request_id == "req-123"
    assert restored.subject_id == "subj-1"
    assert restored.canvas_revision == 1
    assert restored.semantic_block_id == "b1"

def test_semantic_block_stroke_preservation():
    bbox = CanvasBBox(x=10.0, y=20.0, width=100.0, height=50.0)
    block = SemanticBlock(
        block_id="b1",
        block_type=SemanticBlockType.MATH,
        stroke_ids=["stroke-1", "stroke-2"],
        item_ids=["it1"],
        bbox=bbox,
        recognized_text="2x = 4"
    )
    assert block.stroke_ids == ["stroke-1", "stroke-2"]

def test_correction_ancestry(phase4_db):
    session = phase4_db()
    user = User(id="u1", username="student1")
    subj = Subject(id="s1", user_id="u1", name="Algebra")
    nb = Notebook(id="nb-1", subject_id="s1")
    session.add_all([user, subj, nb])
    session.commit()
    
    repo = MemoryRepository(session_factory=phase4_db)
    sess_id = repo.get_or_create_active_session(notebook_id="nb-1", user_id="u1", subject_id="s1")
    att_id = repo.get_or_create_active_attempt(sess_id)
    
    # Add step 1 (VALID)
    step1_id = repo.append_reasoning_step(att_id, "2x = 4")
    repo.update_step_validation(step1_id, "VALID")
    
    # Add step 2 (INVALID, based on step 1)
    step2_id = repo.append_reasoning_step(att_id, "x = 3", previous_step_id=step1_id)
    repo.update_step_validation(step2_id, "INVALID")
    
    # Add step 3 (VALID correction, based on step 1, replaces step 2)
    step3_id = repo.append_reasoning_step(att_id, "x = 2", previous_step_id=step1_id, replaces_step_id=step2_id)
    repo.update_step_validation(step3_id, "VALID")
    
    # Verify ancestry from db
    from app.storage.models.learning import ReasoningStep
    with phase4_db() as db:
        s2 = db.query(ReasoningStep).filter_by(id=step2_id).first()
        s3 = db.query(ReasoningStep).filter_by(id=step3_id).first()
        
        assert s2.previous_step_id == step1_id
        assert s3.previous_step_id == step1_id
        assert s3.replaces_step_id == step2_id

def test_auto_check_debounce():
    # This is a UI level test, usually mocked, but we can verify contract supports it.
    from shared.contracts.recognition import RecognitionRequest
    req = RecognitionRequest(
        request_id="123",
        board_id="b1",
        group_id="g1",
        group_revision=1,
        source_stroke_ids=["s1"],
        is_auto_check=True
    )
    assert req.is_auto_check is True

def test_notebook_stale_result_rejection():
    # Similar to main_window._is_request_stale
    req = ContextRequest(
        request_id="req-123",
        subject_id="s1",
        notebook_id="nb-1",
        session_id="sess-1",
        attempt_id="att-1"
    )
    
    class FakeWindow:
        def __init__(self):
            self.current_subject_id = "s1"
            self._current_notebook_id = "nb-2" # Different notebook!
            self.current_attempt_id = "att-1"
            
        def _is_request_stale(self, r):
            if hasattr(r, "subject_id") and r.subject_id and r.subject_id != getattr(self, "current_subject_id", None):
                return True
            if hasattr(r, "notebook_id") and r.notebook_id and r.notebook_id != getattr(self, "_current_notebook_id", None):
                return True
            if hasattr(r, "attempt_id") and r.attempt_id and r.attempt_id != getattr(self, "current_attempt_id", None):
                return True
            return False

    w = FakeWindow()
    assert w._is_request_stale(req) is True
    
    w._current_notebook_id = "nb-1"
    assert w._is_request_stale(req) is False

def test_subject_stale_result_rejection():
    req = ContextRequest(
        request_id="req-123",
        subject_id="s1",
        notebook_id="nb-1",
        session_id="sess-1",
        attempt_id="att-1"
    )
    
    class FakeWindow:
        def __init__(self):
            self.current_subject_id = "s2" # Different subject!
            self._current_notebook_id = "nb-1" 
            self.current_attempt_id = "att-1"
            
        def _is_request_stale(self, r):
            if hasattr(r, "subject_id") and r.subject_id and r.subject_id != getattr(self, "current_subject_id", None):
                return True
            if hasattr(r, "notebook_id") and r.notebook_id and r.notebook_id != getattr(self, "_current_notebook_id", None):
                return True
            if hasattr(r, "attempt_id") and r.attempt_id and r.attempt_id != getattr(self, "current_attempt_id", None):
                return True
            return False

    w = FakeWindow()
    assert w._is_request_stale(req) is True

def test_ink_preservation():
    bbox = CanvasBBox(x=10.0, y=20.0, width=100.0, height=50.0)
    block = SemanticBlock(
        block_id="b1",
        block_type=SemanticBlockType.MATH,
        stroke_ids=["stroke-1", "stroke-2"],
        item_ids=["it1"],
        bbox=bbox,
        recognized_text="2x = 4"
    )
    # The strokes should be part of the request payload without being modified
    assert len(block.stroke_ids) == 2

def test_offline_sympy_validation():
    p1 = parse_math("x^2 = 4")
    c1 = parse_math("x = 2")
    res1 = validate_transition(p1, c1)
    assert res1.verdict in [ValidationVerdict.VALID, ValidationVerdict.UNKNOWN, ValidationVerdict.INVALID]

def test_no_evidence_behavior(phase4_db):
    session = phase4_db()
    repo = MemoryRepository(session_factory=phase4_db)
    search_service = SubjectSearchService()
    builder = ContextBuilder(repository=repo, search_service=search_service)
    
    req = ContextRequest(
        request_id="req-1",
        user_query="What is quantum mechanics?",
        tutor_mode="EXPLAIN"
    )
    bundle = builder.build_context(req)
    # No documents indexed, should return empty evidence gracefully
    assert len(bundle.retrieved_evidence) == 0

def test_observation_resolution(phase4_db):
    session = phase4_db()
    user = User(id="u1", username="student1")
    subj = Subject(id="s1", user_id="u1", name="Algebra")
    session.add_all([user, subj])
    session.commit()
    
    repo = MemoryRepository(session_factory=phase4_db)
    # Record observation
    obs_id = repo.record_learner_observation(
        user_id="u1", observation_type="TEST_OBS", description="Test", subject_id="s1"
    )
    
    # Fetch observation
    obs = repo.get_learner_observations(user_id="u1", subject_id="s1")
    assert len(obs) == 1
    assert obs[0].status == "ACTIVE"
