import requests
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import qtawesome as qta

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings & Diagnostics")
        self.resize(400, 300)
        self.setStyleSheet("""
        
            QDialog {
                background-color: #f2f2f7;
            }
            QLabel {
                color: #1c1c1e;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
                color: #1c1c1e;
            }
            QPushButton:hover {
                background-color: #e5e5ea;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        title = QLabel("API Integrations Test")
        title.setFont(QFont("-apple-system", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        self._add_diagnostic_row(layout, "Groq API (Structure Agent)", "/api/diagnostics/groq")
        self._add_diagnostic_row(layout, "Gemini API (Vision/RAG)", "/api/diagnostics/gemini")
        self._add_diagnostic_row(layout, "Tectonic Engine (LaTeX Compiler)", "/api/diagnostics/tectonic")

        layout.addStretch()

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)

    def _add_diagnostic_row(self, layout: QVBoxLayout, label_text: str, endpoint: str):
        row = QFrame()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        
        lbl = QLabel(label_text)
        lbl.setFont(QFont("-apple-system", 12))
        
        btn_test = QPushButton("Test Connection")
        status_lbl = QLabel("")
        status_lbl.setFixedWidth(24)

        btn_test.clicked.connect(lambda: self._run_test(btn_test, status_lbl, endpoint))
        
        row_layout.addWidget(lbl)
        row_layout.addStretch()
        row_layout.addWidget(status_lbl)
        row_layout.addWidget(btn_test)
        
        layout.addWidget(row)

    def _run_test(self, button: QPushButton, status_lbl: QLabel, endpoint: str):
        button.setText("Testing...")
        button.setEnabled(False)
        status_lbl.setText("")
        
        # We use QApplication.processEvents to force UI update since requests.get is blocking
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        
        try:
            resp = requests.get(f"http://127.0.0.1:8000{endpoint}", timeout=10)
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            if resp.status_code == 200 and data.get("status") == "ok":
                status_lbl.setText("✅")
                status_lbl.setToolTip(data.get("message", "Connected successfully"))
            else:
                msg = data.get("message", f"HTTP {resp.status_code}: {resp.text}")
                status_lbl.setText("❌")
                status_lbl.setToolTip(msg)
        except Exception as e:
            status_lbl.setText("❌")
            status_lbl.setToolTip(f"Connection failed: {str(e)}")
        finally:
            button.setText("Test Connection")
            button.setEnabled(True)
