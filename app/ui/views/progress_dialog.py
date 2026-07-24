from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class ProgressDialog(QDialog):
    def __init__(self, parent=None, title="Generating Document..."):
        super().__init__(parent)
        self.setWindowTitle("Progress")
        self.setFixedSize(400, 150)
        
        # Remove the close button so user can't easily interrupt the pipeline blindly
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                border-radius: 12px;
            }
            QLabel {
                color: #1c1c1e;
            }
            QProgressBar {
                border: 1px solid #d1d1d6;
                border-radius: 6px;
                text-align: center;
                background-color: #f2f2f7;
                color: #1c1c1e;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #007aff;
                border-radius: 5px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self.lbl_title = QLabel(title)
        self.lbl_title.setFont(QFont("-apple-system", 14, QFont.Weight.Bold))
        layout.addWidget(self.lbl_title, alignment=Qt.AlignmentFlag.AlignCenter)

        self.lbl_status = QLabel("Initializing...")
        self.lbl_status.setFont(QFont("-apple-system", 11))
        self.lbl_status.setStyleSheet("color: #8e8e93;")
        layout.addWidget(self.lbl_status, alignment=Qt.AlignmentFlag.AlignCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

    def update_progress(self, stage: str, progress: int):
        self.lbl_status.setText(stage)
        self.progress_bar.setValue(progress)

    def finish_success(self):
        self.lbl_status.setText("Success!")
        self.progress_bar.setValue(100)
        self.accept()

    def finish_error(self, error_msg: str):
        self.lbl_status.setText("Failed!")
        self.lbl_status.setStyleSheet("color: #ff3b30;")
        self.reject()
