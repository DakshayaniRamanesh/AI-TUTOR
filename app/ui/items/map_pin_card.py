"""
MapPinCard Canvas Item (Map thumbnail preview card with address label)
"""

from PyQt6.QtWidgets import QGraphicsProxyWidget, QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from .base_item import BaseGraphicsItemMixin

class MapPinWidget(QWidget):
    def __init__(self, title: str = "Raymond James Stadium", address: str = "4201 N Dale Mabry Hwy, Tampa, FL", parent=None):
        super().__init__(parent)
        self.resize(260, 150)
        self.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 12px;
            }
            QLabel#MapPlaceholder {
                background-color: #e5f3ff;
                border-radius: 8px;
                color: #007aff;
                font-weight: bold;
                font-size: 13px;
            }
            QLabel#AddressLabel {
                font-size: 11px;
                color: #3a3a3c;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        map_box = QLabel("◈ MAP PREVIEW\n" + title, self)
        map_box.setObjectName("MapPlaceholder")
        map_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        map_box.setFixedHeight(80)

        lbl_address = QLabel(address, self)
        lbl_address.setObjectName("AddressLabel")
        lbl_address.setWordWrap(True)

        layout.addWidget(map_box)
        layout.addWidget(lbl_address)

class MapPinCard(QGraphicsProxyWidget, BaseGraphicsItemMixin):
    def __init__(self, title: str = "Raymond James Stadium", address: str = "4201 N Dale Mabry Hwy, Tampa, FL", parent=None):
        super().__init__(parent)
        self.setup_base_properties()
        self.setZValue(5)
        
        self.card = MapPinWidget(title, address)
        self.setWidget(self.card)

    def contextMenuEvent(self, event):
        self.build_context_menu(event.screenPos())

    def to_dict(self) -> dict:
        return {
            "type": "MapPinCard",
            "x": self.x(),
            "y": self.y(),
            "title": self.card.findChild(QLabel, "MapPlaceholder").text(),
            "address": self.card.findChild(QLabel, "AddressLabel").text(),
            "z_value": self.zValue()
        }
