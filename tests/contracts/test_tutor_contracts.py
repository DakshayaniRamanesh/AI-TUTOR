import pytest
from pydantic import ValidationError
from shared.contracts.tutoring import (
    TutorFeedback, 
    FeedbackSeverity, 
    EngineFailure, 
    ErrorCode
)

def test_tutor_feedback_defaults():
    feedback = TutorFeedback(feedback_text="Good job!")
    assert feedback.severity == FeedbackSeverity.INFO
    assert len(feedback.socratic_hints) == 0
    assert len(feedback.anchors) == 0

def test_engine_failure_retryable_enforcement():
    # Should accept booleans
    fail1 = EngineFailure(request_id="req_1", provider_name="groq", user_message="Timeout", is_retryable=True)
    assert fail1.is_retryable is True
    
    # Should reject non-booleans/garbage
    with pytest.raises(ValidationError):
        EngineFailure(request_id="req_2", provider_name="groq", user_message="Bad data", is_retryable="maybe")

def test_error_code_enum():
    fail = EngineFailure(request_id="req_3", provider_name="groq", error_code=ErrorCode.NETWORK_TIMEOUT, user_message="Net down")
    assert fail.error_code == "NETWORK_TIMEOUT"
    
    with pytest.raises(ValidationError):
        EngineFailure(request_id="req_4", provider_name="groq", error_code="INTERNET_BROKEN", user_message="Net down")
