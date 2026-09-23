from typing import List, Optional
from enum import Enum
from pydantic import Field, model_validator
from .common import ContractModel, StableId

class RecognitionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    AMBIGUOUS = "AMBIGUOUS"
    FAILED = "FAILED"

class ContentType(str, Enum):
    TEXT = "TEXT"
    EQUATION = "EQUATION"
    DIAGRAM = "DIAGRAM"
    UNKNOWN = "UNKNOWN"

class RecognitionAlternative(ContractModel):
    text: str
    latex: Optional[str] = None
    normalized_expression: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)

class RecognitionRequest(ContractModel):
    request_id: StableId
    board_id: StableId
    learning_session_id: StableId
    stroke_group_id: StableId
    source_stroke_ids: List[StableId] = Field(default_factory=list)
    image_b64: Optional[str] = None
    expected_type: Optional[ContentType] = None

class RecognitionResult(ContractModel):
    request_id: StableId
    status: RecognitionStatus
    content_type: ContentType = Field(default=ContentType.UNKNOWN)
    
    # Parsed interpretations
    plain_text: Optional[str] = None
    latex: Optional[str] = None
    normalized_expression: Optional[str] = None
    
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    alternatives: List[RecognitionAlternative] = Field(default_factory=list)
    
    # Traceability
    source_stroke_ids: List[StableId] = Field(default_factory=list, min_length=1)
    provider_name: str
    warnings: List[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_content_and_confidence(self) -> 'RecognitionResult':
        if self.status == RecognitionStatus.SUCCESS:
            if not (self.plain_text or self.latex or self.normalized_expression):
                raise ValueError("SUCCESS status requires at least one parsed output (plain_text, latex, or normalized_expression).")
        elif self.status == RecognitionStatus.FAILED:
            if self.confidence > 0.0:
                raise ValueError("FAILED status cannot have a confidence > 0.0.")
        return self
