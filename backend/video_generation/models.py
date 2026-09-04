"""
Data models for the Manim AI Video Generator pipeline.

The original text/PDF workflow remains supported, while the whiteboard-aware
pipeline adds structured BoardSelection -> BoardIR -> TeachingPlan ->
Storyboard -> SceneSpec stages.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


@dataclass
class PathData:
    """One freehand path drawn by the user on the annotation canvas."""
    points: List[Tuple[float, float]] = field(default_factory=list)
    stroke_color: str = "#ef4444"
    stroke_width: int = 3


@dataclass
class AnnotationEvent:
    """One annotation event submitted by the video player."""
    timestamp: float
    frame_image: str = ""
    paths: List[PathData] = field(default_factory=list)
    comment: str = ""


@dataclass
class BoardSelection:
    """
    Structured whiteboard selection sent by the desktop client.

    `selected_items` and `nearby_items` contain the canvas objects' serialized
    dictionaries. `image_b64` is intentionally supplementary: native canvas
    data is the primary source of truth, while the raster crop lets a vision
    model interpret handwriting or ambiguous diagrams.
    """
    board_id: str = ""
    board_revision: Optional[str] = None
    bbox: Dict[str, float] = field(default_factory=dict)
    lasso_polygon: List[Tuple[float, float]] = field(default_factory=list)
    selected_items: List[Dict[str, Any]] = field(default_factory=list)
    nearby_items: List[Dict[str, Any]] = field(default_factory=list)
    image_b64: str = ""
    user_instruction: str = ""

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["BoardSelection"]:
        if not data:
            return None
        polygon = []
        for pt in data.get("lasso_polygon", []) or []:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                try:
                    polygon.append((float(pt[0]), float(pt[1])))
                except (TypeError, ValueError):
                    pass
        bbox = data.get("bbox", {}) if isinstance(data.get("bbox", {}), dict) else {}
        return cls(
            board_id=str(data.get("board_id", "") or ""),
            board_revision=data.get("board_revision"),
            bbox={k: float(v) for k, v in bbox.items() if k in {"x", "y", "width", "height"} and isinstance(v, (int, float))},
            lasso_polygon=polygon,
            selected_items=list(data.get("selected_items", []) or []),
            nearby_items=list(data.get("nearby_items", []) or []),
            image_b64=str(data.get("image_b64", "") or ""),
            user_instruction=str(data.get("user_instruction", "") or ""),
        )

    def has_content(self) -> bool:
        return bool(self.selected_items or self.image_b64 or self.user_instruction)


@dataclass
class BoardElement:
    id: str
    type: str
    selected: bool = True
    text: str = ""
    bbox: Dict[str, float] = field(default_factory=dict)
    properties: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class BoardRelation:
    source: str
    target: str
    relation: str
    confidence: float = 0.5


@dataclass
class BoardIR:
    """Normalized semantic representation of the selected board region."""
    elements: List[BoardElement] = field(default_factory=list)
    relations: List[BoardRelation] = field(default_factory=list)
    concepts: List[str] = field(default_factory=list)
    equations: List[str] = field(default_factory=list)
    questions: List[str] = field(default_factory=list)
    selected_element_ids: List[str] = field(default_factory=list)
    supporting_element_ids: List[str] = field(default_factory=list)
    probable_topic: str = ""
    learning_intent: str = ""
    ambiguities: List[str] = field(default_factory=list)
    vision_summary: str = ""
    extracted_text: str = ""


@dataclass
class TeachingStep:
    step_id: str
    before_state: str
    learner_question: str
    concept_or_rule: str
    explanation: str
    visual_strategy: str
    after_state: str
    misconception_to_avoid: Optional[str] = None
    estimated_duration: float = 5.0


@dataclass
class TeachingPlan:
    learning_objective: str = ""
    existing_knowledge: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    misconceptions: List[str] = field(default_factory=list)
    steps: List[TeachingStep] = field(default_factory=list)
    key_concepts: List[str] = field(default_factory=list)
    estimated_duration_seconds: int = 35


@dataclass
class SceneSpec:
    """
    Backend-neutral declarative animation scene.

    This intentionally mirrors the existing PenEcho objects/motions idea so the
    same conceptual scene can later power both an instant canvas preview and a
    deterministic Manim compiler.
    """
    scene_id: str
    title: str = ""
    learning_goal: str = ""
    duration_seconds: float = 8.0
    layout: str = "default"
    objects: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    narration: str = ""


@dataclass
class Storyboard:
    title: str = ""
    scenes: List[SceneSpec] = field(default_factory=list)
    rationale: str = ""


@dataclass
class SceneResult:
    scene_id: str
    manim_code: str = ""
    video_path: Optional[str] = None
    passed_validation: bool = False
    error: Optional[str] = None


@dataclass
class ValidationResult:
    stage: str
    passed: bool
    message: str = ""
    scene_id: Optional[str] = None


@dataclass
class VideoJob:
    """
    Shared LangGraph state object.

    Legacy fields are intentionally retained so text/PDF requests keep working
    while the new whiteboard-aware path is rolled out incrementally.
    """
    # Required fields
    job_id: str
    user_prompt: str
    document_text: str = ""

    page_range: Optional[str] = None
    emphasis_note: Optional[str] = None
    output_type: str = "video"
    subject_id: Optional[str] = None

    # Whiteboard-aware input / semantic state
    board_selection: Optional[BoardSelection] = None
    board_ir: Optional[BoardIR] = None
    teaching_plan: Optional[TeachingPlan] = None
    storyboard: Optional[Storyboard] = None
    scene_specs: List[SceneSpec] = field(default_factory=list)
    scene_results: List[SceneResult] = field(default_factory=list)
    validation_results: List[ValidationResult] = field(default_factory=list)

    # Optional fields with defaults
    pdf_path: str = ""
    status: JobStatus = JobStatus.PENDING
    step: str = "init"
    progress_percentage: int = 0

    story_script: Optional[str] = None
    manim_code: Optional[str] = None
    video_path: Optional[str] = None
    video_url: Optional[str] = None
    stitched_video_url: Optional[str] = None

    # CI / retry state
    retry_count: int = 0
    has_build_error: bool = False
    build_error_trace: Optional[str] = None

    # Story revision state
    revision_count: int = 0
    needs_revision: bool = False

    # Annotation
    annotations: List[AnnotationEvent] = field(default_factory=list)
    annotation_context: Dict[str, Any] = field(default_factory=dict)

    version: int = 1
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LatexJob:
    """LangGraph state object for the LaTeX conversion pipeline."""
    job_id: str
    image_b64: str
    template_type: str
    mode: str = "study"
    classroom_action: str = "Solve Question"

    status: JobStatus = JobStatus.PENDING
    step: str = "init"
    progress_percentage: int = 0

    raw_transcription: Optional[str] = None
    structured_latex: Optional[str] = None
    final_tex_code: Optional[str] = None
    pdf_path: Optional[str] = None
    pdf_url: Optional[str] = None

    retry_count: int = 0
    has_build_error: bool = False
    build_error_trace: Optional[str] = None

    error_message: Optional[str] = None
