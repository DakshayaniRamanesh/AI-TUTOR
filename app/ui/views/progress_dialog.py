from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from ..theme_manager import ThemeManager
from ..kestrel_theme import MONO_FONT


class ProgressDialog(QDialog):
    def __init__(self, parent=None, title="PROCESSING..."):
        super().__init__(parent)
        self.setWindowTitle("Progress")
        self.setFixedSize(400, 150)
        c = ThemeManager.instance().get_colors()
        
        # Remove the close button so user can't easily interrupt the pipeline blindly
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c['bg_card']};
                border-radius: 4px;
                border: 1px solid {c['border_color']};
            }}
            QLabel#TitleLabel {{
                color: {c['text_primary']};
                font-family: {MONO_FONT};
                font-size: 13px;
                font-weight: 800;
                letter-spacing: 1.5px;
            }}
            QLabel#StatusLabel {{
                color: {c['text_secondary']};
                font-family: {MONO_FONT};
                font-weight: 500;
                font-size: 11px;
            }}
            QProgressBar {{
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                text-align: center;
                background-color: {c['input_bg']};
                color: {c['text_primary']};
                font-family: {MONO_FONT};
                font-weight: 600;
                font-size: 10px;
                height: 16px;
            }}
            QProgressBar::chunk {{
                background-color: {c['accent']};
                border-radius: 1px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        clean_title = title.replace("✨", "").replace("🌸", "").strip().upper()
        self.lbl_title = QLabel(clean_title if clean_title else "PROCESSING...")
        self.lbl_title.setObjectName("TitleLabel")
        layout.addWidget(self.lbl_title, alignment=Qt.AlignmentFlag.AlignCenter)

        self.lbl_status = QLabel("Initializing engine...", self)
        self.lbl_status.setObjectName("StatusLabel")
        layout.addWidget(self.lbl_status, alignment=Qt.AlignmentFlag.AlignCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

    def update_progress(self, stage: str, progress: int):
        clean_stage = stage.replace("🌱", "").replace("🌿", "").replace("🌸", "").replace("🌺", "").strip()
        self.lbl_status.setText(f"[ {progress}% ] {clean_stage}")
        self.progress_bar.setValue(progress)

    def finish_success(self):
        c = ThemeManager.instance().get_colors()
        self.lbl_title.setText("TASK COMPLETE")
        self.lbl_status.setText("Done")
        self.progress_bar.setValue(100)
        QTimer.singleShot(600, self.accept)

    def finish_error(self, error_msg: str):
        self.lbl_title.setText("ERROR")
        self.lbl_status.setText(error_msg[:40] if error_msg else "An error occurred.")
        self.lbl_status.setStyleSheet("color: #cc3333;")
        QTimer.singleShot(2000, self.reject)
