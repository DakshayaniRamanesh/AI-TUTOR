from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from .theme_manager import ThemeManager


class EraserPopup(QWidget):
    size_changed = pyqtSignal(int)  # 1=small, 2=medium, 3=large

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.selected_size = 2
        self._init_ui()
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme(ThemeManager.instance().current_theme)

    def _init_ui(self):
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(6, 6, 6, 6)
        self.layout.setSpacing(4)

        self.sizes = [
            (8, 1, 'Small Eraser'),
            (16, 2, 'Medium Eraser'),
            (24, 3, 'Large Eraser')
        ]
        
        self.buttons = {}
        for icon_size, size_id, tooltip in self.sizes:
            btn = QPushButton("", self)
            btn.setIconSize(QSize(28, 28))
            btn.setFixedSize(32, 32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda checked, s=size_id: self._on_size_clicked(s))
            self.layout.addWidget(btn)
            self.buttons[size_id] = (btn, icon_size)
            
        self.setFixedSize(116, 44)

    def _render_icons(self):
        c = ThemeManager.instance().get_colors()
        for size_id, (btn, icon_size) in self.buttons.items():
            is_active = (size_id == self.selected_size)
            pixmap = QPixmap(28, 28)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            circle_color = QColor(c['accent_text'] if is_active else c['text_secondary'])
            painter.setBrush(circle_color)
            painter.setPen(Qt.PenStyle.NoPen)
            center = 14
            radius = icon_size / 2.0
            painter.drawEllipse(int(center - radius), int(center - radius), icon_size, icon_size)
            painter.end()
            
            btn.setIcon(QIcon(pixmap))
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
            EraserPopup {{
                background-color: {c['bg_card']};
                border-radius: 4px;
                border: 1px solid {c['border_color']};
            }}
        """)
        self._render_icons()

    def _on_size_clicked(self, size_id: int):
        self.selected_size = size_id
        self._render_icons()
        self.size_changed.emit(size_id)
