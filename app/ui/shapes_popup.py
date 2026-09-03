from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
import qtawesome as qta
from .theme_manager import ThemeManager


class ShapesPopup(QWidget):
    shape_selected = pyqtSignal(str)  # "rectangle", "circle", "line", "arrow", "triangle"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.active_shape = "rectangle"
        self._init_ui()
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme(ThemeManager.instance().current_theme)

    def _init_ui(self):
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(6, 6, 6, 6)
        self.layout.setSpacing(4)

        self.shapes = [
            ('ri.checkbox-blank-line', 'rectangle'),
            ('ri.disc-line', 'circle'),
            ('ri.subtract-line', 'line'),
            ('ri.arrow-right-line', 'arrow'),
            ('ri.play-line', 'triangle')
        ]
        
        self.buttons = {}
        for icon_name, shape_id in self.shapes:
            btn = QPushButton("", self)
            btn.setIconSize(QSize(18, 18))
            btn.setFixedSize(32, 32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(shape_id.capitalize())
            btn.clicked.connect(lambda checked, s=shape_id: self._on_shape_clicked(s))
            self.layout.addWidget(btn)
            self.buttons[shape_id] = (btn, icon_name)
            
        self.setFixedSize(184, 44)

    def _render_buttons(self):
        c = ThemeManager.instance().get_colors()
        for shape_id, (btn, icon_name) in self.buttons.items():
            is_active = (shape_id == self.active_shape)
            icon_col = c['accent_text'] if is_active else c['text_secondary']
            btn.setIcon(qta.icon(icon_name, color=icon_col))
            if is_active:
                btn.setStyleSheet(f"background-color: {c['accent']}; border: none; border-radius: 2px;")
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        border: none;
                        border-radius: 2px;
                    }}
                    QPushButton:hover {{
                        background-color: {c['panel_card_bg']};
                    }}
                """)

    def _apply_theme(self, theme_name: str = "light"):
        c = ThemeManager.instance().get_colors()
        self.setStyleSheet(f"""
            ShapesPopup {{
                background-color: {c['bg_card']};
                border-radius: 4px;
                border: 1px solid {c['border_color']};
            }}
        """)
        self._render_buttons()

    def _on_shape_clicked(self, shape_id: str):
        self.active_shape = shape_id
        self._render_buttons()
        self.shape_selected.emit(shape_id)
