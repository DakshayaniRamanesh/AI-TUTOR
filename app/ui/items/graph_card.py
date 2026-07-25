"""
GraphCard Canvas Item — Renders high-res math graphs directly onto the canvas
"""

import os
from PyQt6.QtWidgets import QGraphicsProxyWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, pyqtSignal
from .base_item import BaseGraphicsItemMixin

class HeaderDragBar(QWidget):
    def __init__(self, proxy_getter, parent=None):
        super().__init__(parent)
        self.proxy_getter = proxy_getter
        self._drag_start = None
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
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_start = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        event.accept()

class GraphWidget(QWidget):
    delete_requested = pyqtSignal()

    def __init__(self, title: str = "Math Plot", image_path: str = "", proxy_getter=None, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.resize(460, 310)
        self.setStyleSheet("""
            QWidget#GraphContainer {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 12px;
            }
            QLabel#GraphTitle {
                font-size: 12px;
                font-weight: bold;
                color: #007aff;
            }
        """)

        self.setObjectName("GraphContainer")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(4)

        # Header Drag Bar
        self.header_bar = HeaderDragBar(proxy_getter, self)
        header = QHBoxLayout(self.header_bar)
        header.setContentsMargins(0, 0, 0, 0)

        lbl_title = QLabel(f"◈ {title}", self.header_bar)
        lbl_title.setObjectName("GraphTitle")
        header.addWidget(lbl_title)
        header.addStretch()

        btn_del = QPushButton("✕", self.header_bar)
        btn_del.setFixedSize(20, 20)
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #8e8e93;
                border: none;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                color: #d32f2f;
                background-color: #ffebee;
                border-radius: 10px;
            }
        """)
        btn_del.clicked.connect(self.delete_requested.emit)
        header.addWidget(btn_del)

        layout.addWidget(self.header_bar)

        # Plot Image Display
        self.img_label = QLabel(self)
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if image_path and os.path.exists(image_path):
            pix = QPixmap(image_path)
            self.img_label.setPixmap(pix.scaled(440, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.img_label.setText("Plot Preview")

        layout.addWidget(self.img_label)

class GraphCard(QGraphicsProxyWidget, BaseGraphicsItemMixin):
    def __init__(self, title: str = "Math Plot", image_path: str = "", parent=None):
        super().__init__(parent)
        self.setup_base_properties()
        self.setZValue(6)
        
        self.card = GraphWidget(title, image_path, proxy_getter=lambda: self)
        self.card.delete_requested.connect(self._delete_self)
        self.setWidget(self.card)

    def _delete_self(self):
        scene = self.scene()
        if scene:
            scene.removeItem(self)

    def contextMenuEvent(self, event):
        self.build_context_menu(event.screenPos())

    def to_dict(self) -> dict:
        return {
            "type": "GraphCard",
            "x": self.x(),
            "y": self.y(),
            "title": self.card.findChild(QLabel, "GraphTitle").text().replace("◈ ", ""),
            "image_path": self.card.image_path,
            "z_value": self.zValue()
        }
