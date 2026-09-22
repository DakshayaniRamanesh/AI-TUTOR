"""
Interactive Playable Flappy Bird Canvas Game Widget
Real-time 60fps arcade Flappy Bird game running natively on the Kestrel canvas.
Supports click and spacebar controls, animated physics, score tracking, and restart.
"""

import random
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QKeyEvent, QMouseEvent
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from ...kestrel_theme import MONO_FONT


class FlappyBirdGameWidget(QWidget):
    """
    Playable mini Flappy Bird arcade game widget.
    """

    WIDTH = 300
    HEIGHT = 360
    GRAVITY = 0.45
    JUMP_FORCE = -7.5
    PIPE_SPEED = 2.8
    PIPE_GAP = 100
    PIPE_FREQUENCY = 75 # frames between pipes

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.state = "READY" # "READY", "PLAYING", "GAME_OVER"
        self.score = 0
        self.high_score = 0

        # Bird state
        self.bird_x = 65
        self.bird_y = self.HEIGHT // 2
        self.bird_velocity = 0
        self.bird_radius = 12

        # Pipes: list of dict {"x": float, "top_h": float, "bottom_y": float, "passed": bool}
        self.pipes = []
        self.frame_count = 0

        # 60 FPS Game Loop Timer
        self.timer = QTimer(self)
        self.timer.setInterval(16) # ~60fps
        self.timer.timeout.connect(self._game_loop)
        self.timer.start()

    def reset_game(self):
        self.state = "READY"
        self.score = 0
        self.bird_x = 65
        self.bird_y = self.HEIGHT // 2
        self.bird_velocity = 0
        self.pipes.clear()
        self.frame_count = 0
        self.update()

    def flap(self):
        if self.state == "READY":
            self.state = "PLAYING"
            self.bird_velocity = self.JUMP_FORCE
        elif self.state == "PLAYING":
            self.bird_velocity = self.JUMP_FORCE
        elif self.state == "GAME_OVER":
            self.reset_game()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self.flap()
            event.accept()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in [Qt.Key.Key_Space, Qt.Key.Key_Up, Qt.Key.Key_W]:
            self.flap()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _game_loop(self):
        if self.state == "PLAYING":
            self._update_physics()
        elif self.state == "READY":
            # Gentle bobbing animation while waiting
            self.frame_count += 1
            import math
            self.bird_y = (self.HEIGHT // 2) + math.sin(self.frame_count * 0.1) * 6

        self.update()

    def _update_physics(self):
        self.frame_count += 1

        # 1. Update bird gravity
        self.bird_velocity += self.GRAVITY
        self.bird_y += self.bird_velocity

        # Ceiling & Ground Collision
        ground_y = self.HEIGHT - 25
        if self.bird_y >= ground_y - self.bird_radius:
            self.bird_y = ground_y - self.bird_radius
            self._trigger_game_over()
            return
        elif self.bird_y <= self.bird_radius:
            self.bird_y = self.bird_radius
            self.bird_velocity = 0

        # 2. Spawn Pipes
        if self.frame_count % self.PIPE_FREQUENCY == 0:
            min_top = 40
            max_top = self.HEIGHT - self.PIPE_GAP - 60
            top_h = random.randint(min_top, max_top)
            bottom_y = top_h + self.PIPE_GAP
            self.pipes.append({
                "x": float(self.WIDTH),
                "top_h": top_h,
                "bottom_y": bottom_y,
                "passed": False
            })

        # 3. Move Pipes & Check Collisions
        pipe_w = 42
        bird_box = QRectF(
            self.bird_x - self.bird_radius + 2,
            self.bird_y - self.bird_radius + 2,
            (self.bird_radius - 2) * 2,
            (self.bird_radius - 2) * 2
        )

        for p in list(self.pipes):
            p["x"] -= self.PIPE_SPEED

            top_rect = QRectF(p["x"], 0, pipe_w, p["top_h"])
            bottom_rect = QRectF(p["x"], p["bottom_y"], pipe_w, self.HEIGHT - p["bottom_y"] - 25)

            # Collision test
            if bird_box.intersects(top_rect) or bird_box.intersects(bottom_rect):
                self._trigger_game_over()
                return

            # Score increment
            if not p["passed"] and p["x"] + pipe_w < self.bird_x:
                p["passed"] = True
                self.score += 1
                if self.score > self.high_score:
                    self.high_score = self.score

        # Remove off-screen pipes
        self.pipes = [p for p in self.pipes if p["x"] + pipe_w > -10]

    def _trigger_game_over(self):
        self.state = "GAME_OVER"
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Sky Background
        painter.fillRect(0, 0, self.WIDTH, self.HEIGHT, QColor("#70c5ce"))

        # Clouds
        painter.setBrush(QColor(255, 255, 255, 140))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(30, 60, 65, 25)
        painter.drawEllipse(180, 40, 80, 30)

        # 2. Draw Pipes
        pipe_w = 42
        pipe_border = QColor("#2e7d32")
        pipe_fill = QColor("#4caf50")
        painter.setBrush(pipe_fill)
        painter.setPen(QPen(pipe_border, 2))

        for p in self.pipes:
            # Top Pipe
            painter.drawRect(int(p["x"]), 0, pipe_w, int(p["top_h"]))
            # Top Pipe Cap
            painter.drawRect(int(p["x"] - 2), int(p["top_h"] - 14), pipe_w + 4, 14)

            # Bottom Pipe
            b_h = int(self.HEIGHT - p["bottom_y"] - 25)
            painter.drawRect(int(p["x"]), int(p["bottom_y"]), pipe_w, b_h)
            # Bottom Pipe Cap
            painter.drawRect(int(p["x"] - 2), int(p["bottom_y"]), pipe_w + 4, 14)

        # 3. Ground
        ground_y = self.HEIGHT - 25
        painter.fillRect(0, ground_y, self.WIDTH, 25, QColor("#ded895"))
        painter.fillRect(0, ground_y, self.WIDTH, 4, QColor("#5ee270"))

        # 4. Draw Flappy Bird
        painter.save()
        painter.translate(self.bird_x, self.bird_y)
        # Rotation based on velocity
        angle = max(-25.0, min(70.0, self.bird_velocity * 4.5))
        painter.rotate(angle)

        # Body (Yellow)
        painter.setBrush(QColor("#facc15"))
        painter.setPen(QPen(QColor("#b45309"), 1.5))
        painter.drawEllipse(QRectF(-self.bird_radius, -self.bird_radius, self.bird_radius * 2, self.bird_radius * 2))

        # Wing
        painter.setBrush(QColor("#fef08a"))
        painter.drawEllipse(QRectF(-10, -4, 11, 7))

        # Eye
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QRectF(3, -7, 6, 6))
        painter.setBrush(QColor("#000000"))
        painter.drawEllipse(QRectF(5.5, -5.5, 3.0, 3.0))

        # Beak
        painter.setBrush(QColor("#f97316"))
        painter.drawPolygon([QPointF(9, -2), QPointF(16, 2), QPointF(9, 5)])
        painter.restore()

        # 5. UI Overlay
        if self.state == "PLAYING":
            # Live Score
            painter.setFont(QFont(MONO_FONT, 20, QFont.Weight.Bold))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRectF(0, 16, self.WIDTH, 35), Qt.AlignmentFlag.AlignCenter, str(self.score))

        elif self.state == "READY":
            painter.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRectF(0, 80, self.WIDTH, 30), Qt.AlignmentFlag.AlignCenter, "FLAPPY BIRD")

            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
            painter.drawText(QRectF(0, 110, self.WIDTH, 25), Qt.AlignmentFlag.AlignCenter, "Tap or Space to Jump!")

        elif self.state == "GAME_OVER":
            # Dark overlay card
            card_rect = QRectF(30, 75, self.WIDTH - 60, 150)
            painter.setBrush(QColor(0, 0, 0, 185))
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            painter.drawRoundedRect(card_rect, 10, 10)

            painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            painter.setPen(QColor("#ef4444"))
            painter.drawText(QRectF(30, 88, self.WIDTH - 60, 26), Qt.AlignmentFlag.AlignCenter, "GAME OVER")

            painter.setFont(QFont(MONO_FONT, 11, QFont.Weight.Bold))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRectF(30, 120, self.WIDTH - 60, 22), Qt.AlignmentFlag.AlignCenter, f"Score: {self.score}")
            painter.setPen(QColor("#f59e0b"))
            painter.drawText(QRectF(30, 144, self.WIDTH - 60, 22), Qt.AlignmentFlag.AlignCenter, f"Best: {self.high_score}")

            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            painter.setPen(QColor("#10b981"))
            painter.drawText(QRectF(30, 180, self.WIDTH - 60, 22), Qt.AlignmentFlag.AlignCenter, "Tap to Play Again")

    def get_state(self) -> dict:
        return {"high_score": self.high_score}
