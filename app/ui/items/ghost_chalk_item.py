"""
GhostChalkItem — Teacher-Style Ghost Chalk & Error Highlighting for Kestrel.
Developer 1: Visual and Audio Canvas Studio.

Specifications:
- QGraphicsObject embedded in canvas scene coordinates.
- Receives target bounding rectangle (QRectF) containing relevant canvas content.
- Animates drawing over ~600ms to feel like a teacher actively marking the work.
- Two visual states:
    - Error mode (#ff6b6b): Soft coral/amber glowing oval or bracket indicating a problem.
    - Verified mode (#2ecc71): Faint emerald underline or check indicating success.
"""

import math
from enum import Enum
from typing import Optional

from PyQt6.QtWidgets import QGraphicsObject
from PyQt6.QtCore import (
    Qt, QRectF, QPointF, pyqtProperty, pyqtSignal,
    QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QPainterPath, QBrush
)


class GhostChalkMode(Enum):
    ERROR = "error"          # #ff6b6b coral/amber loop
    VERIFIED = "verified"    # #2ecc71 emerald underline


class GhostChalkItem(QGraphicsObject):
    """
    Renders an animated hand-drawn chalk annotation around or beneath student work.
    """
    drawing_completed = pyqtSignal()

    def __init__(self, rect: QRectF, mode: GhostChalkMode = GhostChalkMode.ERROR, parent=None):
        super().__init__(parent)
        self.setZValue(990)  # Just under the laser pointer, above ink strokes
        
        self._target_rect = QRectF(rect)
        self._mode = mode
        self._progress = 0.0     # 0.0 to 1.0 (animated)
        self._opacity = 1.0
        
        # Color mapping
        self._color_error = QColor("#ff6b6b")
        self._color_verified = QColor("#2ecc71")

        # Animation setup
        self._anim = QPropertyAnimation(self, b"progress")
        self._anim.setDuration(600)  # ~600ms per spec
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim.finished.connect(self._on_draw_finished)

    # ── Qt Property: progress ─────────────────────────────────────────────────

    def get_progress(self) -> float:
        return self._progress

    def set_progress(self, val: float):
        self._progress = float(val)
        self.update()

    progress = pyqtProperty(float, get_progress, set_progress)

    # ── Qt Property: opacity ──────────────────────────────────────────────────

    def get_opacity_val(self) -> float:
        return self._opacity

    def set_opacity_val(self, val: float):
        self._opacity = float(val)
        self.setOpacity(self._opacity)
        self.update()

    opacityVal = pyqtProperty(float, get_opacity_val, set_opacity_val)

    # ── Geometry & Bounding ───────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        # Expand bounds for chalk glow and padding
        padding = 24.0
        return self._target_rect.adjusted(-padding, -padding, padding, padding)

    def set_target_rect(self, rect: QRectF, mode: Optional[GhostChalkMode] = None):
        """Updates the target area and triggers re-drawing animation."""
        self.prepareGeometryChange()
        self._target_rect = QRectF(rect)
        if mode:
            self._mode = mode
        self.start_animation()

    def start_animation(self):
        """Animates the chalk drawing from 0.0 to 1.0."""
        self._progress = 0.0
        if self._anim.state() == QPropertyAnimation.State.Running:
            self._anim.stop()
        self._anim.start()

    def _on_draw_finished(self):
        self.drawing_completed.emit()

    # ── Hand-Drawn Chalk Path Generation ──────────────────────────────────────

    def _generate_chalk_oval_path(self, rect: QRectF, progress: float) -> QPainterPath:
        """
        Builds an organic hand-drawn oval path wrapping around the target rect,
        interpolated up to `progress`. Adds subtle teacher-chalk natural wobble.
        """
        path = QPainterPath()
        if progress <= 0.0:
            return path

        cx = rect.center().x()
        cy = rect.center().y()
        rx = (rect.width() / 2.0) + 12.0
        ry = (rect.height() / 2.0) + 8.0

        # Full oval is 0 to 2*pi + slight overlap (0.35 rad) for teacher look
        max_angle = (2.0 * math.pi + 0.35) * progress
        num_points = max(10, int(60 * progress))

        for i in range(num_points + 1):
            theta = (i / num_points) * max_angle
            # Slight harmonic wobble for genuine chalk feel
            wobble = 1.6 * math.sin(3.0 * theta) + 0.8 * math.cos(5.0 * theta)
            x = cx + (rx + wobble) * math.cos(theta)
            y = cy + (ry + wobble * 0.7) * math.sin(theta)

            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        return path

    def _generate_chalk_underline_path(self, rect: QRectF, progress: float) -> QPainterPath:
        """
        Builds a smooth teacher double-underline or check arc beneath the target rect.
        """
        path = QPainterPath()
        if progress <= 0.0:
            return path

        x_start = rect.left() - 6.0
        x_end = rect.right() + 6.0
        total_width = x_end - x_start
        current_x = x_start + total_width * progress

        y_base = rect.bottom() + 6.0

        num_points = max(5, int(40 * progress))
        for i in range(num_points + 1):
            px = x_start + (current_x - x_start) * (i / num_points)
            norm = (px - x_start) / max(1.0, total_width)
            # Gentle swoop: slight dip in the middle then rising slightly at the end
            py = y_base + 3.0 * math.sin(norm * math.pi) + 0.7 * math.sin(norm * 8.0)
            if i == 0:
                path.moveTo(px, py)
            else:
                path.lineTo(px, py)

        return path

    # ── Paint Overrides ───────────────────────────────────────────────────────

    def paint(self, painter: QPainter, option, widget=None):
        if self._progress <= 0.01:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        base_color = self._color_error if self._mode == GhostChalkMode.ERROR else self._color_verified
        
        # Select path generator based on mode
        if self._mode == GhostChalkMode.ERROR:
            path = self._generate_chalk_oval_path(self._target_rect, self._progress)
        else:
            path = self._generate_chalk_underline_path(self._target_rect, self._progress)

        # 1. Diffuse soft glowing outer aura
        aura_color = QColor(base_color)
        aura_color.setAlpha(45)
        aura_pen = QPen(aura_color, 8.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.strokePath(path, aura_pen)

        # 2. Mid-glow layer
        mid_color = QColor(base_color)
        mid_color.setAlpha(110)
        mid_pen = QPen(mid_color, 4.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.strokePath(path, mid_pen)

        # 3. Crisp chalk stroke center
        core_color = QColor(base_color)
        core_color.setAlpha(225)
        core_pen = QPen(core_color, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.strokePath(path, core_pen)
