"""
Persistent STEM / Math Question Bar docked at the bottom of the canvas
Supports Classroom Mode (straight direct answer) and Study Mode (elaborate step-by-step solution)
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QComboBox
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont

class AskBar(QWidget):
    question_submitted = pyqtSignal(str)
    mode_changed = pyqtSignal(str) # Emits "classroom" or "study"

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
            QComboBox {
                background-color: #f2f2f7;
                color: #1c1c1e;
                border: 1px solid #d1d1d6;
                border-radius: 12px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 600;
            }
            QComboBox:hover {
                background-color: #e5e5ea;
                border-color: #007aff;
            }
            QComboBox::drop-down {
                border: none;
                width: 16px;
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
        self.input_field.setPlaceholderText("Ask a question (e.g. 25*14, d/dx(x^3), integral of sin(x)...)")
        self.input_field.returnPressed.connect(self._submit)
        
        self.mode_combo = QComboBox(container)
        self.mode_combo.addItem("🏫 Classroom Mode", "classroom")
        self.mode_combo.addItem("📖 Study Mode", "study")
        self.mode_combo.setCurrentIndex(1) # Default to Study Mode
        self.mode_combo.setToolTip("🏫 Classroom Mode: Straight, direct answer only (No elaboration/waiting)\n📖 Study Mode: Detailed step-by-step solution")
        self.mode_combo.currentIndexChanged.connect(self._on_combo_mode_changed)
        
        self.btn_ask = QPushButton("Ask AI", container)
        self.btn_ask.clicked.connect(self._submit)
        
        c_layout.addWidget(self.input_field)
        c_layout.addWidget(self.mode_combo)
        c_layout.addWidget(self.btn_ask)
        
        main_layout.addWidget(container)

    def _on_combo_mode_changed(self, index: int):
        mode = self.get_mode()
        if mode == "classroom":
            self.input_field.setPlaceholderText("Classroom Mode: Ask for straight, direct answers...")
        else:
            self.input_field.setPlaceholderText("Study Mode: Ask for step-by-step detailed explanations...")
        self.mode_changed.emit(mode)

    def get_mode(self) -> str:
        return self.mode_combo.currentData() or "study"

    def set_mode(self, mode: str):
        idx = 0 if mode == "classroom" else 1
        self.mode_combo.setCurrentIndex(idx)

    def _submit(self):
        text = self.input_field.text().strip()
        if text:
            self.question_submitted.emit(text)
            self.input_field.clear()

