from typing import List, Optional
from enum import Enum
from pydantic import Field
from .common import ContractModel, StableId, CanvasBBox, CoordinateSpace

class CanvasAnchor(ContractModel):
    """Links a semantic reasoning concept back to physical UI items on the whiteboard."""
    item_ids: List[StableId] = Field(default_factory=list)
    board_id: StableId
    board_revision: Optional[str] = None
    bbox_snapshot: Optional[CanvasBBox] = None
    coordinate_space: CoordinateSpace = Field(default=CoordinateSpace.SCENE)

class ReasoningStepInput(ContractModel):
    """The input provided to the engine to evaluate a single logical step."""
    step_id: StableId
    anchors: List[CanvasAnchor] = Field(default_factory=list)
    student_text: str
    context_text: Optional[str] = None

class ValidationVerdict(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"

class ValidationResult(ContractModel):
    """The output of the engine after evaluating a step."""
    step_id: StableId
    verdict: ValidationVerdict = Field(default=ValidationVerdict.UNKNOWN)
    explanation: Optional[str] = None
