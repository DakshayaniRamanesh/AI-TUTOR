"""
Freeform Canvas View (Pan, Pinch/Scroll Zoom 0.1x-5.0x, Smart Paste, Keyboard Deletion)
"""

from PyQt6.QtWidgets import QGraphicsView, QApplication
from PyQt6.QtGui import QPainter, QWheelEvent, QKeyEvent, QMouseEvent
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from ..backend.workspace.link_utils import is_valid_url, is_video_url, fetch_url_metadata
from ..backend.workspace.summarizer_client import summarize_url
from .items.video_float_item import VideoFloatItem
from .items.answer_bubble import AnswerBubble


from .items.card_item import CardItem
from .items.image_item import ImageItem

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
        self.last_mouse_scene_pos = QPointF(100, 100)
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

    def tabletEvent(self, event):
        """
        Forwards QTabletEvent (stylus/graphics tablet with pressure & tilt)
        to CanvasScene for vector stroke processing.
        """
        scene = self.scene()
        if scene and hasattr(scene, "handle_tablet_event"):
            pos = self.mapToScene(event.position().toPoint())
            handled = scene.handle_tablet_event(event, pos)
            if handled:
                event.accept()
                return
        super().tabletEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        self.last_mouse_scene_pos = self.mapToScene(event.position().toPoint())
        if event.button() == Qt.MouseButton.MiddleButton or (event.button() == Qt.MouseButton.LeftButton and QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier):
            self._is_panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        self.last_mouse_scene_pos = self.mapToScene(event.position().toPoint())
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

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())
            items = self.scene().items(scene_pos)
            if not items:
                from .items.text_box_item import TextBoxItem
                note = TextBoxItem(text="Type here...")
                note.setPos(scene_pos)
                self.scene().addItem(note)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

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

        # Intercept Ctrl+C / Ctrl+X / Ctrl+V
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_C or event.key() == Qt.Key.Key_X:
                scene = self.scene()
                if scene:
                    selected = scene.selectedItems()
                    if selected:
                        items_data = []
                        for item in selected:
                            if hasattr(item, "to_dict"):
                                try:
                                    items_data.append(item.to_dict())
                                    if event.key() == Qt.Key.Key_X:
                                        scene.removeItem(item)
                                except Exception as e:
                                    print(f"Error copying item: {e}")
                        if items_data:
                            import json
                            from PyQt6.QtCore import QMimeData
                            mime_data = QMimeData()
                            mime_data.setData("application/x-kestrel-items", json.dumps(items_data).encode("utf-8"))
                            QApplication.clipboard().setMimeData(mime_data)
                        event.accept()
                        return

            elif event.key() == Qt.Key.Key_V:
                clipboard = QApplication.clipboard()
                mime_data = clipboard.mimeData()
                
                center_pos = self.mapToScene(self.viewport().rect().center())
                
                # 0. Handle pasting Kestrel items
                if mime_data.hasFormat("application/x-kestrel-items"):
                    import json
                    payload = mime_data.data("application/x-kestrel-items").data().decode("utf-8")
                    try:
                        items_data = json.loads(payload)
                        scene = self.scene()
                        if scene and hasattr(scene, "create_item_from_dict"):
                            for data in items_data:
                                item = scene.create_item_from_dict(data)
                                if item:
                                    # Paste them at center
                                    item.setPos(center_pos.x() + data.get("x", 0), center_pos.y() + data.get("y", 0))
                                    if "z_value" in data:
                                        item.setZValue(data["z_value"])
                                    scene.addItem(item)
                            event.accept()
                            return
                    except Exception as e:
                        print(f"Error pasting items: {e}")

                # 1. Handle pasting raw images (scans/screenshots)
                if mime_data.hasImage():
                    pixmap = clipboard.pixmap()
                    if not pixmap.isNull():
                        item = ImageItem(pixmap)
                        item.setPos(center_pos)
                        item.setZValue(5) # Behind ink
                        self.scene().addItem(item)
                        event.accept()
                        return

                # 2. Handle pasting URLs
                text = clipboard.text()
                if text and is_valid_url(text):
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
