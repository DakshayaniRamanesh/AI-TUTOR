from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSlider, QPushButton, QLabel, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPoint
from PyQt6.QtGui import QColor, QPainter, QPainterPath

class ColorButton(QPushButton):
    def __init__(self, color_hex: str, is_active: bool = False, parent=None):
        super().__init__(parent)
        self.color_hex = color_hex
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.is_active = is_active
        self.update_style()

    def set_active(self, active: bool):
        self.is_active = active
        self.update_style()

    def update_style(self):
        border = "2px solid #000000" if self.is_active else "1px solid #e2e8f0"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.color_hex};
                border-radius: 14px;
                border: {border};
            }}
            QPushButton:hover {{
                border: 2px solid #94a3b8;
            }}
        """)

class PenPropertiesPopup(QWidget):
    color_changed = pyqtSignal(str)
    thickness_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        # Style the popup to look modern (rounded, white background, shadow)
        self.setStyleSheet("""
            PenPropertiesPopup {
                background-color: #ffffff;
                border-radius: 12px;
                border: 1px solid #cbd5e1;
            }
        """)

        # Add drop shadow
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(16)

        # Thickness slider
        slider_layout = QHBoxLayout()
        self.lbl_thickness = QLabel("3")
        self.lbl_thickness.setFixedWidth(24)
        self.lbl_thickness.setStyleSheet("color: #0f172a; font-weight: bold;")
        
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 40)
        self.slider.setValue(3)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border-radius: 2px;
                height: 4px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #fecdd3, stop:1 #e11d48);
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 2px solid #e11d48;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
        """)
        self.slider.valueChanged.connect(self._on_slider_changed)

        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(self.lbl_thickness)
        layout.addLayout(slider_layout)

        # Separator
        from PyQt6.QtWidgets import QFrame
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #e2e8f0;")
        layout.addWidget(sep)

        # Color Grid
        self.colors = [
            "#1c1c1e", "#ef4444", "#f59e0b", "#10b981",
            "#3b82f6", "#8b5cf6", "#ec4899", "#64748b",
            "#06b6d4", "#f43f5e", "#84cc16", "#d946ef"
        ]
        
        self.color_buttons = []
        grid = QGridLayout()
        grid.setSpacing(10)
        
        for i, c in enumerate(self.colors):
            btn = ColorButton(c, is_active=(i==0))
            btn.clicked.connect(lambda checked, color=c: self._on_color_clicked(color))
            self.color_buttons.append(btn)
            grid.addWidget(btn, i // 4, i % 4)
            
        layout.addLayout(grid)
        self.setFixedSize(180, 220)

    def _on_slider_changed(self, val):
        self.lbl_thickness.setText(str(val))
        self.thickness_changed.emit(val)

    def _on_color_clicked(self, hex_color: str):
        for btn in self.color_buttons:
            btn.set_active(btn.color_hex == hex_color)
        self.color_changed.emit(hex_color)

    def set_active_color(self, hex_color: str):
        for btn in self.color_buttons:
            btn.set_active(btn.color_hex == hex_color)

    def set_active_thickness(self, val: int):
        self.slider.setValue(val)
        self.lbl_thickness.setText(str(val))
