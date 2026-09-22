"""
Interactive Tally Counter Canvas Widget
Quick count and tracking widget for repetitions, goals, and scores.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QProgressBar
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from ...theme_manager import ThemeManager
from ...kestrel_theme import MONO_FONT


class InteractiveCounterWidget(QWidget):
    """
    In-canvas interactive tally counter.
    """

    def __init__(self, target_goal: int = 10, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        self.count = 0
        self.goal = target_goal
        self._init_ui()

    def _init_ui(self):
        c = ThemeManager.instance().get_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # Big Number Display
        self.lbl_count = QLabel("0", self)
        self.lbl_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_count.setStyleSheet(f"""
            font-size: 40px;
            font-weight: 800;
            font-family: {MONO_FONT};
            color: #8b5cf6;
        """)
        layout.addWidget(self.lbl_count)

        # Progress bar
        self.progress = QProgressBar(self)
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.setRange(0, self.goal)
        self.progress.setValue(0)
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: rgba(139, 92, 246, 0.2);
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #8b5cf6;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress)

        # Button Controls
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        btn_minus = QPushButton("–1", self)
        btn_minus.setFixedHeight(32)
        btn_minus.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_minus.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['panel_card_bg']};
                border: 1px solid {c['border_color']};
                border-radius: 6px;
                color: {c['text_primary']};
                font-weight: 700;
                font-size: 13px;
            }}
            QPushButton:hover {{ border-color: #ef4444; color: #ef4444; }}
        """)
        btn_minus.clicked.connect(lambda: self._adjust(-1))
        btn_row.addWidget(btn_minus)

        btn_plus = QPushButton("+1", self)
        btn_plus.setFixedHeight(32)
        btn_plus.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_plus.setStyleSheet("""
            QPushButton {
                background-color: #8b5cf6;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-weight: 700;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #7c3aed; }
        """)
        btn_plus.clicked.connect(lambda: self._adjust(1))
        btn_row.addWidget(btn_plus)

        layout.addLayout(btn_row)

        # Reset button
        btn_reset = QPushButton("Reset", self)
        btn_reset.setFixedHeight(22)
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {c['text_secondary']};
                font-size: 10px;
                font-weight: 600;
            }}
            QPushButton:hover {{ color: #ef4444; }}
        """)
        btn_reset.clicked.connect(self._reset)
        layout.addWidget(btn_reset)

    def _adjust(self, delta: int):
        self.count = max(0, self.count + delta)
        self.lbl_count.setText(str(self.count))
        self.progress.setValue(min(self.goal, self.count))

    def _reset(self):
        self.count = 0
        self.lbl_count.setText("0")
        self.progress.setValue(0)
