"""
Base Interactive Canvas Widget Framework
Provides draggable, minimizable, deletable floating card containers for in-canvas mini-apps.
"""

from PyQt6.QtWidgets import (
    QGraphicsProxyWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame
)
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
import qtawesome as qta

from ..base_item import BaseGraphicsItemMixin
from ...theme_manager import ThemeManager
from ...kestrel_theme import MONO_FONT


class InteractiveDragBar(QWidget):
    """
    Dedicated drag header bar enabling smooth dragging of QGraphicsProxyWidget items.
    """
    def __init__(self, proxy_getter, parent=None):
        super().__init__(parent)
        self.proxy_getter = proxy_getter
        self._drag_start = None
        self.setFixedHeight(30)
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
                scene = proxy.scene()
                if scene and hasattr(scene, "item_collaborated_update") and not getattr(scene, "_is_remote_event", False):
                    scene.item_collaborated_update.emit(proxy.to_dict())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_start = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        proxy = self.proxy_getter()
        if proxy and proxy.scene():
            proxy.scene().scene_changed.emit()
        event.accept()


class InteractiveCardContainer(QWidget):
    """
    Outer card styling with macOS traffic light buttons, title, and embedded content widget.
    """
    delete_requested = pyqtSignal()
    minimized_toggled = pyqtSignal(bool)

    def __init__(self, title: str, icon_name: str, content_widget: QWidget, proxy_getter, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.proxy_getter = proxy_getter
        self.content_widget = content_widget
        self.is_minimized = False

        self._apply_style()

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 8, 10, 10)
        outer_layout.setSpacing(6)

        # ── Header Drag Bar ──
        self.header = InteractiveDragBar(proxy_getter, self)
        hdr_layout = QHBoxLayout(self.header)
        hdr_layout.setContentsMargins(0, 0, 0, 0)
        hdr_layout.setSpacing(6)

        # Icon + Title
        icon_lbl = QLabel(self.header)
        try:
            icon_pixmap = qta.icon(icon_name or "ri.apps-line", color="#8b5cf6").pixmap(15, 15)
        except Exception:
            icon_pixmap = qta.icon("ri.apps-line", color="#8b5cf6").pixmap(15, 15)
        icon_lbl.setPixmap(icon_pixmap)
        hdr_layout.addWidget(icon_lbl)

        self.title_lbl = QLabel(title, self.header)
        self.title_lbl.setStyleSheet(f"font-size: 11px; font-weight: 700; font-family: {MONO_FONT}; letter-spacing: 0.5px;")
        hdr_layout.addWidget(self.title_lbl)

        hdr_layout.addStretch()

        # Minimize Button
        self.btn_min = QPushButton("–", self.header)
        self.btn_min.setFixedSize(18, 18)
        self.btn_min.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_min.setToolTip("Minimize / Expand")
        self.btn_min.setStyleSheet("""
            QPushButton {
                background: rgba(255, 189, 46, 0.2);
                color: #ffbd2e;
                border: 1px solid #ffbd2e;
                border-radius: 9px;
                font-size: 11px;
                font-weight: bold;
                padding: 0;
            }
            QPushButton:hover { background: #ffbd2e; color: #000; }
        """)
        self.btn_min.clicked.connect(self._toggle_minimize)
        hdr_layout.addWidget(self.btn_min)

        # Close / Delete Button
        self.btn_close = QPushButton("×", self.header)
        self.btn_close.setFixedSize(18, 18)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setToolTip("Close Widget")
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: rgba(255, 95, 86, 0.2);
                color: #ff5f56;
                border: 1px solid #ff5f56;
                border-radius: 9px;
                font-size: 11px;
                font-weight: bold;
                padding: 0;
            }
            QPushButton:hover { background: #ff5f56; color: #fff; }
        """)
        self.btn_close.clicked.connect(self.delete_requested.emit)
        hdr_layout.addWidget(self.btn_close)

        outer_layout.addWidget(self.header)

        # Separator line
        self.sep = QFrame(self)
        self.sep.setFrameShape(QFrame.Shape.HLine)
        self.sep.setFixedHeight(1)
        outer_layout.addWidget(self.sep)

        # Content Widget
        outer_layout.addWidget(self.content_widget, stretch=1)

    def _apply_style(self):
        c = ThemeManager.instance().get_colors()
        self.setStyleSheet(f"""
            InteractiveCardContainer {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border_color']};
                border-radius: 12px;
            }}
            QFrame {{
                background-color: {c['border_color']};
            }}
            QLabel {{
                color: {c['text_primary']};
            }}
        """)

    def _toggle_minimize(self):
        self.is_minimized = not self.is_minimized
        self.content_widget.setVisible(not self.is_minimized)
        self.sep.setVisible(not self.is_minimized)
        if self.is_minimized:
            self.adjustSize()
        else:
            self.content_widget.adjustSize()
            self.adjustSize()
        self.minimized_toggled.emit(self.is_minimized)


class InteractiveCanvasItem(QGraphicsProxyWidget, BaseGraphicsItemMixin):
    """
    QGraphicsItem wrapper representing an interactive canvas widget.
    Fully integrates with selection, moving, deleting, and collaboration synchronization.
    """

    def __init__(self, widget_type: str, title: str, icon_name: str, content_widget: QWidget, state_data: dict = None, parent=None):
        super().__init__(parent)
        self.setup_base_properties()
        self.setZValue(25) # Float comfortably above strokes and notes

        self.widget_type = widget_type
        self.title = title
        self.icon_name = icon_name
        self.content_widget = content_widget
        self.state_data = state_data or {}

        # Outer card container
        self.container = InteractiveCardContainer(
            title=title,
            icon_name=icon_name,
            content_widget=content_widget,
            proxy_getter=lambda: self
        )
        self.container.delete_requested.connect(self._delete_self)
        self.container.minimized_toggled.connect(self._on_minimized_toggled)
        self.setWidget(self.container)

    def _delete_self(self):
        scene = self.scene()
        if scene:
            iid = getattr(self, "item_id", None)
            if hasattr(scene, "item_collaborated_delete") and not getattr(scene, "_is_remote_event", False) and iid:
                scene.item_collaborated_delete.emit([iid])
            scene.removeItem(self)
            scene.scene_changed.emit()

    def _on_minimized_toggled(self, is_min: bool):
        scene = self.scene()
        if scene and hasattr(scene, "item_collaborated_update") and not getattr(scene, "_is_remote_event", False):
            scene.item_collaborated_update.emit(self.to_dict())

    def contextMenuEvent(self, event):
        self.build_context_menu(event.screenPos())

    def to_dict(self) -> dict:
        state = dict(self.state_data) if hasattr(self, "state_data") and self.state_data else {}
        if hasattr(self.content_widget, "get_state"):
            try:
                state.update(self.content_widget.get_state())
            except Exception:
                pass

        return {
            "item_id": getattr(self, "item_id", ""),
            "type": "InteractiveCanvasWidget",
            "widget_type": self.widget_type,
            "title": self.title,
            "icon_name": self.icon_name,
            "x": self.x(),
            "y": self.y(),
            "z_value": self.zValue(),
            "is_minimized": self.container.is_minimized,
            "state_data": state
        }
