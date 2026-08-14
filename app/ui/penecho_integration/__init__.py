"""
Penecho Canvas Integration Package for AI-TUTOR.
Exposes ported drawing protocols, mathematical/markdown parsers, animation engine,
freehand lasso selection, and procedural curve loaders.
"""

from .unified_draw import PenechoDrawItem, normalize_drawing_command
from .mixed_text import PenechoMixedTextItem, parse_mixed_text, mixed_tokens_to_html
from .animation_engine import PenechoAnimationItem, normalize_animation_scene, evaluate_scene_state
from .lasso_selection import PenechoLassoOverlay, point_in_polygon, polygon_bounds
from .summon_widgets import PenechoSummonItem, generate_curve_points
from .export_utils import export_canvas_to_image
from .draft_layer import PenechoDraftLayerItem
from .ai_canvas_bridge import AICanvasWorker, create_draft_from_payload

__all__ = [
    "PenechoDrawItem",
    "normalize_drawing_command",
    "PenechoMixedTextItem",
    "parse_mixed_text",
    "mixed_tokens_to_html",
    "PenechoAnimationItem",
    "normalize_animation_scene",
    "evaluate_scene_state",
    "PenechoLassoOverlay",
    "point_in_polygon",
    "polygon_bounds",
    "PenechoSummonItem",
    "generate_curve_points",
    "export_canvas_to_image",
    "PenechoDraftLayerItem",
    "AICanvasWorker",
    "create_draft_from_payload",
]
