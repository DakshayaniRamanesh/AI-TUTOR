from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QColor
import qtawesome as qta

class ShapesPopup(QWidget):
    shape_selected = pyqtSignal(str) # "rectangle", "circle", "line", "arrow", "triangle"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            ShapesPopup {
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

        shapes = [
            ('fa5.square', 'rectangle'),
            ('fa5.circle', 'circle'),
            ('fa5s.slash', 'line'), # line doesn't have an exact icon, slash or horizontal rule is fine
            ('fa5s.long-arrow-alt-right', 'arrow'),
            ('fa5s.caret-up', 'triangle')
        ]
        
        self.buttons = {}
        for icon_name, shape_id in shapes:
            btn = QPushButton(qta.icon(icon_name, color='#475569'), "")
            btn.setIconSize(QSize(20, 20))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(shape_id.capitalize())
            # Capture variable using default arg
            btn.clicked.connect(lambda checked, s=shape_id: self._on_shape_clicked(s))
            layout.addWidget(btn)
            self.buttons[shape_id] = btn
            
    def _on_shape_clicked(self, shape_id: str):
        for s_id, btn in self.buttons.items():
            if s_id == shape_id:
                btn.setStyleSheet("background-color: #e2e8f0; border: 1px solid #cbd5e1;")
            else:
                btn.setStyleSheet("")
        self.shape_selected.emit(shape_id)
