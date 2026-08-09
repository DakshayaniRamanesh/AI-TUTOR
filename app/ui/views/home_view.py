from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal

class HomeView(QWidget):
    # These signals tell the main window to switch screens
    open_blank_notebook = pyqtSignal()
    open_my_subjects = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #f8f9fa; color: #1c1c1e; font-family: -apple-system, sans-serif;")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Title
        title = QLabel("Welcome to Kestrel")
        title.setStyleSheet("font-size: 32px; font-weight: bold; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Choose how you want to start learning today.")
        subtitle.setStyleSheet("font-size: 16px; color: #6e6e73; margin-bottom: 40px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # Buttons Layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(30)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Blank Notebook Button (Unstructured path)
        self.btn_blank = QPushButton("📝 Blank Notebook\n\nQuick, unfiled scratchpad")
        self._style_button(self.btn_blank)
        self.btn_blank.clicked.connect(self.open_blank_notebook.emit)
        btn_layout.addWidget(self.btn_blank)

        # My Subjects Button (Structured path)
        self.btn_subjects = QPushButton("📚 My Subjects\n\nOrganized notes & videos")
        self._style_button(self.btn_subjects)
        self.btn_subjects.clicked.connect(self.open_my_subjects.emit)
        btn_layout.addWidget(self.btn_subjects)

        layout.addLayout(btn_layout)

    def _style_button(self, btn: QPushButton):
        btn.setFixedSize(240, 160)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 2px solid #e5e5ea;
                border-radius: 12px;
                font-size: 16px;
                font-weight: 500;
                color: #1c1c1e;
                padding: 20px;
            }
            QPushButton:hover {
                border-color: #007aff;
                color: #007aff;
                background-color: #f0f8ff;
            }
        """)
