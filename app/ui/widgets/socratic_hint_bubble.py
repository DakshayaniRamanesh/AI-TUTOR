"""
SocraticHintBubble — Floating pedagogical assistance card.
"""
from typing import List, Optional
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QColor

try:
    import qtawesome as qta
except ImportError:
    qta = None

from app.ui.kestrel_theme import MONO_FONT


class SocraticHintBubble(QFrame):
    """
    Floating pedagogical assistance card positioned near the laser pointer.
    """
    closed = pyqtSignal()
    hint_level_changed = pyqtSignal(int)  # Emits 1, 2, or 3 depending on hint level

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SocraticHintBubble")
        self.setFixedWidth(330)
        
        # State
        self._current_level = 0
        self._hints: List[str] = []
        self._citation_text = ""

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
        if qta:
            icon_lbl.setPixmap(qta.icon("ri.magic-line").pixmap(14, 14))
        else:
            icon_lbl.setText("✨")
        hdr_row.addWidget(icon_lbl)

        title_lbl = QLabel("TUTOR GUIDANCE", self)
        title_lbl.setStyleSheet(f"font-family: {MONO_FONT}; font-size: 11px; font-weight: 800; letter-spacing: 1px;")
        hdr_row.addWidget(title_lbl)
        hdr_row.addStretch(1)

        self.btn_close = QPushButton("×", self)
        self.btn_close.setFixedSize(18, 18)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self._on_close_clicked)
        hdr_row.addWidget(self.btn_close)
        layout.addLayout(hdr_row)

        # ── Spoken Tutor Message ──
        self.lbl_message = QLabel(self)
        self.lbl_message.setWordWrap(True)
        self.lbl_message.setStyleSheet("font-size: 12px; line-height: 1.4; font-weight: 500;")
        layout.addWidget(self.lbl_message)

        # ── Citation Pill ──
        self.citation_pill = QFrame(self)
        self.citation_pill.setObjectName("citationPill")
        pill_layout = QHBoxLayout(self.citation_pill)
        pill_layout.setContentsMargins(8, 4, 8, 4)
        pill_layout.setSpacing(6)

        pill_icon = QLabel(self.citation_pill)
        if qta:
            pill_icon.setPixmap(qta.icon("ri.book-open-line").pixmap(11, 11))
        else:
            pill_icon.setText("📖")
        pill_layout.addWidget(pill_icon)

        self.lbl_citation = QLabel(self.citation_pill)
        self.lbl_citation.setStyleSheet(f"font-family: {MONO_FONT}; font-size: 10px; font-weight: 600;")
        self.lbl_citation.setWordWrap(True)
        pill_layout.addWidget(self.lbl_citation)
        pill_layout.addStretch(1)
        layout.addWidget(self.citation_pill)
        self.citation_pill.hide()

        # ── Progressive Hint Container ──
        self.hint_box = QFrame(self)
        self.hint_box.setObjectName("hintBox")
        self.hint_layout = QVBoxLayout(self.hint_box)
        self.hint_layout.setContentsMargins(10, 8, 10, 8)
        self.hint_layout.setSpacing(6)

        self.lbl_hint_badge = QLabel("HINT LEVEL 1", self.hint_box)
        self.lbl_hint_badge.setStyleSheet(f"font-family: {MONO_FONT}; font-size: 9px; font-weight: 800; letter-spacing: 0.5px;")
        self.hint_layout.addWidget(self.lbl_hint_badge)

        self.lbl_hint_text = QLabel(self.hint_box)
        self.lbl_hint_text.setWordWrap(True)
        self.lbl_hint_text.setStyleSheet("font-size: 11px; line-height: 1.3;")
        self.hint_layout.addWidget(self.lbl_hint_text)
        
        self.hint_box.hide()
        layout.addWidget(self.hint_box)

        # ── Action Button: Need a Hint? ──
        self.btn_hint = QPushButton("Need a Hint?", self)
        if qta:
            self.btn_hint.setIcon(qta.icon("ri.lightbulb-line"))
        self.btn_hint.setFixedHeight(30)
        self.btn_hint.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hint.clicked.connect(self._on_need_hint_clicked)
        layout.addWidget(self.btn_hint)

    def _apply_style(self):
        # Uses palette colors to support dark and light mode dynamically
        self.setStyleSheet("""
            QFrame#SocraticHintBubble {
                background-color: palette(window);
                border: 1px solid palette(mid);
                border-radius: 8px;
            }
            QFrame#citationPill {
                background-color: palette(alternate-base);
                border: 1px solid palette(midlight);
                border-radius: 4px;
            }
            QFrame#hintBox {
                background-color: palette(base);
                border: 1px solid palette(highlight);
                border-radius: 6px;
            }
            QPushButton {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                font-size: 11px;
                font-weight: 600;
                border-radius: 4px;
                padding: 4px 10px;
                background-color: palette(highlight);
                color: palette(highlighted-text);
            }
        """)

        # Soft drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
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
        
        if citation and citation.strip():
            self._citation_text = citation.strip()
            self.lbl_citation.setText(self._citation_text)
            self.citation_pill.show()
        else:
            self._citation_text = ""
            self.citation_pill.hide()

        self._hints = hints if hints is not None else []
        self.reset_hints()

    def reset_hints(self):
        """Resets the progressive disclosure."""
        self._current_level = 0
        self.hint_box.hide()
        
        if not self._hints:
            self.btn_hint.hide()
        else:
            self.btn_hint.show()
            self.btn_hint.setText(f"Need a Hint? (1 of {len(self._hints)})")
            self.btn_hint.setEnabled(True)
            
        self.adjustSize()

    def _on_need_hint_clicked(self):
        """Advances the progressive disclosure level up to the available hints."""
        if self._current_level >= len(self._hints):
            return

        self._current_level += 1
        
        level_names = {
            1: "HINT LEVEL 1 (NUDGE)",
            2: "HINT LEVEL 2 (FORMULA)",
            3: "HINT LEVEL 3 (SOLUTION REVEAL)"
        }
        badge_text = level_names.get(self._current_level, f"HINT LEVEL {self._current_level}")
        self.lbl_hint_badge.setText(badge_text)

        idx = self._current_level - 1
        self.lbl_hint_text.setText(self._hints[idx])
        self.hint_box.show()

        if self._current_level < len(self._hints):
            self.btn_hint.setText(f"Need More Help? ({self._current_level + 1} of {len(self._hints)})")
        else:
            self.btn_hint.setText("All Hints Revealed")
            self.btn_hint.setEnabled(False)

        self.hint_level_changed.emit(self._current_level)
        self.adjustSize()

    def _on_close_clicked(self):
        self.hide()
        self.closed.emit()
        
    def constrain_to_parent(self, parent_size):
        """Safely repositions so the bubble doesn't go offscreen."""
        if not self.parent():
            return
            
        geo = self.geometry()
        x = geo.x()
        y = geo.y()
        
        # Keep inside left/right bounds
        if x < 10:
            x = 10
        elif x + geo.width() > parent_size.width() - 10:
            x = parent_size.width() - geo.width() - 10
            
        # Keep inside top/bottom bounds
        if y < 10:
            y = 10
        elif y + geo.height() > parent_size.height() - 10:
            y = parent_size.height() - geo.height() - 10
            
        self.move(x, y)
