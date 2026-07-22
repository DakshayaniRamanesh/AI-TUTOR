"""
GroupSelection Canvas Item (Dashed-border bounding container with header & collapse/expand)
"""

from PyQt6.QtWidgets import QGraphicsProxyWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from .base_item import BaseGraphicsItemMixin

class GroupContainerWidget(QWidget):
    def __init__(self, title: str = "Grouped Items", parent=None):
        super().__init__(parent)
        self.resize(320, 240)
        self.is_collapsed = False
        
        self.setStyleSheet("""
            QWidget#GroupWidget {
                background-color: rgba(240, 240, 245, 0.4);
                border: 2px dashed #007aff;
                border-radius: 12px;
            }
            QLabel#GroupHeader {
                font-size: 13px;
                font-weight: bold;
                color: #007aff;
            }
            QPushButton {
                background-color: #007aff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
            }
        """)

        self.setObjectName("GroupWidget")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)

        # Header
        header_layout = QHBoxLayout()
        self.lbl_title = QLabel(f"📦 {title}", self)
        self.lbl_title.setObjectName("GroupHeader")
        
        self.btn_toggle = QPushButton("Collapse", self)
        self.btn_toggle.clicked.connect(self._toggle_collapse)

        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_toggle)
        layout.addLayout(header_layout)
        layout.addStretch()

    def _toggle_collapse(self):
        self.is_collapsed = not self.is_collapsed
        if self.is_collapsed:
            self.resize(self.width(), 44)
            self.btn_toggle.setText("Expand")
        else:
            self.resize(self.width(), 240)
            self.btn_toggle.setText("Collapse")

class GroupSelection(QGraphicsProxyWidget, BaseGraphicsItemMixin):
    def __init__(self, title: str = "More items to check out", parent=None):
        super().__init__(parent)
        self.setup_base_properties()
        self.setZValue(2) # Behind items
        
        self.group_widget = GroupContainerWidget(title)
        self.setWidget(self.group_widget)

    def contextMenuEvent(self, event):
        self.build_context_menu(event.screenPos())

    def to_dict(self) -> dict:
        return {
            "type": "GroupSelection",
            "x": self.x(),
            "y": self.y(),
            "title": self.group_widget.lbl_title.text().replace("📦 ", ""),
            "is_collapsed": self.group_widget.is_collapsed,
            "z_value": self.zValue()
        }
