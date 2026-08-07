from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
import qtawesome as qta

class EraserPopup(QWidget):
    size_changed = pyqtSignal(int) # 1=small, 2=medium, 3=large

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            EraserPopup {
                background-color: #ffffff;
                border-radius: 12px;
                border: 1px solid #cbd5e1;
            }
            QPushButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 8px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                border: 1px solid #e2e8f0;
            }
            QPushButton:pressed {
                background-color: #e2e8f0;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        sizes = [
            (10, 1, 'Small Eraser'),
            (20, 2, 'Medium Eraser'),
            (30, 3, 'Large Eraser')
        ]
        
        self.buttons = {}
        for icon_size, size_id, tooltip in sizes:
            # Create a circle icon to represent the eraser size
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor('#94a3b8'))
            painter.setPen(Qt.PenStyle.NoPen)
            center = 16
            radius = icon_size / 2.0
            painter.drawEllipse(int(center - radius), int(center - radius), icon_size, icon_size)
            painter.end()
            
            btn = QPushButton(QIcon(pixmap), "")
            btn.setIconSize(QSize(32, 32))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda checked, s=size_id: self._on_size_clicked(s))
            layout.addWidget(btn)
            self.buttons[size_id] = btn
            
    def _on_size_clicked(self, size_id: int):
        for s_id, btn in self.buttons.items():
            if s_id == size_id:
                btn.setStyleSheet("background-color: #e2e8f0; border: 1px solid #cbd5e1;")
            else:
                btn.setStyleSheet("")
        self.size_changed.emit(size_id)
