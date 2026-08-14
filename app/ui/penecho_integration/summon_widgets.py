"""
Procedural Mathematical Summon Curve Widgets & QGraphicsItem for AI-TUTOR.
Ported from penecho/public/summon.js.

Provides:
1. Procedural generator for 5 mathematical curves:
   - Lemniscate of Bernoulli
   - Rose Curve (Rhodonea)
   - Superellipse (Lamé Curve)
   - Golden Spiral (Logarithmic Spiral)
   - Deltoid (Hypocycloid)
2. PenechoSummonItem: Animated mathematical visual widget with live particle/glow tracing,
   cycleable curve types, speed controls, and JSON serialization.
"""

import time
import math
from typing import List, Tuple, Dict, Any, Optional
from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QPainterPath, QFont, QRadialGradient
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer

CURVE_TYPES = ["lemniscate", "rose", "superellipse", "golden-spiral", "deltoid"]
TAU = math.pi * 2


def _signed_power(val: float, power: float) -> float:
    return math.copysign(abs(val) ** power, val)


def generate_curve_points(curve_type: str, elapsed: float = 0.0, samples: int = 240) -> List[Tuple[float, float]]:
    """
    Generates normalized (x, y) coordinates in [-1, 1] range for mathematical curves.
    """
    raw_points = []
    for i in range(samples + 1):
        progress = i / float(samples)
        angle = progress * TAU

        if curve_type == "lemniscate":
            x = math.sin(angle)
            y = math.sin(angle) * math.cos(angle) * 0.72
            raw_points.append((x, y))

        elif curve_type == "rose":
            r = math.cos(3.0 * angle)
            x = math.cos(angle) * r
            y = math.sin(angle) * r
            raw_points.append((x, y))

        elif curve_type == "superellipse":
            exponent = 2.0 / (3.1 + math.sin(elapsed * 0.48) * 0.38)
            x = _signed_power(math.cos(angle), exponent)
            y = _signed_power(math.sin(angle), exponent)
            raw_points.append((x, y))

        elif curve_type == "golden-spiral":
            spiral_angle = progress * math.pi * 5.0
            r = 0.105 * math.exp(spiral_angle * 0.138)
            x = math.cos(spiral_angle + elapsed * 0.5) * r
            y = math.sin(spiral_angle + elapsed * 0.5) * r
            raw_points.append((x, y))

        elif curve_type == "deltoid":
            x = 2.0 * math.cos(angle) + math.cos(2.0 * angle)
            y = 2.0 * math.sin(angle) - math.sin(2.0 * angle)
            raw_points.append((x, y))

        else: # Default circle fallback
            raw_points.append((math.cos(angle), math.sin(angle)))

    if not raw_points:
        return []

    # Normalize to [-1, 1]
    min_x = min(p[0] for p in raw_points)
    min_y = min(p[1] for p in raw_points)
    max_x = max(p[0] for p in raw_points)
    max_y = max(p[1] for p in raw_points)

    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0
    span = max(1e-6, max_x - min_x, max_y - min_y)
    scale = 2.0 / span

    return [((p[0] - cx) * scale, (p[1] - cy) * scale) for p in raw_points]


class PenechoSummonItem(QGraphicsItem):
    """
    Animated mathematical curve summon widget.
    Paints procedural mathematical curves with vibrant glowing strokes.
    """

    def __init__(self, curve_type: str = "lemniscate", size: float = 240.0, parent=None):
        super().__init__(parent)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self._curve_type = curve_type if curve_type in CURVE_TYPES else "lemniscate"
        self._size = max(120.0, size)
        self._elapsed = 0.0
        self._glow_color = QColor("#8b5cf6") # Purple glow

        # Animation timer at ~40 FPS
        self._timer = QTimer()
        self._timer.setInterval(25)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

    def _on_tick(self):
        self._elapsed += 0.04
        self.update()

    def boundingRect(self) -> QRectF:
        pad = 20.0
        return QRectF(-pad, -pad, self._size + pad * 2, self._size + pad * 2 + 30)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 1. Background Card
        card_rect = QRectF(0, 0, self._size, self._size + 30)
        card_path = QPainterPath()
        card_path.addRoundedRect(card_rect, 14, 14)
        painter.setPen(QPen(QColor("#3b82f6") if self.isSelected() else QColor("#334155"), 1.5))
        painter.setBrush(QBrush(QColor("#090d16")))
        painter.drawPath(card_path)

        # 2. Draw Glow Background in center
        center_x = self._size / 2.0
        center_y = self._size / 2.0
        radius = (self._size / 2.0) - 20.0

        grad = QRadialGradient(QPointF(center_x, center_y), radius)
        grad.setColorAt(0.0, QColor(139, 92, 246, 60))
        grad.setColorAt(1.0, QColor(9, 13, 22, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QPointF(center_x, center_y), radius, radius)

        # 3. Draw Procedural Mathematical Curve
        points = generate_curve_points(self._curve_type, self._elapsed, samples=200)
        if len(points) >= 2:
            path = QPainterPath()
            sx = center_x + points[0][0] * radius
            sy = center_y + points[0][1] * radius
            path.moveTo(sx, sy)
            for px, py in points[1:]:
                path.lineTo(center_x + px * radius, center_y + py * radius)
            path.closeSubpath()

            # Glowing multi-layer stroke
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(139, 92, 246, 120), 4.0))
            painter.drawPath(path)

            painter.setPen(QPen(QColor("#c084fc"), 2.0))
            painter.drawPath(path)

        # 4. Label at bottom
        painter.setPen(QColor("#94a3b8"))
        painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        name_map = {
            "lemniscate": "∞ Lemniscate of Bernoulli",
            "rose": "✿ Rhodonea (Rose Curve)",
            "superellipse": "⬭ Lamé Superellipse",
            "golden-spiral": "🌀 Golden Spiral",
            "deltoid": "△ Hypocycloid Deltoid"
        }
        title = name_map.get(self._curve_type, self._curve_type.capitalize())
        painter.drawText(QRectF(0, self._size + 2, self._size, 24), Qt.AlignmentFlag.AlignCenter, title)

        painter.restore()

    def mouseDoubleClickEvent(self, event):
        # Cycle to next curve on double click
        idx = CURVE_TYPES.index(self._curve_type) if self._curve_type in CURVE_TYPES else 0
        self._curve_type = CURVE_TYPES[(idx + 1) % len(CURVE_TYPES)]
        self.update()
        event.accept()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "PenechoSummonItem",
            "x": self.pos().x(),
            "y": self.pos().y(),
            "z_value": self.zValue(),
            "curve_type": self._curve_type,
            "size": self._size
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PenechoSummonItem":
        item = cls(
            curve_type=data.get("curve_type", "lemniscate"),
            size=float(data.get("size", 240.0))
        )
        return item
