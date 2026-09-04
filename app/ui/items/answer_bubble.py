"""
AnswerBubble Canvas Item — Direct Canvas Handwritten Ink Text (Dynamic Unclipped Geometry)
Renders Question + Solution / Hints directly onto the canvas paper with Caveat handwritten font.
Includes a toggle button to reveal full solution vs. concise hints.
"""

from PyQt6.QtWidgets import QGraphicsProxyWidget, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from .base_item import BaseGraphicsItemMixin
from ..widgets.streaming_text import TypewriterLabel, get_handwritten_font

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

    def __init__(self, question: str = "", solution: str = "", hints: str = "", is_direct_math: bool = False, proxy_getter=None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.proxy_getter = proxy_getter
        self.question = question
        self.hints = hints or solution
        self.full_solution = solution or hints
        self.is_direct_math = is_direct_math
        self.showing_full = False
        self.setMinimumWidth(880)

        self.setStyleSheet("""
            QWidget#CanvasHandwrittenText {
                background: transparent;
                border: none;
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
        """)

        self.setObjectName("CanvasHandwrittenText")
        self.layout_main = QVBoxLayout(self)
        self.layout_main.setContentsMargins(20, 20, 20, 36)
        self.layout_main.setSpacing(10)

        # Subtle Drag & Control Header
        self.header_bar = HeaderDragBar(proxy_getter, self)
        header = QHBoxLayout(self.header_bar)
        header.setContentsMargins(0, 0, 0, 0)

        lbl_icon = QLabel("✎", self.header_bar)
        lbl_icon.setStyleSheet("font-size: 14px; background: transparent;")
        header.addWidget(lbl_icon)

        # Toggle Button: "✦ Reveal Full Solution"
        self.btn_toggle = QPushButton("✦ Reveal Full Solution", self.header_bar)
        self.btn_toggle.setObjectName("BtnToggle")
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.clicked.connect(self._toggle_full_solution)
        header.addWidget(self.btn_toggle)
        header.addStretch()

        if self.is_direct_math or not self.full_solution:
            self.btn_toggle.hide()

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
        self.stream_label.setFont(get_handwritten_font(24))
        self.stream_label.setStyleSheet("color: #0b2545; background: transparent; padding: 4px;")
        self.layout_main.addWidget(self.stream_label)

        self._render_current_view()

    def _render_current_view(self):
        q_clean = self.question.replace("Question:", "").strip() if self.question else ""
        if self.is_direct_math:
            text = f"Question: {q_clean}\n\n{self.hints}" if q_clean else self.hints
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
        else:
            self.hints = str(res_payload)
            self.full_solution = str(res_payload)
            self.is_direct_math = False

        self.showing_full = False
        self._render_current_view()

    def update_proxy_geometry(self):
        self.adjustSize()
        if self.proxy_getter:
            proxy = self.proxy_getter()
            if proxy:
                proxy.prepareGeometryChange()
                hint = self.layout_main.sizeHint()
                req_width = max(880, hint.width() + 40)
                req_height = max(180, hint.height() + 60)
                self.resize(req_width, req_height)
                proxy.setGeometry(QRectF(0, 0, req_width, req_height))
                proxy.update()

class AnswerBubble(QGraphicsProxyWidget, BaseGraphicsItemMixin):
    def __init__(self, title: str = "Handwritten Solution", full_text: str = "", question: str = "", hints: str = "", is_direct_math: bool = False, parent=None):
        super().__init__(parent)
        self.setup_base_properties()
        self.setZValue(8)

        self.bubble = AnswerBubbleWidget(question=question, solution=full_text, hints=hints, is_direct_math=is_direct_math, proxy_getter=lambda: self)
        self.bubble.delete_requested.connect(self._delete_self)
        self.setWidget(self.bubble)

    def update_solution(self, question: str, res_payload):
        self.bubble.update_text(question, res_payload)

    def _delete_self(self):
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
            "z_value": self.zValue()
        }
