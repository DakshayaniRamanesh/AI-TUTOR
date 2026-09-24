from enum import Enum
from typing import List, Optional
from pydantic import Field
from .common import ContractModel, StableId, CanvasBBox
from .tutoring import CitationChip

class VideoJobState(str, Enum):
    QUEUED = "QUEUED"
    PLANNING = "PLANNING"
    RENDERING = "RENDERING"
    READY = "READY"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class VideoGenerationRequest(ContractModel):
    request_id: StableId
    subject_id: Optional[StableId] = None
    notebook_id: Optional[StableId] = None
    
    anchor_bbox: Optional[CanvasBBox] = None
    recognized_content: str = ""
    tutor_mode: str = "EXPLAIN"
    explanation_goal: str = ""
    
    evidence_ids: List[StableId] = Field(default_factory=list)
    citations: List[CitationChip] = Field(default_factory=list)
    
    requested_duration: Optional[int] = None
    style: Optional[str] = None

class VideoJobCreated(ContractModel):
    request_id: StableId
    job_id: StableId
    status_url: str

class VideoGenerationResult(ContractModel):
    request_id: StableId
    job_id: StableId
    subject_id: Optional[StableId] = None
    notebook_id: Optional[StableId] = None
    
    video_path: Optional[str] = None
    error_message: Optional[str] = None
    citations_used: List[CitationChip] = Field(default_factory=list)

class VideoJobStatus(ContractModel):
    job_id: StableId
    state: VideoJobState
    progress_percent: int = 0
    message: str = ""
    result: Optional[VideoGenerationResult] = None
