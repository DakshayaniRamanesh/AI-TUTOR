from PyQt6.QtWidgets import QGraphicsTextItem
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt
from .base_item import BaseGraphicsItemMixin

class TextBoxItem(QGraphicsTextItem, BaseGraphicsItemMixin):
    def __init__(self, text: str = "Type here...", parent=None):
        super().__init__(text, parent)
        self.setup_base_properties()
        
        # Native editing capabilities
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        
        # Default font
        font = QFont("Segoe UI", 12)
        self.setFont(font)
        self.setDefaultTextColor(QColor("#1e293b"))
        
        # Make sure it's above ink strokes
        self.setZValue(20)

    def contextMenuEvent(self, event):
        # BaseGraphicsItemMixin provides right-click menu (Send to Back, Bring to Front, Delete)
        self.build_context_menu(event.screenPos())

    def to_dict(self) -> dict:
        return {
            "type": "TextBoxItem",
            "x": self.x(),
            "y": self.y(),
            "text": self.toPlainText(),
            "z_value": self.zValue()
        }
