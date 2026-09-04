"""
Apple Freeform Handwritten iOS Sticky Note Canvas Item (Movable via Drag Header, Minimizable, Deletable, Editable)
"""

from PyQt6.QtWidgets import QGraphicsProxyWidget, QWidget, QVBoxLayout, QTextEdit, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from .base_item import BaseGraphicsItemMixin
from ..widgets.streaming_text import get_handwritten_font
import qtawesome as qta

STICKY_COLORS = {
    "yellow": "#fff59d",
    "pink": "#ff80ab",
    "blue": "#80d8ff",
    "green": "#b9f6ca",
    "transparent": "transparent"
}

class HeaderDragBar(QWidget):
    """
    Dedicated drag handle bar allowing 100% smooth dragging of QGraphicsProxyWidget.
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

class StickyNoteWidget(QWidget):
    color_changed = pyqtSignal(str)
    delete_requested = pyqtSignal()

    def __init__(self, text: str = "Sticky Note", color_key: str = "yellow", proxy_getter=None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.color_key = color_key
        self.is_minimized = False
        self.full_height = 240
        self.resize(240, self.full_height)
        self._apply_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(4)

        # Draggable Header Bar
        self.header_bar = HeaderDragBar(proxy_getter, self)
        bar_layout = QHBoxLayout(self.header_bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(4)

        # Drag handle icon
        lbl_drag = QLabel("Note", self.header_bar)
        lbl_drag.setStyleSheet("font-size: 12px; font-weight: bold; color: #333333; background: transparent;")
        bar_layout.addWidget(lbl_drag)

        # Color picker buttons
        for k in STICKY_COLORS:
            btn = QPushButton(self.header_bar)
            btn.setFixedSize(13, 13)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"background-color: {STICKY_COLORS[k]}; border: 1px solid #666666; border-radius: 6px;")
            btn.clicked.connect(lambda _, key=k: self._change_color(key))
            bar_layout.addWidget(btn)

        bar_layout.addStretch()

        # Minimize/Maximize button (– / +)
        self.btn_min = QPushButton("–", self.header_bar)
        self.btn_min.setFixedSize(20, 20)
        self.btn_min.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_min.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #444444;
                border: none;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(0,0,0,0.1);
                border-radius: 10px;
            }
        """)
        self.btn_min.clicked.connect(self._toggle_minimize)
        bar_layout.addWidget(self.btn_min)

        # Delete button
        btn_del = QPushButton(self.header_bar)
        btn_del.setIcon(qta.icon('ri.close-line', color='#555555'))
        btn_del.setFixedSize(20, 20)
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #555555;
                border: none;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                color: #d32f2f;
                background-color: rgba(0,0,0,0.1);
                border-radius: 10px;
            }
        """)
        btn_del.clicked.connect(self.delete_requested.emit)
        bar_layout.addWidget(btn_del)

        layout.addWidget(self.header_bar)

        # Text edit with Strong Focus for typing
        self.text_edit = QTextEdit(self)
        self.text_edit.setPlainText(text)
        self.text_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.text_edit.setFont(get_handwritten_font(22))
        self.text_edit.setStyleSheet("border: none; background: transparent; color: #1c1c1e; padding: 2px;")
        layout.addWidget(self.text_edit)

    def _toggle_minimize(self):
        self.is_minimized = not self.is_minimized
        if self.is_minimized:
            self.text_edit.hide()
            self.btn_min.setText("+")
            self.resize(240, 36)
        else:
            self.text_edit.show()
            self.btn_min.setText("–")
            self.resize(240, self.full_height)

    def _change_color(self, key: str):
        self.color_key = key
        self._apply_style()
        self.color_changed.emit(key)

    def _apply_style(self):
        if self.color_key == "transparent":
            self.setStyleSheet("""
                QWidget {
                    background-color: transparent;
                    border: none;
                }
            """)
        else:
            bg = STICKY_COLORS.get(self.color_key, STICKY_COLORS["yellow"])
            self.setStyleSheet(f"""
                QWidget {{
                    background-color: {bg};
                    border-radius: 12px;
                    border: 1px solid rgba(0, 0, 0, 0.12);
                }}
            """)

class StickyNote(QGraphicsProxyWidget, BaseGraphicsItemMixin):
    def __init__(self, text: str = "Sticky Note", color_key: str = "yellow", parent=None):
        super().__init__(parent)
        self.setup_base_properties()
        self.setZValue(5)
        
        self.widget = StickyNoteWidget(text, color_key, proxy_getter=lambda: self)
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
            "item_id": getattr(self, "item_id", ""),
            "type": "StickyNote",
            "x": self.x(),
            "y": self.y(),
            "text": self.widget.text_edit.toPlainText(),
            "color_key": self.widget.color_key,
            "is_minimized": self.widget.is_minimized,
            "z_value": self.zValue()
        }
