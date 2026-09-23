import pytest
from app.storage.database import Base, engine
from app.services.memory.repositories import MemoryRepository
from app.services.reasoning.math_parser import parse_math
from app.services.reasoning.math_validator import validate_transition
from app.services.reasoning.context_builder import ContextBuilder
from shared.contracts.reasoning import ValidationVerdict

@pytest.fixture(scope="function")
def db_setup():
    # Setup test DB schema
    Base.metadata.create_all(bind=engine)
    yield
    # Keep schema intact for application use
    Base.metadata.create_all(bind=engine)

def test_integration_flow(db_setup):
    repo = MemoryRepository()
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

    # 7. Retrieve context
    context = builder.build_context(attempt_id)
    assert "2x = 4" in context
    assert "x = 2" in context
    assert "VALID" in context
