from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class PlaceholderPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #f2f2f7;")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.title_label = QLabel("Section Under Construction")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #3a3a3c;")
        layout.addWidget(self.title_label)
        
        self.desc_label = QLabel("This feature will be available in a future update.")
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.desc_label.setStyleSheet("font-size: 14px; color: #8e8e93;")
        layout.addWidget(self.desc_label)

    def set_title(self, title: str):
        self.title_label.setText(f"{title} (Coming Soon)")
