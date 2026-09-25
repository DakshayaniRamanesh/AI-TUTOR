from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import Field
from .common import ContractModel, StableId, CanvasBBox, CoordinateSpace
from .reasoning import CanvasAnchor
import time

class SemanticBlockType(str, Enum):
    MATH = "MATH"
    TEXT = "TEXT"
    MIXED = "MIXED"
    DIAGRAM = "DIAGRAM"
    UNKNOWN = "UNKNOWN"

class ContextScope(str, Enum):
    SELECTION = "SELECTION"
    ACTIVE_BLOCK = "ACTIVE_BLOCK"
    VIEWPORT = "VIEWPORT"
    CANVAS = "CANVAS"

class SemanticBlock(ContractModel):
    block_id: StableId
    block_type: SemanticBlockType = Field(default=SemanticBlockType.UNKNOWN)
    stroke_ids: List[StableId] = Field(default_factory=list)
    item_ids: List[StableId] = Field(default_factory=list)
    bbox: Optional[CanvasBBox] = None
    recognized_text: Optional[str] = None
    confidence: Optional[float] = None

class CanvasContext(ContractModel):
    board_id: StableId = Field(default="default_board")
    canvas_revision: Optional[int] = None
    viewport_bbox: Optional[CanvasBBox] = None
    selected_item_ids: List[StableId] = Field(default_factory=list)
    selected_stroke_ids: List[StableId] = Field(default_factory=list)
    semantic_blocks: List[SemanticBlock] = Field(default_factory=list)
    active_block_id: Optional[StableId] = None

class RetrievedEvidence(ContractModel):
    chunk_id: StableId
    material_id: Optional[StableId] = None
    document_title: Optional[str] = None
    chapter: Optional[str] = None
    section: Optional[str] = None
    page_number: Optional[int] = None
    snippet: str
    score: float = 1.0
    source: str = "lexical"  # lexical, vector, hybrid, graph

class LearnerObservationDTO(ContractModel):
    observation_type: str
    description: str
    occurrence_count: int = 1
    status: str = "ACTIVE"
    confidence: float = 1.0

class GraphConceptDTO(ContractModel):
    concept_key: str
    display_name: str
    relation: str
    evidence_count: int = 0

class GraphContext(ContractModel):
    focal_concepts: List[str] = Field(default_factory=list)
    neighbor_concepts: List[GraphConceptDTO] = Field(default_factory=list)

class LearningMemoryContext(ContractModel):
    session_id: Optional[StableId] = None
    attempt_id: Optional[StableId] = None
    recent_steps: List[Dict[str, Any]] = Field(default_factory=list)
    observations: List[LearnerObservationDTO] = Field(default_factory=list)

class RequestTrace(ContractModel):
    request_id: StableId
    subject_id: Optional[StableId] = None
    notebook_id: Optional[StableId] = None
    session_id: Optional[StableId] = None
    attempt_id: Optional[StableId] = None
    canvas_revision: Optional[int] = None
    semantic_block_id: Optional[StableId] = None
    created_at: float = Field(default_factory=time.time)

class ContextRequest(RequestTrace):
    user_id: Optional[StableId] = None
    scope: ContextScope = Field(default=ContextScope.SELECTION)
    canvas_context: Optional[CanvasContext] = None
    user_query: Optional[str] = None
    tutor_mode: str = "CHECK_STEP"
    selected_item_ids: List[StableId] = Field(default_factory=list)
    source_stroke_ids: List[StableId] = Field(default_factory=list)
    anchor_bbox: Optional[CanvasBBox] = None
    viewport_bbox: Optional[CanvasBBox] = None
    recognized_content: Optional[str] = None
    recognition_ambiguities: List[str] = Field(default_factory=list)
    recognition_confidence: Optional[float] = None
    group_revision: Optional[int] = None

class ContextBundle(ContractModel):
    request_id: StableId
    subject_id: Optional[StableId] = None
    notebook_id: Optional[StableId] = None
    session_id: Optional[StableId] = None
    attempt_id: Optional[StableId] = None
    current_work_text: Optional[str] = None
    canvas_anchor: Optional[CanvasAnchor] = None
    recent_reasoning_text: str = ""
    retrieved_evidence: List[RetrievedEvidence] = Field(default_factory=list)
    graph_context: Optional[GraphContext] = None
    learner_observations: List[LearnerObservationDTO] = Field(default_factory=list)
    diagnostic_reasons: List[str] = Field(default_factory=list)
