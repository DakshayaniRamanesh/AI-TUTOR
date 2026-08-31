import requests
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PyQt6.QtCore import Qt
from ..theme_manager import ThemeManager
from ..kestrel_theme import MONO_FONT, ghost_button_qss, primary_button_qss


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings & Diagnostics")
        self.resize(420, 320)
        c = ThemeManager.instance().get_colors()

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border_color']};
            }}
            QLabel {{
                color: {c['text_primary']};
                font-family: {MONO_FONT};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        
        title = QLabel("SYSTEM DIAGNOSTICS & APIS")
        title.setStyleSheet(f"font-size: 13px; font-weight: 800; letter-spacing: 1px; color: {c['text_primary']}; font-family: {MONO_FONT};")
        layout.addWidget(title)

        self._add_diagnostic_row(layout, "Groq API (Structure Agent)", "/api/diagnostics/groq")
        self._add_diagnostic_row(layout, "Gemini API (Vision/RAG)", "/api/diagnostics/gemini")
        self._add_diagnostic_row(layout, "Tectonic Engine (LaTeX Compiler)", "/api/diagnostics/tectonic")

        layout.addStretch()

        btn_close = QPushButton("CLOSE")
        btn_close.setStyleSheet(ghost_button_qss(c))
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)

    def _add_diagnostic_row(self, layout: QVBoxLayout, label_text: str, endpoint: str):
        c = ThemeManager.instance().get_colors()
        row = QFrame()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        
        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"font-size: 12px; font-family: {MONO_FONT}; color: {c['text_primary']};")
        
        btn_test = QPushButton("TEST")
        btn_test.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['bg_card']};
                color: {c['text_primary']};
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                font-family: {MONO_FONT};
                font-size: 11px;
                font-weight: 600;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                border-color: {c['accent']};
                background-color: {c['panel_card_bg']};
            }}
        """)
        status_lbl = QLabel("")
        status_lbl.setFixedWidth(24)

        btn_test.clicked.connect(lambda: self._run_test(btn_test, status_lbl, endpoint))
        
        row_layout.addWidget(lbl)
        row_layout.addStretch()
        row_layout.addWidget(status_lbl)
        row_layout.addWidget(btn_test)
        
        layout.addWidget(row)

    def _run_test(self, button: QPushButton, status_lbl: QLabel, endpoint: str):
        button.setText("...")
        button.setEnabled(False)
        status_lbl.setText("")
        
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        
        try:
            resp = requests.get(f"http://127.0.0.1:8000{endpoint}", timeout=10)
            if resp.status_code == 200 and resp.json().get("status") == "ok":
                status_lbl.setText("✓")
            else:
                status_lbl.setText("✕")
        except Exception:
            status_lbl.setText("✕")
        finally:
            button.setText("TEST")
            button.setEnabled(True)
