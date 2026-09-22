"""
Interactive Math Calculator Canvas Widget
Floating interactive calculator with live expression evaluation and styled keypads.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLineEdit, QPushButton
)
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtCore import Qt
from ...theme_manager import ThemeManager
from ...kestrel_theme import MONO_FONT


class InteractiveCalculatorWidget(QWidget):
    """
    In-canvas interactive mathematical calculator.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(240)
        self._init_ui()

    def _init_ui(self):
        c = ThemeManager.instance().get_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # LCD Display
        self.display = QLineEdit(self)
        self.display.setReadOnly(True)
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.display.setText("0")
        self.display.setFixedHeight(46)
        self.display.setStyleSheet(f"""
            QLineEdit {{
                background-color: {c['panel_card_bg']};
                border: 1px solid {c['border_color']};
                border-radius: 8px;
                color: {c['text_primary']};
                font-family: {MONO_FONT};
                font-size: 20px;
                font-weight: 700;
                padding: 4px 10px;
            }}
        """)
        layout.addWidget(self.display)

        # Keypad Grid
        grid = QGridLayout()
        grid.setSpacing(5)

        buttons = [
            ("C", 0, 0, "#ef4444"), ("(", 0, 1, None), (")", 0, 2, None), ("÷", 0, 3, "#8b5cf6"),
            ("7", 1, 0, None), ("8", 1, 1, None), ("9", 1, 2, None), ("×", 1, 3, "#8b5cf6"),
            ("4", 2, 0, None), ("5", 2, 1, None), ("6", 2, 2, None), ("-", 2, 3, "#8b5cf6"),
            ("1", 3, 0, None), ("2", 3, 1, None), ("3", 3, 2, None), ("+", 3, 3, "#8b5cf6"),
            ("0", 4, 0, None), (".", 4, 1, None), ("⌫", 4, 2, None), ("=", 4, 3, "#10b981")
        ]

        for text, row, col, color in buttons:
            btn = QPushButton(text, self)
            btn.setFixedSize(48, 36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            if color:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {color};
                        color: #ffffff;
                        border: none;
                        border-radius: 6px;
                        font-size: 14px;
                        font-weight: 700;
                        font-family: {MONO_FONT};
                    }}
                    QPushButton:hover {{ opacity: 0.9; }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {c['panel_card_bg']};
                        color: {c['text_primary']};
                        border: 1px solid {c['border_color']};
                        border-radius: 6px;
                        font-size: 14px;
                        font-weight: 600;
                        font-family: {MONO_FONT};
                    }}
                    QPushButton:hover {{ background-color: rgba(139, 92, 246, 0.15); border-color: #8b5cf6; }}
                """)

            btn.clicked.connect(lambda _, t=text: self._on_btn_clicked(t))
            grid.addWidget(btn, row, col)

        layout.addLayout(grid)

    def _on_btn_clicked(self, text: str):
        curr = self.display.text()
        if text == "C":
            self.display.setText("0")
        elif text == "⌫":
            if len(curr) > 1 and curr != "Error":
                self.display.setText(curr[:-1])
            else:
                self.display.setText("0")
        elif text == "=":
            self._evaluate()
        else:
            if curr == "0" and text not in ["+", "-", "×", "÷", "."]:
                self.display.setText(text)
            elif curr == "Error":
                self.display.setText(text)
            else:
                self.display.setText(curr + text)

    def _evaluate(self):
        expr = self.display.text().replace("×", "*").replace("÷", "/")
        try:
            # Safe math evaluation
            allowed = {"__builtins__": None}
            res = eval(expr, allowed, {})
            if isinstance(res, float):
                # Clean up .0
                res = f"{res:.6g}"
            self.display.setText(str(res))
        except Exception:
            self.display.setText("Error")

    def keyPressEvent(self, event: QKeyEvent):
        key = event.text()
        if key in "0123456789+-*/.()":
            t = key.replace("*", "×").replace("/", "÷")
            self._on_btn_clicked(t)
        elif event.key() in [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Equal]:
            self._evaluate()
        elif event.key() == Qt.Key.Key_Backspace:
            self._on_btn_clicked("⌫")
        elif event.key() == Qt.Key.Key_Escape:
            self._on_btn_clicked("C")
        else:
            super().keyPressEvent(event)
