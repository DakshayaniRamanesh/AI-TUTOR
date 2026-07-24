"""
HandwritingNote Canvas Item (Typed/Handwritten text container, Movable via Drag Header, Minimizable, Deletable)
"""

from PyQt6.QtWidgets import QGraphicsProxyWidget, QWidget, QVBoxLayout, QTextEdit, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from .base_item import BaseGraphicsItemMixin
from ..widgets.streaming_text import get_handwritten_font
from ..widgets.floating_toolbar import FloatingSelectionToolbar
from ...backend.handwriting_ocr import recognize_handwriting

class HeaderDragBar(QWidget):
    """
    Header bar allowing 100% smooth mouse dragging of proxy items.
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
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_start = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        event.accept()

class HandwritingNoteWidget(QWidget):
    solve_requested = pyqtSignal(str) # note question/text to solve
    video_requested = pyqtSignal(str) # selected text
    delete_requested = pyqtSignal()

    def __init__(self, text: str = "Type or write note here...", proxy_getter=None, parent=None):
        super().__init__(parent)
        self.is_minimized = False
        self.full_height = 220
        self.resize(340, self.full_height)
        self.setStyleSheet("""
            QWidget#NoteContainer {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 12px;
            }
            QTextEdit {
                border: none;
                background: transparent;
                color: #1c1c1e;
            }
            QPushButton {
                background-color: #f2f2f7;
                color: #1c1c1e;
                border: 1px solid #d1d1d6;
                border-radius: 6px;
                padding: 3px 6px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #e5e5ea;
            }
        """)

        self.setObjectName("NoteContainer")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(4)

        # Header Drag Bar
        self.header_bar = HeaderDragBar(proxy_getter, self)
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)
        
        lbl_title = QLabel("✍️ Note", self.header_bar)
        lbl_title.setStyleSheet("border: none; font-size: 12px; font-weight: bold; color: #007aff;")
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()

        self.btn_ocr = QPushButton("Aa OCR", self.header_bar)
        self.btn_ocr.setToolTip("Toggle OCR / Handwriting Recognition")
        self.btn_ocr.clicked.connect(self._on_ocr_clicked)
        
        self.btn_ask = QPushButton("💡 Solve/Ask", self.header_bar)
        self.btn_ask.setToolTip("Solve equation or ask AI Tutor about this note")
        self.btn_ask.setStyleSheet("color: #007aff; font-weight: bold;")
        self.btn_ask.clicked.connect(self._on_ask_clicked)

        self.btn_font = QPushButton("Handwritten", self.header_bar)
        self.btn_font.clicked.connect(self._toggle_font)

        # Minimize/Maximize button
        self.btn_min = QPushButton("–", self.header_bar)
        self.btn_min.setFixedSize(20, 20)
        self.btn_min.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_min.clicked.connect(self._toggle_minimize)

        # Delete button [✕]
        btn_del = QPushButton("✕", self.header_bar)
        btn_del.setFixedSize(20, 20)
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #8e8e93;
                border: none;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                color: #d32f2f;
                background-color: #ffebee;
                border-radius: 10px;
            }
        """)
        btn_del.clicked.connect(self.delete_requested.emit)

        header_layout.addWidget(self.btn_ocr)
        header_layout.addWidget(self.btn_ask)
        header_layout.addWidget(self.btn_font)
        header_layout.addWidget(self.btn_min)
        header_layout.addWidget(btn_del)
        layout.addWidget(self.header_bar)

        # Text area
        self.text_edit = QTextEdit(self)
        self.text_edit.setPlainText(text)
        self.text_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.use_handwriting_font = True
        self.text_edit.setFont(get_handwritten_font(20))
        self.text_edit.selectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.text_edit)

        # Floating context toolbar for selection
        self.selection_toolbar = FloatingSelectionToolbar(self)
        self.selection_toolbar.hide()
        self.selection_toolbar.generate_video_requested.connect(self._on_generate_video)

    def _toggle_minimize(self):
        self.is_minimized = not self.is_minimized
        if self.is_minimized:
            self.text_edit.hide()
            self.btn_min.setText("+")
            self.resize(340, 36)
        else:
            self.text_edit.show()
            self.btn_min.setText("–")
            self.resize(340, self.full_height)

    def _toggle_font(self):
        self.use_handwriting_font = not self.use_handwriting_font
        if self.use_handwriting_font:
            self.text_edit.setFont(get_handwritten_font(20))
            self.btn_font.setText("Handwritten")
        else:
            font = self.text_edit.font()
            font.setFamily("-apple-system")
            font.setPointSize(13)
            self.text_edit.setFont(font)
            self.btn_font.setText("Standard")

    def _on_ocr_clicked(self):
        current_text = self.text_edit.toPlainText().strip()
        text = recognize_handwriting(current_text)
        self.text_edit.setPlainText(text)

    def _on_ask_clicked(self):
        text = self.text_edit.toPlainText().strip()
        if text:
            self.solve_requested.emit(text)

    def _on_selection_changed(self):
        cursor = self.text_edit.textCursor()
        if cursor.hasSelection():
            sel_text = cursor.selectedText()
            if len(sel_text.strip()) > 3:
                pos = self.mapToGlobal(self.rect().topRight())
                self.selection_toolbar.move(pos.x() - 180, pos.y() - 40)
                self.selection_toolbar.show()
                return
        self.selection_toolbar.hide()

    def _on_generate_video(self):
        sel_text = self.text_edit.textCursor().selectedText()
        if sel_text:
            self.video_requested.emit(sel_text)
            self.selection_toolbar.hide()

class HandwritingNote(QGraphicsProxyWidget, BaseGraphicsItemMixin):
    def __init__(self, text: str = "Type or write note here...", parent=None):
        super().__init__(parent)
        self.setup_base_properties()
        self.setZValue(5)
        
        self.widget = HandwritingNoteWidget(text, proxy_getter=lambda: self)
        self.widget.delete_requested.connect(self._delete_self)
        self.setWidget(self.widget)

    def _delete_self(self):
        scene = self.scene()
        if scene:
            scene.removeItem(self)

    def contextMenuEvent(self, event):
        self.build_context_menu(event.screenPos())

    def to_dict(self) -> dict:
        return {
            "type": "HandwritingNote",
            "x": self.x(),
            "y": self.y(),
            "text": self.widget.text_edit.toPlainText(),
            "use_handwriting_font": self.widget.use_handwriting_font,
            "is_minimized": self.widget.is_minimized,
            "z_value": self.zValue()
        }
