"""
LaTeX-Based Animated Video Generation Package for Kestrel.

Provides semantic parsing of educational LaTeX, animation planning with
progressive document state accumulation, high-resolution 16:9 slide rendering,
FFmpeg video assembly, and an optional Edge TTS narration layer.

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
from .narration_planner import NarrationPlanner, NarrationPlan, NarrationSegment
from .tts_service import TTSService, AudioSegment, create_tts_service

__all__ = [
    # Document model
    "ElementType",
    "ImportanceLevel",
    "TransitionType",
    "DocumentElement",
    "LessonSection",
    "LessonDocument",
    # Core pipeline
    "LatexSemanticParser",
    "AnimationPlanner",
    "AnimationTimeline",
    "TimelineState",
    "VideoAssembler",
    # Voice narration plugin
    "NarrationPlanner",
    "NarrationPlan",
    "NarrationSegment",
    "TTSService",
    "AudioSegment",
    "create_tts_service",
    # LatexFrameRenderer, LatexVideoPipeline, VoiceEnabledPipeline are not eagerly exported
    # to avoid loading PyQt6 / pydantic at import time.
    # Import directly:
    #   from backend.latex_video.frame_renderer import LatexFrameRenderer
    #   from backend.latex_video.pipeline import LatexVideoPipeline
    #   from backend.latex_video.voice_pipeline import VoiceEnabledPipeline
]
