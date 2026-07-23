"""
Persistent STEM / Math & PDF Question Bar docked at the bottom of the canvas
Supports standard STEM mode and PDF Split-Screen RAG mode.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont

class AskBar(QWidget):
    question_submitted = pyqtSignal(str)
    pdf_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_pdf_mode = False
        
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
            QPushButton#BtnAsk {
                background-color: #007aff;
                color: white;
                border: none;
                border-radius: 14px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton#BtnAsk:hover {
                background-color: #0056b3;
            }
            QPushButton#BtnPdf {
                background-color: #f2f2f7;
                color: #ff3b30;
                border: 1px solid #d1d1d6;
                border-radius: 14px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton#BtnPdf:hover {
                background-color: #ffebee;
            }
        """)
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        container = QWidget(self)
        container.setObjectName("AskBarContainer")
        c_layout = QHBoxLayout(container)
        c_layout.setContentsMargins(10, 6, 8, 6)
        c_layout.setSpacing(6)
        
        # PDF upload button
        self.btn_pdf = QPushButton("📄 PDF", container)
        self.btn_pdf.setObjectName("BtnPdf")
        self.btn_pdf.clicked.connect(self.pdf_requested.emit)

        self.input_field = QLineEdit(container)
        self.input_field.setPlaceholderText("Ask a math/STEM question (e.g. d/dx(x^3 + 2x), integral of sin(x)...)")
        self.input_field.returnPressed.connect(self._submit)
        
        self.btn_ask = QPushButton("Ask AI", container)
        self.btn_ask.setObjectName("BtnAsk")
        self.btn_ask.clicked.connect(self._submit)
        
        c_layout.addWidget(self.btn_pdf)
        c_layout.addWidget(self.input_field)
        c_layout.addWidget(self.btn_ask)
        
        main_layout.addWidget(container)

    def set_pdf_mode(self, active: bool, filename: str = ""):
        self.is_pdf_mode = active
        if active:
            doc_name = filename[:20] + "..." if len(filename) > 22 else filename
            self.input_field.setPlaceholderText(f"What would you like to do with '{doc_name}'? (e.g. summarize, explain a section...)")
            self.btn_pdf.setStyleSheet("background-color: #ff3b30; color: white; border-radius: 14px; padding: 6px 12px;")
        else:
            self.input_field.setPlaceholderText("Ask a math/STEM question (e.g. d/dx(x^3 + 2x), integral of sin(x)...)")
            self.btn_pdf.setStyleSheet("background-color: #f2f2f7; color: #ff3b30; border: 1px solid #d1d1d6; border-radius: 14px; padding: 6px 12px;")

    def _submit(self):
        text = self.input_field.text().strip()
        if text:
            self.question_submitted.emit(text)
            self.input_field.clear()
