"""
AnswerBubble Canvas Item — Direct Canvas Handwritten Ink Text (Dynamic Unclipped Geometry)
Renders Question + Solution / Hints directly onto the canvas paper with Caveat handwritten font.
Includes a toggle button to reveal full solution vs. concise hints,
citation chips for retrieved subject materials, and asynchronous voice narration playback.
"""

from typing import List, Optional, Dict, Any
from PyQt6.QtWidgets import (
    QGraphicsProxyWidget, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from .base_item import BaseGraphicsItemMixin
from ..widgets.streaming_text import TypewriterLabel, get_handwritten_font
from app.services.tutoring.voice_service import VoiceNarrationService

class HeaderDragBar(QWidget):
    """
    Subtle drag handle allowing 100% smooth mouse dragging of handwritten canvas text.
    """
    def __init__(self, proxy_getter, parent=None):
        super().__init__(parent)
        self.proxy_getter = proxy_getter
        self._drag_start = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.globalPosition()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start:
            proxy = self.proxy_getter()
            if proxy:
                delta = event.globalPosition() - self._drag_start
                self._drag_start = event.globalPosition()
                proxy.setPos(proxy.pos() + delta)
                proxy.prepareGeometryChange()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_start = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        event.accept()

class AnswerBubbleWidget(QWidget):
    delete_requested = pyqtSignal()
    citation_clicked = pyqtSignal(dict)

    def __init__(
        self, 
        question: str = "", 
        solution: str = "", 
        hints: str = "", 
        is_direct_math: bool = False, 
        verdict: Optional[str] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        spoken_text: Optional[str] = None,
        proxy_getter=None, 
        parent=None
    ):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.proxy_getter = proxy_getter
        self.question = question
        self.hints = hints or solution
        self.full_solution = solution or hints
        self.is_direct_math = is_direct_math
        self.verdict = verdict
        self.citations = citations or []
        self.spoken_text = spoken_text
        self.showing_full = False
        self.setMinimumWidth(720)

        self.setStyleSheet("""
            QWidget#CanvasHandwrittenText {
                background: rgba(255, 255, 255, 0.94);
                border: 1px solid rgba(0, 0, 0, 0.12);
                border-radius: 8px;
            }
            QPushButton#BtnDelete {
                background: transparent;
                color: #8e8e93;
                border: none;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#BtnDelete:hover {
                color: #d32f2f;
                background-color: rgba(211, 47, 47, 0.12);
                border-radius: 10px;
            }
            QPushButton#BtnSpeak {
                background: transparent;
                color: #3b82f6;
                border: 1px solid rgba(59, 130, 246, 0.3);
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#BtnSpeak:hover {
                background-color: rgba(59, 130, 246, 0.15);
            }
            QPushButton#BtnToggle {
                background-color: #0a0a0a;
                color: #ffffff;
                border: 1px solid #252525;
                border-radius: 4px;
                padding: 4px 10px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton#BtnToggle:hover {
                background-color: #222222;
            }
            QLabel#CitationChip {
                background: #f1f5f9;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 500;
            }
        """)

        self.setObjectName("CanvasHandwrittenText")
        self.layout_main = QVBoxLayout(self)
        self.layout_main.setContentsMargins(18, 14, 18, 18)
        self.layout_main.setSpacing(8)

        # Header Bar
        self.header_bar = HeaderDragBar(proxy_getter, self)
        header = QHBoxLayout(self.header_bar)
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        lbl_icon = QLabel("✎", self.header_bar)
        lbl_icon.setStyleSheet("font-size: 14px; background: transparent;")
        header.addWidget(lbl_icon)

        # Verdict Tag if present
        if self.verdict:
            lbl_verdict = QLabel(self.verdict.upper(), self.header_bar)
            if self.verdict.upper() == "VALID":
                lbl_verdict.setStyleSheet("color: #16a34a; font-weight: 700; font-size: 12px;")
            elif self.verdict.upper() == "INVALID":
                lbl_verdict.setStyleSheet("color: #dc2626; font-weight: 700; font-size: 12px;")
            else:
                lbl_verdict.setStyleSheet("color: #64748b; font-weight: 600; font-size: 12px;")
            header.addWidget(lbl_verdict)

        # Toggle Button: "✦ Reveal Full Solution"
        self.btn_toggle = QPushButton("✦ Reveal Full Solution", self.header_bar)
        self.btn_toggle.setObjectName("BtnToggle")
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.clicked.connect(self._toggle_full_solution)
        header.addWidget(self.btn_toggle)
        header.addStretch()

        if self.is_direct_math or not self.full_solution:
            self.btn_toggle.hide()

        # Audio Narration Speak Button
        self.btn_speak = QPushButton("🔊 Listen", self.header_bar)
        self.btn_speak.setObjectName("BtnSpeak")
        self.btn_speak.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_speak.clicked.connect(self._on_speak_clicked)
        header.addWidget(self.btn_speak)

        # Delete button [✕]
        btn_del = QPushButton("✕", self.header_bar)
        btn_del.setObjectName("BtnDelete")
        btn_del.setFixedSize(20, 20)
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.clicked.connect(self.delete_requested.emit)
        header.addWidget(btn_del)

        self.layout_main.addWidget(self.header_bar)

        # Handwritten streaming text label
        self.stream_label = TypewriterLabel("", speed_ms=15, parent=self)
        self.stream_label.setFont(get_handwritten_font(22))
        self.stream_label.setStyleSheet("color: #0b2545; background: transparent; padding: 4px;")
        self.layout_main.addWidget(self.stream_label)

        # Citation chips container
        self.citations_container = QWidget(self)
        self.citations_layout = QHBoxLayout(self.citations_container)
        self.citations_layout.setContentsMargins(0, 4, 0, 0)
        self.citations_layout.setSpacing(6)
        self.layout_main.addWidget(self.citations_container)
        self._render_citations()

        self._render_current_view()

    def _render_citations(self):
        # Clear existing chips
        while self.citations_layout.count():
            item = self.citations_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.citations:
            self.citations_container.hide()
            return

        self.citations_container.show()
        lbl_sources = QLabel("Sources:", self.citations_container)
        lbl_sources.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748b;")
        self.citations_layout.addWidget(lbl_sources)

        for chip in self.citations:
            title = chip.get("document_title") or "Material"
            page = chip.get("page_number")
            chip_text = f"{title} · Page {page}" if page else title
            
            btn_chip = QPushButton(chip_text, self.citations_container)
            btn_chip.setStyleSheet("""
                QPushButton {
                    background: #f1f5f9;
                    color: #2563eb;
                    border: 1px solid #bfdbfe;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background: #e2e8f0;
                    text-decoration: underline;
                }
            """)
            btn_chip.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_chip.clicked.connect(lambda checked, c=chip: self.citation_clicked.emit(c))
            self.citations_layout.addWidget(btn_chip)

        self.citations_layout.addStretch()

    def _on_speak_clicked(self):
        service = VoiceNarrationService.instance()
        if service.is_playing():
            service.stop()
            self.btn_speak.setText("🔊 Listen")
        else:
            text_to_speak = self.spoken_text or self.hints or self.full_solution or self.question
            self.btn_speak.setText("⏹ Stop")
            service.speak(text_to_speak, on_finished=lambda: self.btn_speak.setText("🔊 Listen"))

    def _render_current_view(self):
        q_clean = self.question.replace("Question:", "").strip() if self.question else ""
        has_full_sol = bool(self.full_solution and self.hints and self.full_solution.strip() != self.hints.strip())

        if not has_full_sol:
            text = f"Question: {q_clean}\n\n{self.hints}" if q_clean else (self.hints or self.full_solution)
            self.btn_toggle.hide()
        elif self.showing_full:
            text = f"Question: {q_clean}\n\n{self.full_solution}" if q_clean else self.full_solution
            self.btn_toggle.setText("✦ Hide Full Solution")
            self.btn_toggle.show()
        else:
            text = f"Question: {q_clean}\n\n{self.hints}" if q_clean else self.hints
            self.btn_toggle.setText("✦ Reveal Full Solution")
            self.btn_toggle.show()

        self.stream_label.start_streaming(text)

    def _toggle_full_solution(self):
        self.showing_full = not self.showing_full
        self._render_current_view()

    def update_text(self, question: str, res_payload):
        self.question = question
        if isinstance(res_payload, dict):
            self.hints = res_payload.get("hints", "")
            self.full_solution = res_payload.get("full_solution", "") or res_payload.get("solution", "")
            self.is_direct_math = res_payload.get("is_direct_math", False)
            self.citations = res_payload.get("citations", [])
            self.spoken_text = res_payload.get("spoken_text", "")
            self.verdict = res_payload.get("verdict", None)
        else:
            self.hints = str(res_payload)
            self.full_solution = str(res_payload)
            self.is_direct_math = False

        self.showing_full = False
        self._render_citations()
        self._render_current_view()

class AnswerBubble(QGraphicsProxyWidget, BaseGraphicsItemMixin):
    def __init__(
        self, 
        title: str = "Tutor Feedback", 
        full_text: str = "", 
        question: str = "", 
        hints: str = "", 
        is_direct_math: bool = False, 
        verdict: Optional[str] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        spoken_text: Optional[str] = None,
        parent=None
    ):
        super().__init__(parent)
        self.setup_base_properties()
        self.setZValue(8)

        self.bubble = AnswerBubbleWidget(
            question=question, 
            solution=full_text, 
            hints=hints, 
            is_direct_math=is_direct_math,
            verdict=verdict,
            citations=citations,
            spoken_text=spoken_text,
            proxy_getter=lambda: self
        )
        self.bubble.delete_requested.connect(self._delete_self)
        self.setWidget(self.bubble)

    def update_solution(self, question: str, res_payload):
        self.bubble.update_text(question, res_payload)

    def _delete_self(self):
        VoiceNarrationService.instance().stop()
        scene = self.scene()
        if scene:
            scene.removeItem(self)

    def contextMenuEvent(self, event):
        self.build_context_menu(event.screenPos())

    def to_dict(self) -> dict:
        return {
            "item_id": getattr(self, "item_id", ""),
            "type": "AnswerBubble",
            "x": self.x(),
            "y": self.y(),
            "question": self.bubble.question,
            "full_text": self.bubble.full_solution,
            "hints": self.bubble.hints,
            "is_direct_math": self.bubble.is_direct_math,
            "verdict": self.bubble.verdict,
            "citations": self.bubble.citations,
            "z_value": self.zValue()
        }
