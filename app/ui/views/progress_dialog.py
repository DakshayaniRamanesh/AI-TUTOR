from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

class ProgressDialog(QDialog):
    def __init__(self, parent=None, title="✨ Working on it! ✨"):
        super().__init__(parent)
        self.setWindowTitle("Progress")
        self.setFixedSize(400, 160)
        
        # Remove the close button so user can't easily interrupt the pipeline blindly
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #fdf2f8; /* very light pink */
                border-radius: 16px;
                border: 2px solid #fbcfe8;
            }
            QLabel#TitleLabel {
                color: #be185d;
                font-size: 16px;
                font-weight: 900;
            }
            QLabel#StatusLabel {
                color: #d946ef;
                font-weight: bold;
                font-size: 13px;
            }
            QProgressBar {
                border: 2px solid #f9a8d4;
                border-radius: 10px;
                text-align: center;
                background-color: #ffffff;
                color: #831843;
                font-weight: bold;
                font-size: 12px;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                                  stop:0 #f472b6, stop:1 #c084fc);
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("TitleLabel")
        self.lbl_title.setFont(QFont("-apple-system", 16, QFont.Weight.Black))
        layout.addWidget(self.lbl_title, alignment=Qt.AlignmentFlag.AlignCenter)

        self.lbl_status = QLabel("🌸 Warming up the magic engines... 🌸")
        self.lbl_status.setObjectName("StatusLabel")
        self.lbl_status.setFont(QFont("-apple-system", 12))
        layout.addWidget(self.lbl_status, alignment=Qt.AlignmentFlag.AlignCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Add a cute little animation timer for the title
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._animate_title)
        self.anim_timer.start(500)
        self._anim_frame = 0
        self._base_title = title.replace("✨", "").strip()

    def _animate_title(self):
        emojis = ["✨", "🌟", "⭐", "💫"]
        emoji = emojis[self._anim_frame % len(emojis)]
        self.lbl_title.setText(f"{emoji} {self._base_title} {emoji}")
        self._anim_frame += 1

    def update_progress(self, stage: str, progress: int):
        # Sprinkle some cute emojis based on progress
        if progress < 30:
            prefix = "🌱"
        elif progress < 70:
            prefix = "🌿"
        elif progress < 100:
            prefix = "🌸"
        else:
            prefix = "🌺"
            
        self.lbl_status.setText(f"{prefix} {stage}")
        self.progress_bar.setValue(progress)

    def finish_success(self):
        self.anim_timer.stop()
        self.lbl_title.setText("🎉 All Done! 🎉")
        self.lbl_status.setText("💖 Magic successful! 💖")
        self.progress_bar.setValue(100)
        
        # Close after a short delay so the user sees the success state
        QTimer.singleShot(800, self.accept)

    def finish_error(self, error_msg: str):
        self.anim_timer.stop()
        self.lbl_title.setText("🥺 Oh no... 🥺")
        self.lbl_status.setText("💔 Something went wrong! 💔")
        self.lbl_status.setStyleSheet("color: #e11d48;")
        
        QTimer.singleShot(2000, self.reject)
