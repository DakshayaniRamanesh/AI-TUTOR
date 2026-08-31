from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSlider, QPushButton, QLabel, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from .theme_manager import ThemeManager
from .kestrel_theme import MONO_FONT


class ColorButton(QPushButton):
    def __init__(self, color_hex: str, is_active: bool = False, parent=None):
        super().__init__(parent)
        self.color_hex = color_hex
        self.setFixedSize(26, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.is_active = is_active
        self.update_style()

    def set_active(self, active: bool):
        self.is_active = active
        self.update_style()

    def update_style(self):
        c = ThemeManager.instance().get_colors()
        border = f"2px solid {c['accent']}" if self.is_active else f"1px solid {c['border_color']}"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.color_hex};
                border-radius: 2px;
                border: {border};
            }}
            QPushButton:hover {{
                border: 2px solid {c['text_secondary']};
            }}
        """)


class PenPropertiesPopup(QWidget):
    color_changed = pyqtSignal(str)
    thickness_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._init_ui()
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme(ThemeManager.instance().current_theme)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Thickness slider
        slider_layout = QHBoxLayout()
        slider_layout.setSpacing(8)

        lbl_title = QLabel("SIZE", self)
        lbl_title.setObjectName("LblSizeTitle")
        lbl_title.setStyleSheet(f"font-size: 11px; font-weight: 700; letter-spacing: 1px; font-family: {MONO_FONT};")

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 40)
        self.slider.setValue(3)
        self.slider.valueChanged.connect(self._on_slider_changed)

        self.lbl_thickness = QLabel("3", self)
        self.lbl_thickness.setFixedWidth(24)
        self.lbl_thickness.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_thickness.setStyleSheet(f"font-size: 12px; font-weight: 600; font-family: {MONO_FONT};")

        slider_layout.addWidget(lbl_title)
        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(self.lbl_thickness)
        layout.addLayout(slider_layout)

        # Separator
        self.sep = QFrame()
        self.sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(self.sep)

        # Color Grid
        self.colors = [
            "#0a0a0a", "#e5e5ea", "#ef4444", "#f59e0b",
            "#10b981", "#3b82f6", "#8b5cf6", "#ec4899",
            "#64748b", "#06b6d4", "#f43f5e", "#84cc16"
        ]
        
        self.color_buttons = []
        grid = QGridLayout()
        grid.setSpacing(6)
        
        for i, c_hex in enumerate(self.colors):
            btn = ColorButton(c_hex, is_active=(i == 0))
            btn.clicked.connect(lambda checked, color=c_hex: self._on_color_clicked(color))
            self.color_buttons.append(btn)
            grid.addWidget(btn, i // 4, i % 4)
            
        layout.addLayout(grid)
        self.setFixedSize(180, 190)

    def _apply_theme(self, theme_name: str = "light"):
        c = ThemeManager.instance().get_colors()
        self.setStyleSheet(f"""
            PenPropertiesPopup {{
                background-color: {c['bg_card']};
                border-radius: 4px;
                border: 1px solid {c['border_color']};
            }}
            QLabel {{
                color: {c['text_primary']};
            }}
            QSlider::groove:horizontal {{
                border-radius: 1px;
                height: 2px;
                background-color: {c['border_color']};
            }}
            QSlider::handle:horizontal {{
                background-color: {c['accent']};
                border: 1px solid {c['accent']};
                width: 12px;
                height: 12px;
                margin: -5px 0;
                border-radius: 6px;
            }}
        """)
        self.sep.setStyleSheet(f"color: {c['border_color']};")
        for btn in self.color_buttons:
            btn.update_style()

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
