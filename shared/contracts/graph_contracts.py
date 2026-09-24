from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field, model_validator
import datetime
from enum import Enum

class NodeType(str, Enum):
    SUBJECT = "SUBJECT"
    MODULE = "MODULE"
    CONCEPT = "CONCEPT"
    RESOURCE = "RESOURCE"
    NOTEBOOK = "NOTEBOOK"
    EXERCISE = "EXERCISE"
    EXAMPLE = "EXAMPLE"

class RelationType(str, Enum):
    PART_OF = "PART_OF"
    PREREQUISITE_OF = "PREREQUISITE_OF"
    EXPLAINS = "EXPLAINS"
    EXAMPLE_OF = "EXAMPLE_OF"
    APPLIES_TO = "APPLIES_TO"
    RELATED_TO = "RELATED_TO"
    CONTAINS = "CONTAINS"
    MENTIONS = "MENTIONS"
    PRACTICED_IN = "PRACTICED_IN"
    DERIVED_FROM = "DERIVED_FROM"

ExtractionMode = Literal["ONLINE_STRUCTURED", "OFFLINE_STRUCTURAL", "PARTIAL", "FAILED"]

class GraphEvidenceDTO(BaseModel):
    id: str
    subject_id: Optional[str] = None
    notebook_id: Optional[str] = None
    material_id: Optional[str] = None
    chunk_id: Optional[str] = None
    page_number: Optional[int] = None
    snippet: Optional[str] = None
    confidence: Optional[float] = None

class GraphNodeDTO(BaseModel):
    id: str
    subject_id: str
    canonical_key: str
    display_name: str
    node_type: NodeType
    description: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    evidence_counts: int = 0
    extraction_mode: Optional[ExtractionMode] = None
    evidence: List[GraphEvidenceDTO] = Field(default_factory=list)

    @model_validator(mode='after')
    def check_semantic_evidence(self):
        if self.extraction_mode in ("ONLINE_STRUCTURED", "ONLINE_SEMANTIC") and self.node_type not in ("SUBJECT", "RESOURCE", "NOTEBOOK"):
            if not self.evidence or not any(ev.chunk_id for ev in self.evidence):
                raise ValueError("Semantic nodes require valid chunk_id evidence.")
        return self

class GraphEdgeDTO(BaseModel):
    id: str
    subject_id: str
    source_node_id: str
    target_node_id: str
    relation_type: RelationType
    evidence_counts: int = 0
    extraction_mode: Optional[ExtractionMode] = None
    evidence: List[GraphEvidenceDTO] = Field(default_factory=list)

    @model_validator(mode='after')
    def check_semantic_evidence(self):
        if self.extraction_mode in ("ONLINE_STRUCTURED", "ONLINE_SEMANTIC") and self.relation_type not in ("PART_OF",):
            if not self.evidence or not any(ev.chunk_id for ev in self.evidence):
                raise ValueError("Semantic edges require valid chunk_id evidence.")
        return self
    
class GraphLayoutStateDTO(BaseModel):
    node_id: str
    x: float
    y: float
    pinned: bool = False

class GraphSnapshot(BaseModel):
    scope: Literal["SUBJECT", "GLOBAL"]
    scope_id: Optional[str]
    revision: int
    nodes: List[GraphNodeDTO] = Field(default_factory=list)
    edges: List[GraphEdgeDTO] = Field(default_factory=list)
    layout: Dict[str, GraphLayoutStateDTO] = Field(default_factory=dict)
    build_state: Literal["NOT_BUILT", "QUEUED", "EXTRACTING", "MERGING", "READY", "PARTIAL", "FAILED"] = "NOT_BUILT"
    created_time: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

class GraphBuildRequest(BaseModel):
    subject_id: str
    material_id: Optional[str] = None
    request_id: str
    resource_revision: str
