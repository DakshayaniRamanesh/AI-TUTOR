from typing import List, Optional
from enum import Enum
from pydantic import Field
from .common import ContractModel, StableId
from .reasoning import CanvasAnchor

class FeedbackSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class TutorFeedback(ContractModel):
    """Pedagogical feedback intended for the student."""
    feedback_text: str
    socratic_hints: List[str] = Field(default_factory=list)
    severity: FeedbackSeverity = Field(default=FeedbackSeverity.INFO)
    anchors: List[CanvasAnchor] = Field(default_factory=list)

class ErrorCode(str, Enum):
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    PARSE_FAILED = "PARSE_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNKNOWN = "UNKNOWN"

class EngineFailure(ContractModel):
    """System failure indicating the engine could not process the request."""
    request_id: StableId
    provider_name: str
    error_code: ErrorCode = Field(default=ErrorCode.UNKNOWN)
    user_message: str
    technical_details: Optional[str] = Field(default=None, repr=False)
    is_retryable: bool = Field(default=False)
