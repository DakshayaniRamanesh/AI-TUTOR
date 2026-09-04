"""
Web Link / Media Preview Card Canvas Item
"""

from PyQt6.QtWidgets import QGraphicsProxyWidget, QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from .base_item import BaseGraphicsItemMixin

class CardWidget(QWidget):
    def __init__(self, title: str = "Card Title", subtitle: str = "Card Subtitle / Description", image_url: str = "", source_url: str = "", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.resize(280, 160)
        self.setStyleSheet("""
            QWidget {
                background-color: #fafafa;
                border: 1px solid #e0e0e0;
                border-radius: 12px;
            }
            QLabel#TitleLabel {
                font-size: 14px;
                font-weight: bold;
                color: #111111;
            }
            QLabel#SubtitleLabel {
                font-size: 12px;
                color: #666666;
            }
            QLabel#URLLabel {
                font-size: 11px;
                color: #007aff;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)

        self.lbl_title = QLabel(title, self)
        self.lbl_title.setObjectName("TitleLabel")
        self.lbl_title.setWordWrap(True)

        self.lbl_sub = QLabel(subtitle, self)
        self.lbl_sub.setObjectName("SubtitleLabel")
        self.lbl_sub.setWordWrap(True)

        self.lbl_url = QLabel(source_url or "https://example.com", self)
        self.lbl_url.setObjectName("URLLabel")

        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_sub)
        layout.addStretch()
        layout.addWidget(self.lbl_url)

class CardItem(QGraphicsProxyWidget, BaseGraphicsItemMixin):
    def __init__(self, title: str = "Web Link Preview", subtitle: str = "Description text...", image_url: str = "", source_url: str = "", parent=None):
        super().__init__(parent)
        self.setup_base_properties()
        self.setZValue(5)
        
        self.card = CardWidget(title, subtitle, image_url, source_url)
        self.setWidget(self.card)

    def contextMenuEvent(self, event):
        self.build_context_menu(event.screenPos())

    def to_dict(self) -> dict:
        return {
            "item_id": getattr(self, "item_id", ""),
            "type": "CardItem",
            "x": self.x(),
            "y": self.y(),
            "title": self.card.lbl_title.text(),
            "subtitle": self.card.lbl_sub.text(),
            "source_url": self.card.lbl_url.text(),
            "z_value": self.zValue()
        }
