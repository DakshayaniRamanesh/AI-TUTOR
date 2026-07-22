"""
Ink Stroke Canvas Item (Pen, Highlighter, Object & Pixel Eraser)
"""

from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsItem
from PyQt6.QtGui import QPen, QColor, QPainterPath, QPainter
from PyQt6.QtCore import Qt
from .base_item import BaseGraphicsItemMixin

class InkStroke(QGraphicsPathItem, BaseGraphicsItemMixin):
    def __init__(self, path: QPainterPath = None, tool_mode: str = "pen", color: str = "#000000", width: float = 3.0, parent=None):
        super().__init__(parent)
        self.setup_base_properties()
        
        self.tool_mode = tool_mode
        self.stroke_color = QColor(color)
        self.stroke_width = width
        
        if tool_mode == "highlighter":
            self.stroke_color.setAlpha(100)
            self.stroke_width = 18.0
            self.setZValue(0) # highlighter behind text
        else:
            self.setZValue(10)

        pen = QPen(self.stroke_color, self.stroke_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.setPen(pen)

        if path:
            self.setPath(path)

    def contextMenuEvent(self, event):
        self.build_context_menu(event.screenPos())

    def to_dict(self) -> dict:
        element_list = []
        path = self.path()
        for i in range(path.elementCount()):
            el = path.elementAt(i)
            element_list.append({"x": el.x, "y": el.y, "type": int(el.type)})
        return {
            "type": "InkStroke",
            "x": self.x(),
            "y": self.y(),
            "tool_mode": self.tool_mode,
            "color": self.stroke_color.name(QColor.NameFormat.HexArgb),
            "width": self.stroke_width,
            "z_value": self.zValue(),
            "elements": element_list
        }
