"""
Procedural Simulation Interactive Widget (Physics, Math Curves, Oscillations)
Clean, professional light theme matching Kestrel design system and academic workstations.
No emojis or neon styling — uses crisp typography, Remix icons, and high-contrast palettes.
"""

import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QFrame
)
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush
import qtawesome as qta

from ...kestrel_theme import MONO_FONT


class ProceduralSimulationWidget(QWidget):
    """
    In-Canvas procedural visual simulation with live physics animations.
    Light theme, academic aesthetic, Remix icons.
    """

    def __init__(self, sim_type: str = "orbit", parent=None):
        super().__init__(parent)
        self.sim_type = sim_type
        self.setFixedSize(300, 260)
        self.setStyleSheet("background-color: #ffffff;")

        self.elapsed = 0.0
        self.speed = 1.0
        self.is_paused = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Top Control Row
        top_row = QHBoxLayout()
        titles = {
            "orbit": ("Planetary Orbit Simulator", "ri.earth-line"),
            "pendulum": ("Harmonic Pendulum", "ri.timer-line"),
            "wave": ("Wave Propagation", "ri.pulse-line"),
            "curve": ("Lemniscate Math Curve", "ri.function-line")
        }
        title_text, icon_name = titles.get(sim_type, ("Physics Simulation", "ri.flask-line"))

        icon_lbl = QLabel(self)
        try:
            icon_pixmap = qta.icon(icon_name, color="#0f172a").pixmap(14, 14)
        except Exception:
            icon_pixmap = qta.icon("ri.flask-line", color="#0f172a").pixmap(14, 14)
        icon_lbl.setPixmap(icon_pixmap)
        top_row.addWidget(icon_lbl)

        self.title_lbl = QLabel(title_text, self)
        self.title_lbl.setStyleSheet(f"font-weight: 700; font-size: 11px; color: #0f172a; font-family: {MONO_FONT};")
        top_row.addWidget(self.title_lbl)
        top_row.addStretch(1)

        self.btn_pause = QPushButton(self)
        self.btn_pause.setFixedSize(26, 22)
        self.btn_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pause.setIcon(qta.icon("ri.pause-line", color="#334155"))
        self.btn_pause.setStyleSheet("""
            QPushButton {
                background: #f1f5f9;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
            }
            QPushButton:hover { background: #e2e8f0; }
        """)
        self.btn_pause.clicked.connect(self._toggle_pause)
        top_row.addWidget(self.btn_pause)
        layout.addLayout(top_row)

        # Simulation Canvas Area placeholder
        self.canvas_area = QWidget(self)
        self.canvas_area.setFixedSize(280, 180)
        layout.addWidget(self.canvas_area)

        # Bottom Slider Controls
        bot_row = QHBoxLayout()
        lbl_speed = QLabel("Speed:", self)
        lbl_speed.setStyleSheet(f"font-size: 10px; color: #64748b; font-family: {MONO_FONT}; font-weight: 600;")
        bot_row.addWidget(lbl_speed)

        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(5, 25)
        self.slider.setValue(10)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 4px; background: #e2e8f0; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #2563eb; border-radius: 2px; }
            QSlider::handle:horizontal { background: #ffffff; border: 2px solid #2563eb; width: 12px; margin: -4px 0; border-radius: 6px; }
        """)
        self.slider.valueChanged.connect(lambda v: setattr(self, "speed", v / 10.0))
        bot_row.addWidget(self.slider)
        layout.addLayout(bot_row)

        # Animation timer (~60 fps)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._step)
        self.timer.start(16)

    def _toggle_pause(self):
        self.is_paused = not self.is_paused
        icon_name = "ri.play-line" if self.is_paused else "ri.pause-line"
        self.btn_pause.setIcon(qta.icon(icon_name, color="#334155"))

    def _step(self):
        if not self.is_paused:
            self.elapsed += 0.025 * self.speed
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background Box (Pure White with Crisp Border)
        painter.setBrush(QColor("#f8fafc"))
        painter.setPen(QPen(QColor("#e2e8f0"), 1.0))
        painter.drawRoundedRect(QRectF(10, 36, 280, 180), 6, 6)

        cx = 150.0
        cy = 126.0

        if self.sim_type == "pendulum":
            length = 95.0
            max_angle = 0.65
            angle = max_angle * math.sin(self.elapsed * 2.8)
            bob_x = cx + length * math.sin(angle)
            bob_y = 52.0 + length * math.cos(angle)

            # Pivot
            painter.setBrush(QColor("#64748b"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(cx - 5, 47, 10, 10))

            # Rod
            painter.setPen(QPen(QColor("#94a3b8"), 2.0))
            painter.drawLine(QPointF(cx, 52), QPointF(bob_x, bob_y))

            # Bob
            painter.setBrush(QColor("#dc2626"))
            painter.setPen(QPen(QColor("#991b1b"), 1.5))
            painter.drawEllipse(QRectF(bob_x - 14, bob_y - 14, 28, 28))

            # Formula
            painter.setFont(QFont(MONO_FONT, 8, QFont.Weight.Bold))
            painter.setPen(QColor("#0f172a"))
            painter.drawText(20, 204, "T = 2π√(L/g)  |  θ(t) = θ₀ cos(ωt)")

        elif self.sim_type == "wave":
            nodes = 7
            spacing = 240.0 / (nodes - 1)
            start_x = 30.0
            amplitude = 35.0

            painter.setPen(QPen(QColor("#94a3b8"), 1.0, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(start_x, cy), QPointF(start_x + 240, cy))

            colors = ["#2563eb", "#7c3aed", "#db2777", "#059669", "#d97706", "#0891b2", "#4f46e5"]
            for i in range(nodes):
                x = start_x + i * spacing
                phase = i * 0.75 - self.elapsed * 3.2
                y = cy + amplitude * math.sin(phase)

                painter.setBrush(QColor(colors[i % len(colors)]))
                painter.setPen(QPen(QColor("#ffffff"), 1.5))
                painter.drawEllipse(QRectF(x - 9, y - 9, 18, 18))

            # Formula
            painter.setFont(QFont(MONO_FONT, 8, QFont.Weight.Bold))
            painter.setPen(QColor("#0f172a"))
            painter.drawText(20, 204, "y(x,t) = A sin(kx - ωt)  |  λ = 2π/k")

        elif self.sim_type == "curve":
            a = 75.0
            t = self.elapsed * 1.5
            trace_x = cx + (a * math.cos(t)) / (1 + (math.sin(t) ** 2))
            trace_y = cy + (a * math.sin(t) * math.cos(t)) / (1 + (math.sin(t) ** 2))

            # Draw complete lemniscate curve
            painter.setPen(QPen(QColor("#cbd5e1"), 1.5))
            prev_pt = None
            for step in range(120):
                th = step * (math.pi * 2 / 120.0)
                px = cx + (a * math.cos(th)) / (1 + (math.sin(th) ** 2))
                py = cy + (a * math.sin(th) * math.cos(th)) / (1 + (math.sin(th) ** 2))
                if prev_pt:
                    painter.drawLine(prev_pt, QPointF(px, py))
                prev_pt = QPointF(px, py)

            # Draw moving particle
            painter.setBrush(QColor("#2563eb"))
            painter.setPen(QPen(QColor("#1d4ed8"), 1.5))
            painter.drawEllipse(QRectF(trace_x - 7, trace_y - 7, 14, 14))

            # Formula
            painter.setFont(QFont(MONO_FONT, 8, QFont.Weight.Bold))
            painter.setPen(QColor("#0f172a"))
            painter.drawText(20, 204, "(x² + y²)² = 2a²(x² - y²)")

        else: # "orbit"
            # Sun
            painter.setBrush(QColor("#f59e0b"))
            painter.setPen(QPen(QColor("#d97706"), 1.5))
            painter.drawEllipse(QRectF(cx - 16, cy - 16, 32, 32))

            # Orbit Path
            rx, ry = 95.0, 52.0
            painter.setPen(QPen(QColor("#cbd5e1"), 1.2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(cx - rx, cy - ry, rx * 2, ry * 2))

            # Planet
            px = cx + rx * math.cos(self.elapsed * 1.8)
            py = cy + ry * math.sin(self.elapsed * 1.8)
            painter.setBrush(QColor("#2563eb"))
            painter.setPen(QPen(QColor("#1d4ed8"), 1.5))
            painter.drawEllipse(QRectF(px - 8, py - 8, 16, 16))

            # Formula
            painter.setFont(QFont(MONO_FONT, 8, QFont.Weight.Bold))
            painter.setPen(QColor("#0f172a"))
            painter.drawText(20, 204, "F = G(m₁m₂)/r²  |  T² ∝ r³")

    def get_state(self) -> dict:
        return {
            "sim_type": self.sim_type,
            "speed": self.speed,
            "is_paused": self.is_paused
        }
