"""
AnswerBubble Canvas Item — Direct Canvas Handwritten Ink Text (Dynamic Unclipped Geometry)
Renders Question + Solution directly onto the canvas paper with Caveat handwritten font.
Dynamically resizes QGraphicsProxyWidget geometry so zero text is ever clipped at top or bottom.
"""

from PyQt6.QtWidgets import QGraphicsProxyWidget, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF
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

    def __init__(self, question: str = "", solution: str = "", proxy_getter=None, parent=None):
        super().__init__(parent)
        self.proxy_getter = proxy_getter
        self.question = question
        self.solution = solution
        self.setMinimumWidth(880)
        
        q_clean = question.replace("Question:", "").strip() if question else ""
        sol_clean = solution.strip()
        if sol_clean.startswith("Question:"):
            parts = sol_clean.split("\n\n", 1)
            if len(parts) > 1:
                sol_clean = parts[1]

        if q_clean:
            self.full_text = f"Question: {q_clean}\n\nSolution:\n{sol_clean}"
        else:
            self.full_text = sol_clean

        # 100% Transparent canvas integration — no box, no clipping boundary!
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
        """)

        self.setObjectName("CanvasHandwrittenText")
        self.layout_main = QVBoxLayout(self)
        self.layout_main.setContentsMargins(20, 20, 20, 36)
        self.layout_main.setSpacing(10)

        # Subtle Drag & Control Header
        self.header_bar = HeaderDragBar(proxy_getter, self)
        header = QHBoxLayout(self.header_bar)
        header.setContentsMargins(0, 0, 0, 0)

        lbl_icon = QLabel("✍️", self.header_bar)
        lbl_icon.setStyleSheet("font-size: 14px; background: transparent;")
        header.addWidget(lbl_icon)
        header.addStretch()

        # Delete button [✕]
        btn_del = QPushButton("✕", self.header_bar)
        btn_del.setObjectName("BtnDelete")
        btn_del.setFixedSize(20, 20)
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.clicked.connect(self.delete_requested.emit)
        header.addWidget(btn_del)

        self.layout_main.addWidget(self.header_bar)

        # Handwritten streaming text label (Caveat font 24pt, Dark Blue Ink)
        self.stream_label = TypewriterLabel(self.full_text, speed_ms=15, parent=self)
        self.stream_label.setFont(get_handwritten_font(24))
        self.stream_label.setStyleSheet("color: #0b2545; background: transparent; padding: 4px;")
        self.layout_main.addWidget(self.stream_label)
        
        # Start incremental typewriter reveal
        self.stream_label.start_streaming()

    def update_proxy_geometry(self):
        """
        Dynamically updates the QGraphicsProxyWidget bounding rectangle on every streaming tick
        so zero text is ever cut off at the top or bottom boundary.
        """
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
    def __init__(self, title: str = "Handwritten Solution", full_text: str = "", question: str = "", parent=None):
        super().__init__(parent)
        self.setup_base_properties()
        self.setZValue(8)
        
        self.bubble = AnswerBubbleWidget(question=question, solution=full_text, proxy_getter=lambda: self)
        self.bubble.delete_requested.connect(self._delete_self)
        self.setWidget(self.bubble)

    def _delete_self(self):
        scene = self.scene()
        if scene:
            scene.removeItem(self)

    def contextMenuEvent(self, event):
        self.build_context_menu(event.screenPos())

    def to_dict(self) -> dict:
        return {
            "type": "AnswerBubble",
            "x": self.x(),
            "y": self.y(),
            "question": self.bubble.question,
            "full_text": self.bubble.stream_label.full_text,
            "z_value": self.zValue()
        }
