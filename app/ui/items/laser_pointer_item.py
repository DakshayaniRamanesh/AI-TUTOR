"""
LaserPointerItem — Native Animated Laser Pointer for Kestrel Whiteboard.
Developer 1: Visual and Audio Canvas Studio.

Specifications:
- QGraphicsObject embedded in canvas scene coordinates (pans/zooms with math content).
- Layered radial gradient: intense hot-red/amber center (~6px radius) surrounded by
  semi-transparent outer glow (~20px radius).
- Smooth motion via QPropertyAnimation along a curved / Bézier path.
- Idle pulsing / breathing opacity effect once target is reached.
"""

from PyQt6.QtWidgets import QGraphicsObject
from PyQt6.QtCore import (
    Qt, QPointF, QRectF, pyqtProperty, pyqtSignal,
    QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
)
from PyQt6.QtGui import QPainter, QRadialGradient, QColor, QBrush


class LaserPointerItem(QGraphicsObject):
    """
    Animated glowing laser pointer indicating where the AI tutor is looking.
    """
    arrived = pyqtSignal(QPointF)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setZValue(1000)  # Always above ink strokes and cards
        
        # Visual styling parameters
        self._core_radius = 6.0
        self._glow_radius = 20.0
        self._core_color = QColor(255, 69, 58, 255)       # Intense hot coral-red
        self._halo_color = QColor(255, 149, 0, 180)       # Amber glow
        self._glow_color = QColor(255, 59, 48, 0)         # Fade out to transparent
        
        # Animated properties
        self._pulse_opacity = 0.95
        self._scale_factor = 1.0
        self._current_pos = QPointF(0, 0)
        self.setPos(self._current_pos)

        # Pulse animation setup
        self._pulse_anim = QPropertyAnimation(self, b"pulseOpacity")
        self._pulse_anim.setDuration(1200)
        self._pulse_anim.setStartValue(0.65)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse_anim.setLoopCount(-1)  # Infinite breathing loop

        # Motion animation
        self._move_anim = None
        self._group = None

    # ── Qt Property: pulseOpacity ─────────────────────────────────────────────

    def get_pulse_opacity(self) -> float:
        return self._pulse_opacity

    def set_pulse_opacity(self, val: float):
        self._pulse_opacity = float(val)
        self.update()

    pulseOpacity = pyqtProperty(float, get_pulse_opacity, set_pulse_opacity)

    # ── Qt Property: scaleFactor ──────────────────────────────────────────────

    def get_scale_factor(self) -> float:
        return self._scale_factor

    def set_scale_factor(self, val: float):
        self._scale_factor = float(val)
        self.update()

    scaleFactor = pyqtProperty(float, get_scale_factor, set_scale_factor)

    # ── QGraphicsItem Overrides ───────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        r = self._glow_radius * 1.5
        return QRectF(-r, -r, r * 2, r * 2)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        alpha_mult = self._pulse_opacity
        glow_r = self._glow_radius * self._scale_factor
        core_r = self._core_radius * self._scale_factor

        # 1. Outer diffuse radial glow
        grad = QRadialGradient(0, 0, glow_r)
        c_core = QColor(self._core_color)
        c_core.setAlpha(int(255 * alpha_mult))
        
        c_halo = QColor(self._halo_color)
        c_halo.setAlpha(int(160 * alpha_mult))
        
        c_glow = QColor(self._glow_color)
        c_glow.setAlpha(0)

        grad.setColorAt(0.0, c_core)
        grad.setColorAt(0.35, c_halo)
        grad.setColorAt(0.7, QColor(self._halo_color.red(), self._halo_color.green(), self._halo_color.blue(), int(60 * alpha_mult)))
        grad.setColorAt(1.0, c_glow)

        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(0, 0), glow_r, glow_r)

        # 2. Concentrated high-intensity center core
        core_grad = QRadialGradient(0, 0, core_r)
        c_white = QColor(255, 255, 255, int(240 * alpha_mult))
        core_grad.setColorAt(0.0, c_white)
        core_grad.setColorAt(0.5, c_core)
        core_grad.setColorAt(1.0, c_halo)

        painter.setBrush(QBrush(core_grad))
        painter.drawEllipse(QPointF(0, 0), core_r, core_r)

    # ── Movement & Behavior ───────────────────────────────────────────────────

    def move_to(self, target_pos: QPointF, duration_ms: int = 750):
        """
        Moves the laser pointer smoothly from its current position to target_pos.
        Uses a Bézier-style ease curve and dynamic scale pulse.
        """
        self.stop_breathing()

        if self._group and self._group.state() == QParallelAnimationGroup.State.Running:
            self._group.stop()

        start_pos = self.pos()
        self._move_anim = QPropertyAnimation(self, b"pos")
        self._move_anim.setDuration(duration_ms)
        self._move_anim.setStartValue(start_pos)
        self._move_anim.setEndValue(target_pos)
        self._move_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # Slight scale pulse during transit
        scale_anim = QPropertyAnimation(self, b"scaleFactor")
        scale_anim.setDuration(duration_ms)
        scale_anim.setKeyValueAt(0.0, 1.0)
        scale_anim.setKeyValueAt(0.5, 1.35)
        scale_anim.setKeyValueAt(1.0, 1.0)
        scale_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self._group = QParallelAnimationGroup()
        self._group.addAnimation(self._move_anim)
        self._group.addAnimation(scale_anim)

        def _on_finish():
            self.start_breathing()
            self.arrived.emit(target_pos)

        self._group.finished.connect(_on_finish)
        self._group.start()

    def start_breathing(self):
        """Initiates the idle pulsing/breathing opacity effect."""
        if self._pulse_anim.state() != QPropertyAnimation.State.Running:
            self._pulse_anim.start()

    def stop_breathing(self):
        """Stops the breathing pulse and resets opacity."""
        if self._pulse_anim.state() == QPropertyAnimation.State.Running:
            self._pulse_anim.stop()
        self.set_pulse_opacity(1.0)

    def set_pointer_colors(self, core_color: QColor, halo_color: QColor):
        """Allows switching pointer palette (e.g. amber vs ruby)."""
        self._core_color = core_color
        self._halo_color = halo_color
        self.update()
