"""
Interactive Dice Roller & Coin Flipper Canvas Widget
Randomizer tool for probability, games, and quick decisions.
"""

import random
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QStackedWidget
)
from PyQt6.QtGui import QFont, QPainter, QColor, QBrush, QPen
from PyQt6.QtCore import Qt, QTimer, QRectF
from ...theme_manager import ThemeManager
from ...kestrel_theme import MONO_FONT


class InteractiveDiceCoinWidget(QWidget):
    """
    In-canvas interactive dice roller and coin flipper.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(240)
        self.mode = "dice" # "dice" or "coin"

        self.dice_value = 6
        self.coin_value = "HEADS"
        self.is_animating = False
        self.anim_ticks = 0

        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(60)
        self.anim_timer.timeout.connect(self._on_anim_tick)

        self._init_ui()

    def _init_ui(self):
        c = ThemeManager.instance().get_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(8)

        # Mode toggle
        mode_row = QHBoxLayout()
        self.btn_dice = QPushButton("🎲 Dice", self)
        self.btn_dice.setFixedHeight(24)
        self.btn_dice.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dice.setStyleSheet("background: #8b5cf6; color: #fff; border-radius: 4px; font-weight: 700; font-size: 11px;")
        self.btn_dice.clicked.connect(lambda: self._set_mode("dice"))
        mode_row.addWidget(self.btn_dice)

        self.btn_coin = QPushButton("🪙 Coin", self)
        self.btn_coin.setFixedHeight(24)
        self.btn_coin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_coin.setStyleSheet(f"background: {c['panel_card_bg']}; color: {c['text_secondary']}; border: 1px solid {c['border_color']}; border-radius: 4px; font-size: 11px;")
        self.btn_coin.clicked.connect(lambda: self._set_mode("coin"))
        mode_row.addWidget(self.btn_coin)
        layout.addLayout(mode_row)

        # Big Result Display
        self.lbl_result = QLabel("🎲 6", self)
        self.lbl_result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_result.setFixedHeight(80)
        self.lbl_result.setStyleSheet(f"""
            font-size: 34px;
            font-weight: 800;
            font-family: {MONO_FONT};
            color: #8b5cf6;
            background: {c['panel_card_bg']};
            border: 1px solid {c['border_color']};
            border-radius: 10px;
        """)
        layout.addWidget(self.lbl_result)

        # Roll / Flip Button
        self.btn_action = QPushButton("Roll Dice", self)
        self.btn_action.setFixedHeight(34)
        self.btn_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_action.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #6366f1);
                color: #ffffff;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover { opacity: 0.9; }
        """)
        self.btn_action.clicked.connect(self._trigger_roll)
        layout.addWidget(self.btn_action)

    def _set_mode(self, mode: str):
        self.mode = mode
        c = ThemeManager.instance().get_colors()
        if mode == "dice":
            self.btn_dice.setStyleSheet("background: #8b5cf6; color: #fff; border-radius: 4px; font-weight: 700; font-size: 11px;")
            self.btn_coin.setStyleSheet(f"background: {c['panel_card_bg']}; color: {c['text_secondary']}; border: 1px solid {c['border_color']}; border-radius: 4px; font-size: 11px;")
            self.lbl_result.setText(f"🎲 {self.dice_value}")
            self.btn_action.setText("Roll Dice")
        else:
            self.btn_coin.setStyleSheet("background: #f59e0b; color: #fff; border-radius: 4px; font-weight: 700; font-size: 11px;")
            self.btn_dice.setStyleSheet(f"background: {c['panel_card_bg']}; color: {c['text_secondary']}; border: 1px solid {c['border_color']}; border-radius: 4px; font-size: 11px;")
            self.lbl_result.setText(f"🪙 {self.coin_value}")
            self.btn_action.setText("Flip Coin")

    def _trigger_roll(self):
        if self.is_animating:
            return
        self.is_animating = True
        self.anim_ticks = 0
        self.btn_action.setEnabled(False)
        self.anim_timer.start()

    def _on_anim_tick(self):
        self.anim_ticks += 1
        if self.mode == "dice":
            rnd = random.randint(1, 6)
            self.lbl_result.setText(f"🎲 {rnd}")
        else:
            rnd = random.choice(["HEADS", "TAILS"])
            self.lbl_result.setText(f"🪙 {rnd}")

        if self.anim_ticks >= 12:
            self.anim_timer.stop()
            self.is_animating = False
            self.btn_action.setEnabled(True)
            if self.mode == "dice":
                self.dice_value = random.randint(1, 6)
                self.lbl_result.setText(f"🎲 {self.dice_value}")
            else:
                self.coin_value = random.choice(["HEADS", "TAILS"])
                self.lbl_result.setText(f"🪙 {self.coin_value}")
