from typing import List, Optional
from enum import Enum
from pydantic import Field
from .common import ContractModel, StableId
from .reasoning import CanvasAnchor, ValidationVerdict

class FeedbackSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class TutorMode(str, Enum):
    CHECK_STEP = "CHECK_STEP"
    AUTO_CHECK = "AUTO_CHECK"
    HINT = "HINT"
    EXPLAIN = "EXPLAIN"
    ASK = "ASK"
    SUMMARIZE = "SUMMARIZE"
    VERIFY = "VERIFY"

class CitationChip(ContractModel):
    chunk_id: Optional[StableId] = None
    material_id: Optional[StableId] = None
    document_title: Optional[str] = None
    chapter: Optional[str] = None
    section: Optional[str] = None
    page_number: Optional[int] = None
    snippet: str = ""

class TutorFeedback(ContractModel):
    """Pedagogical feedback intended for the student."""
    feedback_text: str
    socratic_hints: List[str] = Field(default_factory=list)
    severity: FeedbackSeverity = Field(default=FeedbackSeverity.INFO)
    anchors: List[CanvasAnchor] = Field(default_factory=list)
    citations: List[CitationChip] = Field(default_factory=list)
    spoken_text: Optional[str] = None
    verdict: Optional[ValidationVerdict] = None

from .context import RequestTrace

class TutorResponse(RequestTrace):
    """Authoritative response returned by TutorOrchestrator."""
    tutor_mode: TutorMode = Field(default=TutorMode.CHECK_STEP)
    verdict: Optional[ValidationVerdict] = None
    feedback_text: str
    socratic_hints: List[str] = Field(default_factory=list)
    severity: FeedbackSeverity = Field(default=FeedbackSeverity.INFO)
    anchors: List[CanvasAnchor] = Field(default_factory=list)
    citations: List[CitationChip] = Field(default_factory=list)
    spoken_text: Optional[str] = None
    source_mode: str = "OFFLINE_LOCAL"  # OFFLINE_LOCAL, HYBRID_RAG, LLM_SYNTHESIS
    is_stale: bool = False

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
