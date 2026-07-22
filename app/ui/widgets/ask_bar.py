"""
Persistent STEM / Math Question Bar docked at the bottom of the canvas
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont

class AskBar(QWidget):
    question_submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QWidget#AskBarContainer {
                background-color: #ffffff;
                border: 1px solid #e5e5ea;
                border-radius: 20px;
            }
            QLineEdit {
                border: none;
                background: transparent;
                font-size: 14px;
                padding-left: 8px;
                color: #1c1c1e;
            }
            QPushButton {
                background-color: #007aff;
                color: white;
                border: none;
                border-radius: 14px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        container = QWidget(self)
        container.setObjectName("AskBarContainer")
        c_layout = QHBoxLayout(container)
        c_layout.setContentsMargins(12, 6, 8, 6)
        
        self.input_field = QLineEdit(container)
        self.input_field.setPlaceholderText("Ask a math/STEM question (e.g. d/dx(x^3 + 2x), integral of sin(x)...)")
        self.input_field.returnPressed.connect(self._submit)
        
        self.btn_ask = QPushButton("Ask AI", container)
        self.btn_ask.clicked.connect(self._submit)
        
        c_layout.addWidget(self.input_field)
        c_layout.addWidget(self.btn_ask)
        
        main_layout.addWidget(container)

    def _submit(self):
        text = self.input_field.text().strip()
        if text:
            self.question_submitted.emit(text)
            self.input_field.clear()
