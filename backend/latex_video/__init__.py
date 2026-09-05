"""
LaTeX-Based Animated Video Generation Package for Kestrel.

Provides semantic parsing of educational LaTeX, animation planning with
progressive document state accumulation, high-resolution 16:9 slide rendering,
and FFmpeg video assembly.

Heavy runtime dependencies (PyQt6, pydantic) are imported lazily by their
respective modules to keep the package importable in lightweight test environments.
"""

from .document_model import (
    ElementType,
    ImportanceLevel,
    TransitionType,
    DocumentElement,
    LessonSection,
    LessonDocument,
)
from .latex_parser import LatexSemanticParser
from .animation_planner import AnimationPlanner, AnimationTimeline, TimelineState
from .video_assembler import VideoAssembler

__all__ = [
    "ElementType",
    "ImportanceLevel",
    "TransitionType",
    "DocumentElement",
    "LessonSection",
    "LessonDocument",
    "LatexSemanticParser",
    "AnimationPlanner",
    "AnimationTimeline",
    "TimelineState",
    "VideoAssembler",
    # LatexFrameRenderer and LatexVideoPipeline are not eagerly exported
    # to avoid loading PyQt6 / pydantic at import time.
    # Import them directly: from backend.latex_video.frame_renderer import LatexFrameRenderer
]
