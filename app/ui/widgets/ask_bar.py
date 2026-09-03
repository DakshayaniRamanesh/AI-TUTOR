"""
Persistent STEM / Math & PDF Question Bar docked at the bottom of the canvas
Monochrome / Technical Aesthetic
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QComboBox
from PyQt6.QtCore import pyqtSignal
from ..theme_manager import ThemeManager
from ..kestrel_theme import MONO_FONT, primary_button_qss, ghost_button_qss


class AskBar(QWidget):
    question_submitted = pyqtSignal(str)
    mode_changed = pyqtSignal(str)  # Emits "classroom" or "study"
    question_with_context_submitted = pyqtSignal(str, str, int, str)
    pdf_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_pdf_mode = False
        self.current_selected_text = ""
        self.current_page_num = None
        self.surrounding_context = ""
        self.doc_filename = ""
        
        self._init_ui()
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme(ThemeManager.instance().current_theme)

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        container = QWidget(self)
        container.setObjectName("AskBarContainer")
        c_layout = QHBoxLayout(container)
        c_layout.setContentsMargins(8, 4, 8, 4)
        c_layout.setSpacing(6)
        
        # PDF upload button
        self.btn_pdf = QPushButton("PDF", container)
        self.btn_pdf.setObjectName("BtnPdf")
        self.btn_pdf.clicked.connect(self.pdf_requested.emit)

        self.input_field = QLineEdit(container)
        self.input_field.setPlaceholderText("Ask AI a question (e.g. 25*14, d/dx(x^3), integral of sin(x)...)")
        self.input_field.returnPressed.connect(self._submit)
        
        self.mode_combo = QComboBox(container)
        self.mode_combo.addItem("Classroom Mode", "classroom")
        self.mode_combo.addItem("Study Mode", "study")
        self.mode_combo.setCurrentIndex(1)  # Default to Study Mode
        self.mode_combo.setToolTip("Classroom Mode: Direct answer only\nStudy Mode: Detailed step-by-step solution")
        self.mode_combo.currentIndexChanged.connect(self._on_combo_mode_changed)
        
        self.btn_ask = QPushButton("ASK AI", container)
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
            self.input_field.setPlaceholderText("Classroom Mode: Ask for direct solutions...")
        else:
            self.input_field.setPlaceholderText("Study Mode: Ask for step-by-step explanations...")
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
        c = ThemeManager.instance().get_colors()

        if active:
            doc_name = filename[:20] + "..." if len(filename) > 22 else filename
            self.input_field.setPlaceholderText(f"Analyze '{doc_name}'...")
            self.btn_pdf.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c['accent']};
                    color: {c['accent_text']};
                    border: 1px solid {c['accent']};
                    border-radius: 2px;
                    font-family: {MONO_FONT};
                    font-size: 11px;
                    font-weight: 700;
                    padding: 4px 8px;
                }}
            """)
        else:
            self.input_field.setPlaceholderText("Ask AI a question (e.g. d/dx(x^3 + 2x), integral of sin(x)...)")
            self.btn_pdf.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {c['text_secondary']};
                    border: 1px solid {c['border_color']};
                    border-radius: 2px;
                    font-family: {MONO_FONT};
                    font-size: 11px;
                    font-weight: 700;
                    padding: 4px 8px;
                }}
                QPushButton:hover {{
                    border-color: {c['accent']};
                    color: {c['text_primary']};
                }}
            """)

    def set_selection_context(self, selected_text: str, page_num: int, surrounding_context: str = ""):
        self.current_selected_text = selected_text
        self.current_page_num = page_num
        self.surrounding_context = surrounding_context
        
        snippet = selected_text[:35].replace('\n', ' ')
        if not snippet:
            snippet = f"Passage on Page {page_num}"
        
        self.input_field.setPlaceholderText(f"Question about [P.{page_num}]: \"{snippet}...\"")
        self.input_field.setFocus()

    def _submit(self):
        text = self.input_field.text().strip()
        
        if self.current_selected_text:
            q_text = text if text else "Explain and solve this selected passage step-by-step."
            self.question_with_context_submitted.emit(q_text, self.current_selected_text, self.current_page_num or 1, self.surrounding_context)
            
            self.current_selected_text = ""
            self.current_page_num = None
            self.surrounding_context = ""
            if self.is_pdf_mode:
                doc_name = self.doc_filename[:20] + "..." if len(self.doc_filename) > 22 else self.doc_filename
                self.input_field.setPlaceholderText(f"Analyze '{doc_name}'...")
        elif text:
            self.question_submitted.emit(text)

        self.input_field.clear()

    def _apply_theme(self, theme_name: str = "light"):
        c = ThemeManager.instance().get_colors()
        self.setStyleSheet(f"""
            QWidget#AskBarContainer {{
                background-color: {c['bg_toolbar']};
                border: 1px solid {c['border_color']};
                border-radius: 4px;
            }}
            QLineEdit {{
                border: none;
                background: transparent;
                font-family: {MONO_FONT};
                font-size: 13px;
                padding-left: 6px;
                color: {c['text_primary']};
            }}
            QComboBox {{
                background-color: {c['bg_card']};
                color: {c['text_primary']};
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                padding: 3px 8px;
                font-family: {MONO_FONT};
                font-size: 11px;
                font-weight: 600;
            }}
            QComboBox:hover {{
                border-color: {c['accent']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 14px;
            }}
            QPushButton#BtnPdf {{
                background-color: transparent;
                color: {c['text_secondary']};
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                font-family: {MONO_FONT};
                font-size: 11px;
                font-weight: 700;
                padding: 4px 8px;
            }}
            QPushButton#BtnPdf:hover {{
                border-color: {c['accent']};
                color: {c['text_primary']};
            }}
            QPushButton#BtnAsk {{
                background-color: {c['accent']};
                color: {c['accent_text']};
                border: 1px solid {c['accent']};
                border-radius: 2px;
                padding: 4px 12px;
                font-family: {MONO_FONT};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
            QPushButton#BtnAsk:hover {{
                background-color: {c['accent_hover']};
            }}
        """)
