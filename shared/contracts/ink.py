from typing import List, Optional
from pydantic import Field
from .common import ContractModel, StableId, CanvasBBox

class InkPoint(ContractModel):
    x: float
    y: float
    pressure: float = Field(default=1.0, ge=0.0, le=1.0)
    timestamp_ms: Optional[int] = None

class InkStroke(ContractModel):
    id: StableId
    board_id: StableId
    points: List[InkPoint] = Field(default_factory=list, min_length=1)
    tool_type: str = Field(default="pen")
    color: str = Field(default="#1c1c1e")
    width: float = Field(default=3.0, ge=0.0)
    bbox: CanvasBBox

class InkGroup(ContractModel):
    id: StableId
    board_id: StableId
    revision: int = Field(default=0)
    stroke_ids: List[StableId] = Field(default_factory=list, min_length=1)
    bbox: CanvasBBox
