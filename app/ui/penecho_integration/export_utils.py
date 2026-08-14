"""
High-DPI Lossless Cropped Canvas Exporter for AI-TUTOR.
Ported from penecho/src/client/app/canvas-runtime.js.

Provides:
- export_canvas_to_image: Lossless PNG/JPG export cropped to content bounding box
  with configurable margin padding and 1x-3x adaptive high-DPI scaling.
"""

from typing import Optional
from PyQt6.QtWidgets import QGraphicsScene
from PyQt6.QtGui import QImage, QPainter, QColor
from PyQt6.QtCore import QRectF, QSize, Qt


def export_canvas_to_image(
    scene: QGraphicsScene,
    output_path: str,
    margin_px: float = 40.0,
    scale_factor: float = 2.0,
    background_color: Optional[str] = None
) -> bool:
    """
    Renders the scene's content items into a high-DPI cropped image file.
    """
    items = [item for item in scene.items() if item.isVisible()]
    if not items:
        # Fallback to scene rect if empty
        crop_rect = QRectF(0, 0, 800, 600)
    else:
        # Compute union bounding rect of all visible items
        min_x = min(item.sceneBoundingRect().left() for item in items)
        min_y = min(item.sceneBoundingRect().top() for item in items)
        max_x = max(item.sceneBoundingRect().right() for item in items)
        max_y = max(item.sceneBoundingRect().bottom() for item in items)
        crop_rect = QRectF(
            min_x - margin_px,
            min_y - margin_px,
            (max_x - min_x) + margin_px * 2,
            (max_y - min_y) + margin_px * 2
        )

    out_width = int(crop_rect.width() * scale_factor)
    out_height = int(crop_rect.height() * scale_factor)
    if out_width <= 0 or out_height <= 0:
        return False

    image = QImage(QSize(out_width, out_height), QImage.Format.Format_ARGB32_Premultiplied)
    
    # Fill background
    bg_col = QColor(background_color) if background_color else QColor("#ffffff")
    image.fill(bg_col)

    painter = QPainter(image)
    painter.setRenderHints(
        QPainter.RenderHint.Antialiasing |
        QPainter.RenderHint.SmoothPixmapTransform |
        QPainter.RenderHint.TextAntialiasing
    )

    target_rect = QRectF(0, 0, out_width, out_height)
    scene.render(painter, target_rect, crop_rect)
    painter.end()

    return image.save(output_path)
