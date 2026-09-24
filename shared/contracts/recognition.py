from typing import List, Optional
from enum import Enum
from pydantic import Field, model_validator
from .common import ContractModel, StableId, CanvasBBox, CoordinateSpace

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
    notebook_id: Optional[StableId] = None
    attempt_id: Optional[StableId] = None
    group_id: StableId
    group_revision: int
    source_stroke_ids: List[StableId] = Field(default_factory=list, min_length=1)
    group_bbox: Optional[CanvasBBox] = None
    coordinate_space: CoordinateSpace = Field(default=CoordinateSpace.SCENE)
    image_b64: Optional[str] = None
    expected_type: Optional[ContentType] = None
    is_auto_check: bool = False

class RecognitionResult(ContractModel):
    request_id: StableId
    board_id: StableId
    notebook_id: Optional[StableId] = None
    attempt_id: Optional[StableId] = None
    group_id: StableId
    group_revision: int
    source_stroke_ids: List[StableId] = Field(default_factory=list, min_length=1)
    group_bbox: Optional[CanvasBBox] = None
    coordinate_space: CoordinateSpace = Field(default=CoordinateSpace.SCENE)
    is_auto_check: bool = False
    
    status: RecognitionStatus
    content_type: ContentType = Field(default=ContentType.UNKNOWN)
    
    # Parsed interpretations
    plain_text: Optional[str] = None
    latex: Optional[str] = None
    normalized_expression: Optional[str] = None
    
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    alternatives: List[RecognitionAlternative] = Field(default_factory=list)
    
    # Traceability
    provider_name: str
    warnings: List[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_content_and_confidence(self) -> 'RecognitionResult':
        if self.status == RecognitionStatus.SUCCESS:
            if not (self.plain_text or self.latex or self.normalized_expression):
                raise ValueError("SUCCESS status requires at least one parsed output (plain_text, latex, or normalized_expression).")
        elif self.status == RecognitionStatus.FAILED:
            if self.confidence is not None and self.confidence > 0.0:
                raise ValueError("FAILED status cannot have a confidence > 0.0.")
        return self
