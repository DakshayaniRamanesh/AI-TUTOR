"""
Shape Metadata Registry & Unit Conversion Utilities.

Provides a unified descriptor mapping for all 7 shape types:
- Circle
- Ellipse
- Rectangle
- Square
- Straight Line
- Arrow
- Cloud

Also provides pure unit conversion functions between canvas pixels and mm, cm, m, inch.
"""

from typing import Dict, List, Any, Tuple, Callable
import math

# Default canvas DPI (96 CSS / standard display pixels per inch)
DEFAULT_CANVAS_DPI: float = 96.0

# Supported measurement units
SUPPORTED_UNITS: List[str] = ["mm", "cm", "m", "inch"]
DEFAULT_UNIT: str = "mm"

# Unit conversion multipliers relative to inches (1 inch = 25.4 mm = 2.54 cm = 0.0254 m)
MM_PER_INCH: float = 25.4
CM_PER_INCH: float = 2.54
M_PER_INCH: float = 0.0254


def convert_px_to_unit(val_px: float, unit: str, dpi: float = DEFAULT_CANVAS_DPI) -> float:
    """
    Converts canvas pixel value to target physical measurement unit.
    
    Parameters:
        val_px: Value in canvas pixels.
        unit: Target unit ('mm', 'cm', 'm', 'inch').
        dpi: Canvas DPI (dots per inch).
        
    Returns:
        Converted value as float.
    """
    if dpi <= 0:
        dpi = DEFAULT_CANVAS_DPI
        
    inches = val_px / dpi
    
    unit_lower = unit.lower()
    if unit_lower == "mm":
        return inches * MM_PER_INCH
    elif unit_lower == "cm":
        return inches * CM_PER_INCH
    elif unit_lower == "m":
        return inches * M_PER_INCH
    elif unit_lower == "inch" or unit_lower == "in":
        return inches
    elif unit_lower == "px":
        return val_px
    else:
        # Default fallback to mm
        return inches * MM_PER_INCH


def convert_unit_to_px(val_unit: float, unit: str, dpi: float = DEFAULT_CANVAS_DPI) -> float:
    """
    Converts physical measurement unit value back to canvas pixels.
    
    Parameters:
        val_unit: Value in physical measurement units.
        unit: Source unit ('mm', 'cm', 'm', 'inch').
        dpi: Canvas DPI (dots per inch).
        
    Returns:
        Value in canvas pixels.
    """
    if dpi <= 0:
        dpi = DEFAULT_CANVAS_DPI
        
    unit_lower = unit.lower()
    if unit_lower == "mm":
        inches = val_unit / MM_PER_INCH
    elif unit_lower == "cm":
        inches = val_unit / CM_PER_INCH
    elif unit_lower == "m":
        inches = val_unit / M_PER_INCH
    elif unit_lower == "inch" or unit_lower == "in":
        inches = val_unit
    elif unit_lower == "px":
        return val_unit
    else:
        inches = val_unit / MM_PER_INCH
        
    return inches * dpi


# ==============================================================================
# UNIFIED SHAPE METADATA DEFINITIONS
# ==============================================================================
# Each entry defines:
# - display_name: Human readable label for UI
# - fields: Dict of field_key -> {label, min_val, step}
# - handles: List of handle definitions for ShapeResizeHandles
# ==============================================================================

SHAPE_METADATA: Dict[str, Dict[str, Any]] = {
    "circle": {
        "display_name": "Circle",
        "fields": [
            {"key": "radius", "label": "Radius", "min": 1.0, "step": 1.0}
        ],
        "handles": [
            {"name": "right", "index": 0, "cursor": "SizeHorCursor"},
            {"name": "bottom", "index": 1, "cursor": "SizeVerCursor"},
            {"name": "left", "index": 2, "cursor": "SizeHorCursor"},
            {"name": "top", "index": 3, "cursor": "SizeVerCursor"}
        ]
    },
    "ellipse": {
        "display_name": "Ellipse",
        "fields": [
            {"key": "width", "label": "Width", "min": 1.0, "step": 1.0},
            {"key": "height", "label": "Height", "min": 1.0, "step": 1.0}
        ],
        "handles": [
            {"name": "right", "index": 0, "cursor": "SizeHorCursor"},
            {"name": "bottom", "index": 1, "cursor": "SizeVerCursor"},
            {"name": "left", "index": 2, "cursor": "SizeHorCursor"},
            {"name": "top", "index": 3, "cursor": "SizeVerCursor"}
        ]
    },
    "rectangle": {
        "display_name": "Rectangle",
        "fields": [
            {"key": "width", "label": "Width", "min": 1.0, "step": 1.0},
            {"key": "height", "label": "Height", "min": 1.0, "step": 1.0}
        ],
        "handles": [
            {"name": "top_left", "index": 0, "cursor": "SizeFDiagCursor"},
            {"name": "top_mid", "index": 1, "cursor": "SizeVerCursor"},
            {"name": "top_right", "index": 2, "cursor": "SizeBDiagCursor"},
            {"name": "right_mid", "index": 3, "cursor": "SizeHorCursor"},
            {"name": "bottom_right", "index": 4, "cursor": "SizeFDiagCursor"},
            {"name": "bottom_mid", "index": 5, "cursor": "SizeVerCursor"},
            {"name": "bottom_left", "index": 6, "cursor": "SizeBDiagCursor"},
            {"name": "left_mid", "index": 7, "cursor": "SizeHorCursor"}
        ]
    },
    "square": {
        "display_name": "Square",
        "fields": [
            {"key": "side", "label": "Side Length", "min": 1.0, "step": 1.0}
        ],
        "handles": [
            {"name": "top_left", "index": 0, "cursor": "SizeFDiagCursor"},
            {"name": "top_mid", "index": 1, "cursor": "SizeVerCursor"},
            {"name": "top_right", "index": 2, "cursor": "SizeBDiagCursor"},
            {"name": "right_mid", "index": 3, "cursor": "SizeHorCursor"},
            {"name": "bottom_right", "index": 4, "cursor": "SizeFDiagCursor"},
            {"name": "bottom_mid", "index": 5, "cursor": "SizeVerCursor"},
            {"name": "bottom_left", "index": 6, "cursor": "SizeBDiagCursor"},
            {"name": "left_mid", "index": 7, "cursor": "SizeHorCursor"}
        ]
    },
    "line": {
        "display_name": "Straight Line",
        "fields": [
            {"key": "length", "label": "Length", "min": 1.0, "step": 1.0}
        ],
        "handles": [
            {"name": "p1", "index": 0, "cursor": "CrossCursor"},
            {"name": "p2", "index": 1, "cursor": "CrossCursor"}
        ]
    },
    "arrow": {
        "display_name": "Arrow",
        "fields": [
            {"key": "length", "label": "Length", "min": 1.0, "step": 1.0}
        ],
        "handles": [
            {"name": "p1", "index": 0, "cursor": "CrossCursor"},
            {"name": "p2", "index": 1, "cursor": "CrossCursor"}
        ]
    },
    "cloud": {
        "display_name": "Cloud Node",
        "fields": [
            {"key": "width", "label": "Width", "min": 10.0, "step": 1.0},
            {"key": "height", "label": "Height", "min": 10.0, "step": 1.0}
        ],
        "handles": [
            {"name": "top_left", "index": 0, "cursor": "SizeFDiagCursor"},
            {"name": "top_right", "index": 2, "cursor": "SizeBDiagCursor"},
            {"name": "bottom_right", "index": 4, "cursor": "SizeFDiagCursor"},
            {"name": "bottom_left", "index": 6, "cursor": "SizeBDiagCursor"}
        ]
    },
    "triangle": {
        "display_name": "Triangle / Polygon",
        "fields": [
            {"key": "width", "label": "Width", "min": 1.0, "step": 1.0},
            {"key": "height", "label": "Height", "min": 1.0, "step": 1.0},
            {"key": "num_sides", "label": "Number of Sides", "min": 3.0, "max": 12.0, "step": 1.0, "is_int": True, "unit_convert": False}
        ],
        "handles": [
            {"name": "top_left", "index": 0, "cursor": "SizeFDiagCursor"},
            {"name": "top_right", "index": 2, "cursor": "SizeBDiagCursor"},
            {"name": "bottom_right", "index": 4, "cursor": "SizeFDiagCursor"},
            {"name": "bottom_left", "index": 6, "cursor": "SizeBDiagCursor"}
        ]
    }
}
