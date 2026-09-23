"""
SocraticHintBubble — Socratic Tutor Hint Card & Progressive Disclosure Bubble.
Developer 1: Visual and Audio Canvas Studio.

Specifications:
- Anchored adjacent to the active LaserPointerItem.
- Displays the tutor's spoken feedback message.
- Citation pill indicating the grounded course source (e.g., textbook, section, page).
- 'Need a Hint?' progressive disclosure control:
    - Level 1: Nudge
    - Level 2: Relevant Formula
    - Level 3: Solution Step Reveal
- Clean monochrome/academic styling consistent with Kestrel theme system.
"""

from typing import List, Optional, Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGraphicsDropShadowEffect, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import QColor, QFont
import qtawesome as qta

from ..kestrel_theme import MONO_FONT


class SocraticHintBubble(QFrame):
    """
    Floating pedagogical assistance card positioned near the laser pointer.
    """
    closed = pyqtSignal()
    hint_level_changed = pyqtSignal(int)  # 1, 2, or 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SocraticHintBubble")
        self.setFixedWidth(330)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # State
        self._current_level = 0  # 0: no hints shown, 1: nudge, 2: formula, 3: solution
        self._hints: List[str] = [
            "Check the signs when applying the distributive property.",
            "Recall: -(a - b) = -a + b or factor out (-1).",
            "In line 2, -(2x - 5) should become -2x + 5, not -2x - 5."
        ]
        self._citation_text = "Calculus: Early Transcendentals, §3.4, p.142"

        self._init_ui()
        self._apply_style()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # ── Header: Title & Close Button ──
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(6)

        icon_lbl = QLabel(self)
        icon_lbl.setPixmap(qta.icon("ri.magic-line", color="#2563eb").pixmap(14, 14))
        hdr_row.addWidget(icon_lbl)

        title_lbl = QLabel("TUTOR GUIDANCE", self)
        title_lbl.setStyleSheet(f"font-family: {MONO_FONT}; font-size: 11px; font-weight: 800; letter-spacing: 1px; color: #0f172a;")
        hdr_row.addWidget(title_lbl)

        hdr_row.addStretch(1)

        self.btn_close = QPushButton("×", self)
        self.btn_close.setFixedSize(18, 18)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #94a3b8;
                font-size: 14px;
                font-weight: bold;
                line-height: 14px;
            }
            QPushButton:hover { color: #0f172a; }
        """)
        self.btn_close.clicked.connect(self._on_close_clicked)
        hdr_row.addWidget(self.btn_close)
        layout.addLayout(hdr_row)

        # ── Spoken Tutor Message ──
        self.lbl_message = QLabel(self)
        self.lbl_message.setWordWrap(True)
        self.lbl_message.setStyleSheet("font-size: 12px; color: #1e293b; line-height: 1.4; font-weight: 500;")
        self.lbl_message.setText("Take a look at your second step. The signs do not match the previous line.")
        layout.addWidget(self.lbl_message)

        # ── Citation Pill ──
        self.citation_pill = QFrame(self)
        self.citation_pill.setObjectName("citationPill")
        pill_layout = QHBoxLayout(self.citation_pill)
        pill_layout.setContentsMargins(8, 4, 8, 4)
        pill_layout.setSpacing(6)

        pill_icon = QLabel(self.citation_pill)
        pill_icon.setPixmap(qta.icon("ri.book-open-line", color="#64748b").pixmap(11, 11))
        pill_layout.addWidget(pill_icon)

        self.lbl_citation = QLabel(self._citation_text, self.citation_pill)
        self.lbl_citation.setStyleSheet(f"font-family: {MONO_FONT}; font-size: 10px; color: #475569; font-weight: 600;")
        self.lbl_citation.setWordWrap(True)
        pill_layout.addWidget(self.lbl_citation)
        pill_layout.addStretch(1)
        layout.addWidget(self.citation_pill)

        # ── Progressive Hint Container ──
        self.hint_box = QFrame(self)
        self.hint_box.setObjectName("hintBox")
        self.hint_layout = QVBoxLayout(self.hint_box)
        self.hint_layout.setContentsMargins(10, 8, 10, 8)
        self.hint_layout.setSpacing(6)

        self.lbl_hint_badge = QLabel("HINT LEVEL 1 (NUDGE)", self.hint_box)
        self.lbl_hint_badge.setStyleSheet(f"font-family: {MONO_FONT}; font-size: 9px; font-weight: 800; color: #2563eb; letter-spacing: 0.5px;")
        self.hint_layout.addWidget(self.lbl_hint_badge)

        self.lbl_hint_text = QLabel(self.hint_box)
        self.lbl_hint_text.setWordWrap(True)
        self.lbl_hint_text.setStyleSheet("font-size: 11px; color: #334155; line-height: 1.3;")
        self.hint_layout.addWidget(self.lbl_hint_text)
        
        self.hint_box.hide()  # Hidden until user requests a hint
        layout.addWidget(self.hint_box)

        # ── Action Button: Need a Hint? ──
        self.btn_hint = QPushButton("Need a Hint?", self)
        self.btn_hint.setIcon(qta.icon("ri.lightbulb-line", color="#ffffff"))
        self.btn_hint.setFixedHeight(30)
        self.btn_hint.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hint.setStyleSheet("""
            QPushButton {
                background-color: #0f172a;
                color: #ffffff;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                font-size: 11px;
                font-weight: 600;
                border-radius: 4px;
                padding: 4px 10px;
            }
            QPushButton:hover { background-color: #1e293b; }
            QPushButton:pressed { background-color: #334155; }
        """)
        self.btn_hint.clicked.connect(self._on_need_hint_clicked)
        layout.addWidget(self.btn_hint)

    def _apply_style(self):
        self.setStyleSheet("""
            QFrame#SocraticHintBubble {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
            }
            QFrame#citationPill {
                background-color: #f1f5f9;
                border: 1px solid #e2e8f0;
                border-radius: 4px;
            }
            QFrame#hintBox {
                background-color: #eff6ff;
                border: 1px solid #bfdbfe;
                border-radius: 6px;
            }
        """)

        # Soft card drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setXOffset(0)
        shadow.setYOffset(6)
        shadow.setColor(QColor(15, 23, 42, 35))
        self.setGraphicsEffect(shadow)

    # ── Public Configuration ──

    def set_feedback(
        self,
        spoken_message: str,
        citation: str = "",
        hints: Optional[List[str]] = None
    ):
        """Populates the bubble with new tutor output and resets hint progression."""
        self.lbl_message.setText(spoken_message)
        if citation:
            self._citation_text = citation
            self.lbl_citation.setText(citation)
            self.citation_pill.show()
        else:
            self.citation_pill.hide()

        if hints and len(hints) > 0:
            self._hints = hints
        self.reset_hints()

    def reset_hints(self):
        """Resets the progressive disclosure to level 0."""
        self._current_level = 0
        self.hint_box.hide()
        self.btn_hint.setText("Need a Hint? (Level 1)")
        self.btn_hint.setEnabled(True)
        self.adjustSize()

    def _on_need_hint_clicked(self):
        """Advances the progressive disclosure level: 1 -> 2 -> 3."""
        if self._current_level >= 3:
            return

        self._current_level += 1
        level_names = {
            1: "HINT LEVEL 1 (NUDGE)",
            2: "HINT LEVEL 2 (FORMULA)",
            3: "HINT LEVEL 3 (SOLUTION REVEAL)"
        }
        self.lbl_hint_badge.setText(level_names.get(self._current_level, "HINT"))

        # Select text for current level (or fallback)
        idx = min(self._current_level - 1, len(self._hints) - 1)
        self.lbl_hint_text.setText(self._hints[idx])
        self.hint_box.show()

        if self._current_level < 3:
            self.btn_hint.setText(f"Need More Help? (Level {self._current_level + 1})")
        else:
            self.btn_hint.setText("All Hints Revealed")
            self.btn_hint.setEnabled(False)

        self.hint_level_changed.emit(self._current_level)
        self.adjustSize()

    def _on_close_clicked(self):
        self.hide()
        self.closed.emit()
