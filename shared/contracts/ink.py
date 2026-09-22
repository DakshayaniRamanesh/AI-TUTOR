from typing import List
from pydantic import Field
from .common import ContractModel, StableId, CanvasBBox

class InkPoint(ContractModel):
    x: float
    y: float
    pressure: float = Field(default=1.0, ge=0.0, le=1.0)
    timestamp: float

class InkStroke(ContractModel):
    id: StableId
    board_id: StableId
    points: List[InkPoint] = Field(default_factory=list)
    tool_type: str = Field(default="pen")
    color: str = Field(default="#1c1c1e")
    width: float = Field(default=3.0, ge=0.0)
    bbox: CanvasBBox

class InkGroup(ContractModel):
    id: StableId
    board_id: StableId
    stroke_ids: List[StableId] = Field(default_factory=list)
    bbox: CanvasBBox
