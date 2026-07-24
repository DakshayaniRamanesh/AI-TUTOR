"""
Freeform Canvas Scene (Infinite SceneRect, Dotted & Ruled Paper Backgrounds, Freehand Drawing, Universal Eraser & Serialization)
"""

from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPathItem, QGraphicsProxyWidget
from PyQt6.QtGui import QPen, QColor, QBrush, QPainterPath, QPainter
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, pyqtSignal

from .items.ink_stroke import InkStroke
from .items.sticky_note import StickyNote
from .items.handwriting_note import HandwritingNote
from .items.table_item import TableItem
from .items.card_item import CardItem
from .items.graph_card import GraphCard
from .items.video_float_item import VideoFloatItem
from .items.answer_bubble import AnswerBubble
from .items.group_selection import GroupSelection

class CanvasScene(QGraphicsScene):
    ink_written_detected = pyqtSignal(str, QPointF)

    def __init__(self, parent=None):
        super().__init__(parent)
        # Infinite canvas bounds
        self.setSceneRect(QRectF(-50000, -50000, 100000, 100000))
        
        # Background mode: "dotted" or "ruled" (ruled is default notebook mode)
        self.background_mode = "ruled"
        
        # Active tool state: "select", "pen", "highlighter", "eraser"
        self.active_tool = "select"
        self.pen_color = "#1c1c1e"
        self.pen_width = 3.0
        
        self._current_path_item = None
        self._current_painter_path = None
        self._is_erasing = False

        # Auto-convert handwriting timer (Apple Notes Math Notes style)
        self._recent_ink_strokes = []
        self._auto_convert_timer = QTimer(self)
        self._auto_convert_timer.setSingleShot(True)
        self._auto_convert_timer.timeout.connect(self._on_auto_convert_ink)

    def set_background_mode(self, mode: str):
        if mode in ["dotted", "ruled"]:
            self.background_mode = mode
            self.update()

    def drawBackground(self, painter: QPainter, rect: QRectF):
        painter.fillRect(rect, QColor("#f4f4f6"))
        
        grid_size = 28
        left = int(rect.left()) - (int(rect.left()) % grid_size)
        top = int(rect.top()) - (int(rect.top()) % grid_size)
        right = int(rect.right())
        bottom = int(rect.bottom())

        if self.background_mode == "dotted":
            painter.setPen(QPen(QColor("#c7c7cc"), 1.5))
            for x in range(left, right, grid_size):
                for y in range(top, bottom, grid_size):
                    painter.drawPoint(x, y)
                    
        elif self.background_mode == "ruled":
            painter.setPen(QPen(QColor("#d1d1d6"), 1))
            for y in range(top, bottom, grid_size):
                painter.drawLine(left, y, right, y)

    def erase_items_at(self, pos: QPointF):
        items = self.items(pos)
        for item in items:
            if item.scene() == self:
                self.removeItem(item)

    def erase_selected_items(self):
        for item in self.selectedItems():
            self.removeItem(item)

    def clear_all(self):
        """
        Clears all items from the canvas scene.
        """
        self.clear()

    def to_dict_list(self) -> list[dict]:
        """
        Serializes all supported canvas items into a list of dict payloads.
        """
        items_data = []
        for item in self.items():
            if hasattr(item, "to_dict"):
                try:
                    items_data.append(item.to_dict())
                except Exception as err:
                    print(f"[CanvasScene] Notice serializing item: {err}")
        return items_data

    def load_from_dict_list(self, items_data: list[dict], video_requested_callback=None, solve_requested_callback=None):
        """
        Restores canvas items from a list of dict payloads.
        """
        self.clear_all()
        if not items_data:
            return

        for data in items_data:
            itype = data.get("type")
            x = data.get("x", 0)
            y = data.get("y", 0)

            item = None
            if itype == "StickyNote":
                item = StickyNote(text=data.get("text", ""), color_key=data.get("color_key", "yellow"))
            elif itype == "HandwritingNote":
                item = HandwritingNote(text=data.get("text", ""))
                if hasattr(item, "widget"):
                    if video_requested_callback:
                        item.widget.video_requested.connect(video_requested_callback)
                    if solve_requested_callback:
                        item.widget.solve_requested.connect(solve_requested_callback)
            elif itype == "TableItem":
                item = TableItem(headers=data.get("headers"), rows=data.get("rows"))
            elif itype == "CardItem":
                item = CardItem(title=data.get("title", "Card"), content=data.get("content", ""))
            elif itype == "GraphCard":
                item = GraphCard(title=data.get("title", "Plot"), image_path=data.get("image_path", ""))
            elif itype == "VideoFloatItem":
                item = VideoFloatItem(
                    job_id=data.get("job_id", ""),
                    title=data.get("title", "Video"),
                    video_url_or_path=data.get("video_path", "")
                )
            elif itype == "AnswerBubble":
                item = AnswerBubble(
                    question=data.get("question", ""),
                    full_text=data.get("full_text", "")
                )
            elif itype == "GroupSelection":
                item = GroupSelection(title=data.get("title", "Group"))

            if item:
                item.setPos(x, y)
                if "z_value" in data:
                    item.setZValue(data["z_value"])
                self.addItem(item)

    def mousePressEvent(self, event):
        if self.active_tool == "eraser" and event.button() == Qt.MouseButton.LeftButton:
            self._is_erasing = True
            self.erase_selected_items()
            self.erase_items_at(event.scenePos())
            event.accept()
        elif self.active_tool in ["pen", "highlighter"] and event.button() == Qt.MouseButton.LeftButton:
            self._current_painter_path = QPainterPath()
            self._current_painter_path.moveTo(event.scenePos())
            
            tool_name = self.active_tool
            self._current_path_item = InkStroke(
                path=self._current_painter_path,
                tool_mode=tool_name,
                color=self.pen_color,
                width=self.pen_width
            )
            self.addItem(self._current_path_item)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_erasing and self.active_tool == "eraser":
            self.erase_items_at(event.scenePos())
            event.accept()
        elif self._current_path_item and self._current_painter_path:
            self._current_painter_path.lineTo(event.scenePos())
            self._current_path_item.setPath(self._current_painter_path)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_erasing:
            self._is_erasing = False
            event.accept()
        elif self._current_path_item:
            if self.active_tool == "pen":
                self._recent_ink_strokes.append(self._current_path_item)
                self._auto_convert_timer.start(1200)
            self._current_path_item = None
            self._current_painter_path = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _on_auto_convert_ink(self):
        if not self._recent_ink_strokes:
            return

        from ..backend.handwriting_ocr import recognize_handwriting

        valid_strokes = [s for s in self._recent_ink_strokes if s.scene() == self]
        if not valid_strokes:
            self._recent_ink_strokes.clear()
            return

        min_x = min(s.sceneBoundingRect().x() for s in valid_strokes)
        min_y = min(s.sceneBoundingRect().y() for s in valid_strokes)
        pos = QPointF(min_x, min_y)

        text = recognize_handwriting(stroke_count=len(valid_strokes))

        for s in valid_strokes:
            self.removeItem(s)

        self._recent_ink_strokes.clear()

        if text:
            self.ink_written_detected.emit(text, pos)
