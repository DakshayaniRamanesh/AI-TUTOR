"""
Persistent STEM / Math & PDF Question Bar docked at the bottom of the canvas
Supports Classroom Mode (straight direct answer), Study Mode (elaborate step-by-step solution), PDF Split-Screen RAG mode, and direct passage context replies.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QComboBox
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont


class AskBar(QWidget):
    question_submitted = pyqtSignal(str)
    mode_changed = pyqtSignal(str) # Emits "classroom" or "study"
    question_with_context_submitted = pyqtSignal(str, str, int, str) # user_question, selected_text, page_num, surrounding_context
    pdf_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_pdf_mode = False
        self.current_selected_text = ""
        self.current_page_num = None
        self.surrounding_context = ""
        self.doc_filename = ""
        
        self._init_ui()
        from ..theme_manager import ThemeManager
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme(ThemeManager.instance().current_theme)

    def _init_ui(self):
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
        self.input_field.setPlaceholderText("Ask a question (e.g. 25*14, d/dx(x^3), integral of sin(x)...)")
        self.input_field.returnPressed.connect(self._submit)
        
        self.mode_combo = QComboBox(container)
        self.mode_combo.addItem("🏫 Classroom Mode", "classroom")
        self.mode_combo.addItem("📖 Study Mode", "study")
        self.mode_combo.setCurrentIndex(1) # Default to Study Mode
        self.mode_combo.setToolTip("🏫 Classroom Mode: Straight, direct answer only (No elaboration/waiting)\n📖 Study Mode: Detailed step-by-step solution")
        self.mode_combo.currentIndexChanged.connect(self._on_combo_mode_changed)
        
        self.btn_ask = QPushButton("Ask AI", container)
        self.btn_ask.setObjectName("BtnAsk")
        self.btn_ask.clicked.connect(self._submit)
        
        c_layout.addWidget(self.btn_pdf)
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

    def set_pdf_mode(self, active: bool, filename: str = ""):
        self.is_pdf_mode = active
        self.doc_filename = filename
        self.current_selected_text = ""
        self.current_page_num = None

        if active:
            doc_name = filename[:20] + "..." if len(filename) > 22 else filename
            self.input_field.setPlaceholderText(f"What would you like to do with '{doc_name}'? (e.g. summarize, explain a section...)")
            self.btn_pdf.setStyleSheet("background-color: #ff3b30; color: white; border-radius: 14px; padding: 6px 12px;")
        else:
            self.input_field.setPlaceholderText("Ask a math/STEM question (e.g. d/dx(x^3 + 2x), integral of sin(x)...)")
            self.btn_pdf.setStyleSheet("background-color: #f2f2f7; color: #ff3b30; border: 1px solid #d1d1d6; border-radius: 14px; padding: 6px 12px;")

    def set_selection_context(self, selected_text: str, page_num: int, surrounding_context: str = ""):
        """
        Links highlighted text selection from PDF to AskBar and focuses input line edit.
        """
        self.current_selected_text = selected_text
        self.current_page_num = page_num
        self.surrounding_context = surrounding_context
        
        snippet = selected_text[:35].replace('\n', ' ')
        if not snippet:
            snippet = f"Passage on Page {page_num}"
        
        self.input_field.setPlaceholderText(f"Ask a question/doubt about [Page {page_num}]: \"{snippet}...\"")
        self.input_field.setFocus()

    def _submit(self):
        text = self.input_field.text().strip()
        
        if self.current_selected_text:
            # If user submitted without typing custom question, default to explaining selection
            q_text = text if text else "Explain and solve this selected passage step-by-step."
            self.question_with_context_submitted.emit(q_text, self.current_selected_text, self.current_page_num or 1, self.surrounding_context)
            
            # Reset selection context
            self.current_selected_text = ""
            self.current_page_num = None
            self.surrounding_context = ""
            if self.is_pdf_mode:
                doc_name = self.doc_filename[:20] + "..." if len(self.doc_filename) > 22 else self.doc_filename
                self.input_field.setPlaceholderText(f"Ask a question about '{doc_name}'...")
        elif text:
            self.question_submitted.emit(text)

        self.input_field.clear()

    def _apply_theme(self, theme_name: str = "light"):
        from ..theme_manager import ThemeManager
        c = ThemeManager.instance().get_colors()
        self.setStyleSheet(f"""
            QWidget#AskBarContainer {{
                background-color: {c['bg_toolbar']};
                border: 1px solid {c['border_color']};
                border-radius: 20px;
            }}
            QLineEdit {{
                border: none;
                background: transparent;
                font-size: 14px;
                padding-left: 8px;
                color: {c['text_primary']};
            }}
            QComboBox {{
                background-color: {c['bg_card']};
                color: {c['text_primary']};
                border: 1px solid {c['border_color']};
                border-radius: 12px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 600;
            }}
            QComboBox:hover {{
                background-color: {c['panel_card_bg']};
                border-color: {c['accent']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 16px;
            }}
            QPushButton#BtnAsk {{
                background-color: {c['accent']};
                color: white;
                border: none;
                border-radius: 14px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton#BtnAsk:hover {{
                background-color: {c['accent_hover']};
            }}
        """)
