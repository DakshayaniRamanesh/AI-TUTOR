"""
Freeform Canvas Scene (Infinite SceneRect, Dotted & Ruled Paper Backgrounds, Freehand Drawing & Universal Eraser)
"""

from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPathItem, QGraphicsProxyWidget
from PyQt6.QtGui import QPen, QColor, QBrush, QPainterPath, QPainter
from PyQt6.QtCore import Qt, QRectF, QPointF
from .items.ink_stroke import InkStroke

class CanvasScene(QGraphicsScene):
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

    def set_background_mode(self, mode: str):
        if mode in ["dotted", "ruled"]:
            self.background_mode = mode
            self.update()

    def drawBackground(self, painter: QPainter, rect: QRectF):
        # Fill base background color
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
            # Ruled lined paper: faint horizontal lines
            painter.setPen(QPen(QColor("#d1d1d6"), 1))
            for y in range(top, bottom, grid_size):
                painter.drawLine(left, y, right, y)

    def erase_items_at(self, pos: QPointF):
        """
        Erases any canvas item (ink stroke, note card, sticky note, table, etc.) at pos.
        """
        items = self.items(pos)
        for item in items:
            if item.scene() == self:
                self.removeItem(item)

    def erase_selected_items(self):
        """
        Erases all currently selected section/items on the canvas.
        """
        for item in self.selectedItems():
            self.removeItem(item)

    def mousePressEvent(self, event):
        if self.active_tool == "eraser" and event.button() == Qt.MouseButton.LeftButton:
            self._is_erasing = True
            # Erase any selected items or items under cursor
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
            self._current_path_item = None
            self._current_painter_path = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)
