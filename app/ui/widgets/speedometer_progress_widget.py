"""
Windows 11 Fluent Style Ultra-Compact Progress Indicator Widget for Top Header Bar.
Provides a sleek, minimal, 24px-tall Windows 11 themed live progress badge without emojis.
"""

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from ..theme_manager import ThemeManager

class SpeedometerProgressWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme_mgr = ThemeManager.instance()
        self.theme_mgr.theme_changed.connect(self._apply_theme)
        
        self._init_ui()
        self._apply_theme(self.theme_mgr.current_theme)
        self.hide()

    def _init_ui(self):
        self.setObjectName("SpeedometerProgressWidget")
        self.setFixedHeight(24)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        self.lbl_stage = QLabel("Converting...", self)
        self.lbl_stage.setFont(QFont("Segoe UI Variable", 9, QFont.Weight.DemiBold))

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedSize(50, 4)
        self.progress_bar.setTextVisible(False)

        self.lbl_percent = QLabel("0%", self)
        self.lbl_percent.setFont(QFont("Segoe UI Variable", 9, QFont.Weight.Bold))

        layout.addWidget(self.lbl_stage)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.lbl_percent)

        self._clear_timer = QTimer(self)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.timeout.connect(self.hide)

    def start_task(self, task_name: str = "Converting..."):
        self._clear_timer.stop()
        clean_task = task_name[:14] + ".." if len(task_name) > 16 else task_name
        self.lbl_stage.setText(clean_task)
        self.progress_bar.setValue(10)
        self.lbl_percent.setText("10%")
        self.show()

    def update_progress(self, stage: str, progress: int):
        self.show()
        clean_stage = stage[:14] + ".." if len(stage) > 16 else stage
        self.lbl_stage.setText(clean_stage)
        self.progress_bar.setValue(progress)
        self.lbl_percent.setText(f"{progress}%")

    def finish_success(self, msg: str = "Ready!"):
        self.lbl_stage.setText(msg)
        self.progress_bar.setValue(100)
        self.lbl_percent.setText("100%")
        self._clear_timer.start(2000)

    def _apply_theme(self, theme_name: str = "light"):
        is_dark = self.theme_mgr.is_dark()
        bg_col = "#f3f3f3" if not is_dark else "#202020"
        border_col = "#e5e5e5" if not is_dark else "#2d2d2d"
        text_col = "#1f1f1f" if not is_dark else "#ffffff"
        bar_bg = "#e0e0e0" if not is_dark else "#333333"
        bar_chunk = "#0067c0" if not is_dark else "#60cdff"

        self.setStyleSheet(f"""
            QFrame#SpeedometerProgressWidget {{
                background-color: {bg_col};
                border: 1px solid {border_col};
                border-radius: 6px;
                padding: 0px 2px;
            }}
            QLabel {{
                color: {text_col};
                background: transparent;
            }}
            QProgressBar {{
                background-color: {bar_bg};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {bar_chunk};
                border-radius: 2px;
            }}
        """)
