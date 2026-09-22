"""
Interactive Bouncing Balls & Physics Sandbox Canvas Widget
Real-time particle simulation with gravity, velocity, collision elasticity, and click-to-spawn.
"""

import random
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider
from PyQt6.QtGui import QPainter, QColor, QMouseEvent
from PyQt6.QtCore import Qt, QTimer, QPointF
from ...theme_manager import ThemeManager
from ...kestrel_theme import MONO_FONT


class PhysicsSimWidget(QWidget):
    """
    Interactive 2D physics gravity sandbox widget.
    """

    WIDTH = 280
    HEIGHT = 280

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.WIDTH, self.HEIGHT)

        self.gravity = 0.35
        self.elasticity = 0.82

        # Particle list: [ {"x": f, "y": f, "vx": f, "vy": f, "r": f, "color": QColor} ]
        self.particles = []
        self._init_particles()

        self.timer = QTimer(self)
        self.timer.setInterval(16) # ~60fps
        self.timer.timeout.connect(self._physics_step)
        self.timer.start()

    def _init_particles(self):
        colors = ["#8b5cf6", "#ec4899", "#3b82f6", "#10b981", "#f59e0b", "#06b6d4"]
        for _ in range(6):
            self.particles.append({
                "x": random.uniform(30, self.WIDTH - 30),
                "y": random.uniform(20, 100),
                "vx": random.uniform(-3, 3),
                "vy": random.uniform(0, 2),
                "r": random.uniform(10, 16),
                "color": QColor(random.choice(colors))
            })

    def mousePressEvent(self, event: QMouseEvent):
        # Spawn a new particle where clicked
        colors = ["#8b5cf6", "#ec4899", "#3b82f6", "#10b981", "#f59e0b", "#06b6d4"]
        self.particles.append({
            "x": float(event.position().x()),
            "y": float(event.position().y()),
            "vx": random.uniform(-4, 4),
            "vy": random.uniform(-5, -1),
            "r": random.uniform(10, 15),
            "color": QColor(random.choice(colors))
        })
        if len(self.particles) > 25:
            self.particles.pop(0)
        event.accept()

    def _physics_step(self):
        for p in self.particles:
            p["vy"] += self.gravity
            p["x"] += p["vx"]
            p["y"] += p["vy"]

            # Floor
            if p["y"] + p["r"] >= self.HEIGHT:
                p["y"] = self.HEIGHT - p["r"]
                p["vy"] = -p["vy"] * self.elasticity
                p["vx"] *= 0.98

            # Ceiling
            if p["y"] - p["r"] <= 0:
                p["y"] = p["r"]
                p["vy"] = -p["vy"] * self.elasticity

            # Walls
            if p["x"] + p["r"] >= self.WIDTH:
                p["x"] = self.WIDTH - p["r"]
                p["vx"] = -p["vx"] * self.elasticity
            elif p["x"] - p["r"] <= 0:
                p["x"] = p["r"]
                p["vx"] = -p["vx"] * self.elasticity

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(0, 0, self.WIDTH, self.HEIGHT, QColor("#090d16"))

        # Instruction hint
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        painter.setPen(QColor(255, 255, 255, 70))
        painter.drawText(10, 20, "Click anywhere to spawn ball")

        # Draw particles
        for p in self.particles:
            painter.setBrush(p["color"])
            painter.setPen(QColor(255, 255, 255, 180))
            painter.drawEllipse(QPointF(p["x"], p["y"]), p["r"], p["r"])
