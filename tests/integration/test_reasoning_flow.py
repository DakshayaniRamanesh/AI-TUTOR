import pytest
import uuid
from app.storage.database import Base, engine
from app.services.memory.repositories import MemoryRepository
from app.services.reasoning.math_parser import parse_math
from app.services.reasoning.math_validator import validate_transition
from app.services.reasoning.context_builder import ContextBuilder
from shared.contracts.reasoning import ValidationVerdict
from shared.contracts.context import ContextRequest


def test_integration_flow(db_session_factory):
    repo = MemoryRepository(session_factory=db_session_factory)
    builder = ContextBuilder(repo)

    # 1. Start a session
    session_id = repo.start_learning_session()
    assert session_id is not None

    # 2. Start problem attempt
    attempt_id = repo.start_problem_attempt(session_id, problem_text="Solve 2x = 4")
    assert attempt_id is not None

    # 3. Store first step
    parsed_1 = parse_math("2x = 4")
    step1_id = repo.append_reasoning_step(attempt_id, recognized_text="2x = 4")

    # 4. Student submits next step
    parsed_2 = parse_math("x = 2")
    step2_id = repo.append_reasoning_step(attempt_id, recognized_text="x = 2")

    # 5. Validate transition
    result = validate_transition(parsed_1, parsed_2)
    assert result.verdict == ValidationVerdict.VALID

    # 6. Store validation event
    repo.update_step_validation(step2_id, verdict=result.verdict, explanation=result.explanation)

    # 7. Retrieve context using Phase 4 ContextRequest API
    req = ContextRequest(
        request_id=str(uuid.uuid4()),
        attempt_id=attempt_id,
        user_query="x = 2",
        tutor_mode="CHECK_STEP"
    )
    bundle = builder.build_context(req)

    # Bundle should contain the recent reasoning steps
    assert "2x = 4" in bundle.recent_reasoning_text or "x = 2" in bundle.recent_reasoning_text
