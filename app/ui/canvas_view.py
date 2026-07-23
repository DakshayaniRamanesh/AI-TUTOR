"""
Freeform Canvas View (Pan, Pinch/Scroll Zoom 0.1x-5.0x, Smart Paste, Keyboard Deletion)
"""

from PyQt6.QtWidgets import QGraphicsView, QApplication
from PyQt6.QtGui import QPainter, QWheelEvent, QKeyEvent, QMouseEvent
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from ..backend.link_utils import is_valid_url, is_video_url, fetch_url_metadata
from ..backend.summarizer_client import summarize_url
from .items.video_float_item import VideoFloatItem
from .items.answer_bubble import AnswerBubble
from .items.handwriting_note import HandwritingNote
from .items.card_item import CardItem

class CanvasView(QGraphicsView):
    zoom_changed = pyqtSignal(float)

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform |
            QPainter.RenderHint.TextAntialiasing
        )
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._is_panning = False
        self._pan_start = QPointF()
        self.current_zoom = 1.0

    def set_zoom(self, scale_factor: float):
        scale_factor = max(0.1, min(5.0, scale_factor))
        factor = scale_factor / self.current_zoom
        self.current_zoom = scale_factor
        self.scale(factor, factor)
        self.zoom_changed.emit(self.current_zoom)

    def zoom_by(self, factor: float):
        self.set_zoom(self.current_zoom * factor)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Zoom
            delta = event.angleDelta().y()
            zoom_factor = 1.15 if delta > 0 else 0.85
            new_zoom = self.current_zoom * zoom_factor
            self.set_zoom(new_zoom)
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton or (event.button() == Qt.MouseButton.LeftButton and QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier):
            self._is_panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - delta.x()))
            self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - delta.y()))
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        # Keyboard Deletion of Selected Canvas Items
        if event.key() in [Qt.Key.Key_Delete, Qt.Key.Key_Backspace]:
            scene = self.scene()
            if scene:
                selected_items = scene.selectedItems()
                for item in selected_items:
                    scene.removeItem(item)
                if selected_items:
                    event.accept()
                    return

        # Intercept Ctrl+V / Cmd+V paste
        if event.key() == Qt.Key.Key_V and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            clipboard = QApplication.clipboard()
            text = clipboard.text()
            if text and is_valid_url(text):
                center_pos = self.mapToScene(self.viewport().rect().center())
                meta = fetch_url_metadata(text)
                
                if meta["is_video"]:
                    # Create floating video player
                    item = VideoFloatItem(title=meta["title"], video_url_or_path=text)
                    item.setPos(center_pos)
                    self.scene().addItem(item)
                else:
                    # Summarize article -> AnswerBubble in handwritten font
                    summary = summarize_url(text, title=meta["title"])
                    bubble = AnswerBubble(title=meta["title"], full_text=summary)
                    bubble.setPos(center_pos)
                    self.scene().addItem(bubble)
                event.accept()
                return

        super().keyPressEvent(event)
