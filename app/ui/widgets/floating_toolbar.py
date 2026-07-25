"""
Floating Context Selection Toolbar (iOS style: Copy | Bold | Generate Video)
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt

class FloatingSelectionToolbar(QWidget):
    copy_requested = pyqtSignal()
    bold_requested = pyqtSignal()
    generate_video_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)
        
        container = QWidget(self)
        container.setStyleSheet("""
            QWidget {
                background-color: #2c2c2e;
                border-radius: 10px;
            }
            QPushButton {
                color: #ffffff;
                background: transparent;
                border: none;
                padding: 4px 10px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3a3a3c;
                border-radius: 6px;
            }
        """)
        c_layout = QHBoxLayout(container)
        c_layout.setContentsMargins(4, 2, 4, 2)
        c_layout.setSpacing(2)
        
        btn_copy = QPushButton("Copy", container)
        btn_copy.clicked.connect(self.copy_requested.emit)
        
        btn_bold = QPushButton("Bold", container)
        btn_bold.clicked.connect(self.bold_requested.emit)
        
        btn_video = QPushButton("▷ Generate Video", container)
        btn_video.setStyleSheet("color: #34c759; font-weight: bold;")
        btn_video.clicked.connect(self.generate_video_requested.emit)
        
        c_layout.addWidget(btn_copy)
        c_layout.addWidget(btn_bold)
        c_layout.addWidget(btn_video)
        
        layout.addWidget(container)
