from enum import Enum
from typing import List, Optional
from pydantic import Field
from .common import ContractModel, StableId, CanvasBBox

class LatexGenerationMode(str, Enum):
    SELECTION_EXACT = "SELECTION_EXACT"
    VIEWPORT_DOCUMENT = "VIEWPORT_DOCUMENT"

class LatexSourceAnchor(ContractModel):
    selected_item_ids: List[StableId] = Field(default_factory=list)
    selected_stroke_ids: List[StableId] = Field(default_factory=list)
    scene_bbox: Optional[CanvasBBox] = None
    image_width: int = 0
    image_height: int = 0

class LatexGenerationRequest(ContractModel):
    request_id: StableId
    subject_id: Optional[StableId] = None
    notebook_id: Optional[StableId] = None
    canvas_revision: Optional[int] = None
    mode: LatexGenerationMode
    anchor: LatexSourceAnchor
    image_b64: str
    template_type: Optional[str] = "Homework"
    classroom_action: Optional[str] = "Solve Question"
    evidence_ids: List[StableId] = Field(default_factory=list)
    created_at: float = Field(default_factory=lambda: 0.0)

class LatexCompilationResult(ContractModel):
    status: str  # e.g., "SUCCESS", "FAILED"
    warnings: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    output_pdf_path: Optional[str] = None

class LatexGenerationResult(ContractModel):
    request_id: StableId
    subject_id: Optional[StableId] = None
    notebook_id: Optional[StableId] = None
    canvas_revision: Optional[int] = None
    
    generated_latex: str
    is_document: bool = False
    provider_used: str = "local"
    
    compilation: Optional[LatexCompilationResult] = None
