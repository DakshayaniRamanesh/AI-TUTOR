"""
Interactive Playable Snake Game Canvas Widget
Real-time 60fps classic Snake game with keyboard controls, food spawning, score, and restart.
"""

import random
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QFont, QKeyEvent, QMouseEvent
from PyQt6.QtCore import Qt, QTimer, QRectF
from ...kestrel_theme import MONO_FONT


class SnakeGameWidget(QWidget):
    """
    Playable Snake arcade game widget.
    """

    GRID_SIZE = 15
    CELL_SIZE = 18
    WIDTH = GRID_SIZE * CELL_SIZE  # 270
    HEIGHT = GRID_SIZE * CELL_SIZE # 270

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.state = "READY" # "READY", "PLAYING", "GAME_OVER"
        self.score = 0
        self.high_score = 0

        self.snake = [(7, 7), (7, 8), (7, 9)]
        self.direction = (0, -1) # Up
        self.next_direction = (0, -1)
        self.food = (3, 3)

        self.timer = QTimer(self)
        self.timer.setInterval(120) # Snake speed
        self.timer.timeout.connect(self._game_tick)

    def reset_game(self):
        self.snake = [(7, 7), (7, 8), (7, 9)]
        self.direction = (0, -1)
        self.next_direction = (0, -1)
        self.score = 0
        self.state = "READY"
        self._spawn_food()
        self.update()

    def _spawn_food(self):
        empty_cells = [
            (x, y) for x in range(self.GRID_SIZE) for y in range(self.GRID_SIZE)
            if (x, y) not in self.snake
        ]
        if empty_cells:
            self.food = random.choice(empty_cells)

    def mousePressEvent(self, event: QMouseEvent):
        self.setFocus()
        if self.state == "READY":
            self.state = "PLAYING"
            self.timer.start()
        elif self.state == "GAME_OVER":
            self.reset_game()
        event.accept()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if self.state == "READY":
            self.state = "PLAYING"
            self.timer.start()

        if self.state == "GAME_OVER":
            if key in [Qt.Key.Key_Space, Qt.Key.Key_Return]:
                self.reset_game()
            return

        if key in [Qt.Key.Key_Up, Qt.Key.Key_W] and self.direction != (0, 1):
            self.next_direction = (0, -1)
        elif key in [Qt.Key.Key_Down, Qt.Key.Key_S] and self.direction != (0, -1):
            self.next_direction = (0, 1)
        elif key in [Qt.Key.Key_Left, Qt.Key.Key_A] and self.direction != (1, 0):
            self.next_direction = (-1, 0)
        elif key in [Qt.Key.Key_Right, Qt.Key.Key_D] and self.direction != (-1, 0):
            self.next_direction = (1, 0)
        else:
            super().keyPressEvent(event)

    def _game_tick(self):
        if self.state != "PLAYING":
            return

        self.direction = self.next_direction
        head_x, head_y = self.snake[0]
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)

        # Wall collisions
        if not (0 <= new_head[0] < self.GRID_SIZE and 0 <= new_head[1] < self.GRID_SIZE):
            self._trigger_game_over()
            return

        # Self collision
        if new_head in self.snake:
            self._trigger_game_over()
            return

        self.snake.insert(0, new_head)

        # Food check
        if new_head == self.food:
            self.score += 10
            if self.score > self.high_score:
                self.high_score = self.score
            self._spawn_food()
        else:
            self.snake.pop()

        self.update()

    def _trigger_game_over(self):
        self.timer.stop()
        self.state = "GAME_OVER"
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Background Grid
        painter.fillRect(0, 0, self.WIDTH, self.HEIGHT, QColor("#0f172a"))

        # Subtle grid lines
        painter.setPen(QColor(255, 255, 255, 10))
        for x in range(0, self.WIDTH, self.CELL_SIZE):
            painter.drawLine(x, 0, x, self.HEIGHT)
        for y in range(0, self.HEIGHT, self.CELL_SIZE):
            painter.drawLine(0, y, self.WIDTH, y)

        # 2. Draw Food (Glowing Apple / Orb)
        fx, fy = self.food
        food_rect = QRectF(fx * self.CELL_SIZE + 2, fy * self.CELL_SIZE + 2, self.CELL_SIZE - 4, self.CELL_SIZE - 4)
        painter.setBrush(QColor("#ef4444"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(food_rect, 6, 6)

        # 3. Draw Snake
        for i, (sx, sy) in enumerate(self.snake):
            seg_rect = QRectF(sx * self.CELL_SIZE + 1, sy * self.CELL_SIZE + 1, self.CELL_SIZE - 2, self.CELL_SIZE - 2)
            if i == 0:
                # Head
                painter.setBrush(QColor("#8b5cf6"))
                painter.drawRoundedRect(seg_rect, 5, 5)
            else:
                # Body gradient
                painter.setBrush(QColor("#a78bfa"))
                painter.drawRoundedRect(seg_rect, 4, 4)

        # 4. Overlays
        if self.state == "READY":
            painter.setBrush(QColor(0, 0, 0, 160))
            painter.drawRect(0, 0, self.WIDTH, self.HEIGHT)
            painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRectF(0, 80, self.WIDTH, 30), Qt.AlignmentFlag.AlignCenter, "SNAKE GAME")
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
            painter.setPen(QColor("#a78bfa"))
            painter.drawText(QRectF(0, 115, self.WIDTH, 25), Qt.AlignmentFlag.AlignCenter, "Click or Arrow Keys to Start")

        elif self.state == "PLAYING":
            painter.setFont(QFont(MONO_FONT, 10, QFont.Weight.Bold))
            painter.setPen(QColor(255, 255, 255, 200))
            painter.drawText(8, 16, f"Score: {self.score}")

        elif self.state == "GAME_OVER":
            painter.setBrush(QColor(0, 0, 0, 185))
            painter.drawRect(0, 0, self.WIDTH, self.HEIGHT)
            painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            painter.setPen(QColor("#ef4444"))
            painter.drawText(QRectF(0, 75, self.WIDTH, 28), Qt.AlignmentFlag.AlignCenter, "GAME OVER")

            painter.setFont(QFont(MONO_FONT, 11, QFont.Weight.Bold))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(QRectF(0, 110, self.WIDTH, 22), Qt.AlignmentFlag.AlignCenter, f"Score: {self.score} | Best: {self.high_score}")

            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
            painter.setPen(QColor("#10b981"))
            painter.drawText(QRectF(0, 150, self.WIDTH, 22), Qt.AlignmentFlag.AlignCenter, "Click to Play Again")

    def get_state(self) -> dict:
        return {"high_score": self.high_score}
