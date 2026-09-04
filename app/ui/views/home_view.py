"""
Home View — Minimal Brutalist / Technical Hero Landing
Matches the Figma reference design:
- Uppercase monospace category headers
- Prominent 'Kestrel' brand title
- Monospace subtitle
- Sharp geometric action buttons: 'NEW CANVAS' (solid primary) and 'SUBJECTS' (ghost bordered)
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from ..theme_manager import ThemeManager
from ..kestrel_theme import MONO_FONT


class HomeView(QWidget):
    open_blank_notebook = pyqtSignal()
    open_my_subjects = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme(ThemeManager.instance().current_theme)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setSpacing(0)

        # Center Container
        center_box = QWidget(self)
        center_box.setMaximumWidth(560)
        c_layout = QVBoxLayout(center_box)
        c_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.setSpacing(14)

        # Logo Icon
        self.lbl_logo = QLabel(center_box)
        self.lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_logo.setFixedSize(80, 80)
        self.lbl_logo.setStyleSheet("background: transparent;")
        c_layout.addWidget(self.lbl_logo, alignment=Qt.AlignmentFlag.AlignCenter)

        c_layout.addSpacing(6)

        # Top micro-tagline (monospace, uppercase, letter-spaced)
        self.lbl_tagline = QLabel("ADAPTIVE STEM LEARNING ENVIRONMENT", center_box)
        self.lbl_tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(self.lbl_tagline)

        # Brand Title
        self.lbl_title = QLabel("Kestrel", center_box)
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(self.lbl_title)

        # Subtitle
        self.lbl_subtitle = QLabel("YOUR INTELLIGENT NOTEBOOK", center_box)
        self.lbl_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(self.lbl_subtitle)

        c_layout.addSpacing(16)

        # Buttons Layout (2 sharp geometric buttons)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(14)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 1. NEW CANVAS Button (Primary Solid Block)
        self.btn_blank = QPushButton("NEW CANVAS", center_box)
        self.btn_blank.setFixedSize(140, 42)
        self.btn_blank.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_blank.clicked.connect(self.open_blank_notebook.emit)
        btn_layout.addWidget(self.btn_blank)

        # 2. SUBJECTS Button (Ghost Bordered Block)
        self.btn_subjects = QPushButton("SUBJECTS", center_box)
        self.btn_subjects.setFixedSize(140, 42)
        self.btn_subjects.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_subjects.clicked.connect(self.open_my_subjects.emit)
        btn_layout.addWidget(self.btn_subjects)

        c_layout.addLayout(btn_layout)

        c_layout.addSpacing(12)

        # Optional bottom demo link (styled cleanly)
        self.btn_demo = QPushButton("→ VIEW FEATURE DEMO BOARD", center_box)
        self.btn_demo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_demo.clicked.connect(self.open_blank_notebook.emit)
        c_layout.addWidget(self.btn_demo, alignment=Qt.AlignmentFlag.AlignCenter)

        main_layout.addWidget(center_box)

    def _apply_theme(self, theme_name: str = "light"):
        c = ThemeManager.instance().get_colors()
        self.setStyleSheet(f"background-color: {c['bg_app']};")

        # Set theme-appropriate logo
        logo_filename = "kestrel_logo_dark.png" if theme_name == "dark" else "kestrel_logo_light.png"
        logo_path = os.path.join(os.path.dirname(__file__), "..", "assets", logo_filename)
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    72, 72,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.lbl_logo.setPixmap(scaled_pixmap)

        self.lbl_tagline.setStyleSheet(f"""
            font-family: {MONO_FONT};
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 2.5px;
            color: {c['text_secondary']};
            background: transparent;
        """)

        self.lbl_title.setStyleSheet(f"""
            font-size: 52px;
            font-weight: 800;
            letter-spacing: -0.5px;
            color: {c['text_primary']};
            background: transparent;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        """)

        self.lbl_subtitle.setStyleSheet(f"""
            font-family: {MONO_FONT};
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 2px;
            color: {c['text_secondary']};
            background: transparent;
        """)

        # Solid Primary Button
        self.btn_blank.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['accent']};
                color: {c['accent_text']};
                border: 1px solid {c['accent']};
                border-radius: 2px;
                font-family: {MONO_FONT};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{
                background-color: {c['accent_hover']};
                border-color: {c['accent_hover']};
            }}
        """)

        # Ghost Bordered Button
        self.btn_subjects.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['bg_card']};
                color: {c['text_primary']};
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                font-family: {MONO_FONT};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{
                border-color: {c['accent']};
                background-color: {c['panel_card_bg']};
            }}
        """)

        # Demo sub-link button
        self.btn_demo.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                font-family: {MONO_FONT};
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 1.5px;
                color: {c['text_secondary']};
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                color: {c['text_primary']};
            }}
        """)
