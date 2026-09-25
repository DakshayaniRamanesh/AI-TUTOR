import os
import requests
import subprocess
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from ..theme_manager import ThemeManager
from ..kestrel_theme import MONO_FONT, ghost_button_qss, primary_button_qss
from shared.ai_client import ai_client

class ApiTester(QThread):
    result_signal = pyqtSignal(str, str)

    def __init__(self, target, parent=None):
        super().__init__(parent)
        self.target = target

    def run(self):
        try:
            if self.target == "gemini":
                self.test_gemini()
            elif self.target == "groq":
                self.test_groq()
            elif self.target == "tectonic":
                self.test_tectonic()
        except Exception as e:
            self.result_signal.emit(self.target, f"ERROR:\n{str(e)}")

    def test_gemini(self):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            self.result_signal.emit("gemini", "ERROR: GEMINI_API_KEY not found in .env")
            return
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": "Reply with only the word SUCCESS."}]}]
        }
        try:
            resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                self.result_signal.emit("gemini", f"SUCCESS! Response: {text}")
            else:
                self.result_signal.emit("gemini", f"FAILED (Code {resp.status_code}):\n{resp.text}")
        except Exception as e:
            self.result_signal.emit("gemini", f"FAILED:\n{e}")


    def test_groq(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            self.result_signal.emit("groq", "ERROR: GROQ_API_KEY not found in .env")
            return
            
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "qwen/qwen3.8-27b",
            "messages": [{"role": "user", "content": "Reply with only the word SUCCESS."}],
            "max_tokens": 10
        }
        
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                self.result_signal.emit("groq", f"SUCCESS! Response: {text}")
            else:
                self.result_signal.emit("groq", f"FAILED (Code {resp.status_code}):\n{resp.text}")
        except Exception as e:
            self.result_signal.emit("groq", f"FAILED:\n{e}")

    def test_tectonic(self):
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        tectonic_path = os.path.join(root_dir, "tectonic.exe")
        
        if not os.path.exists(tectonic_path):
            self.result_signal.emit("tectonic", f"ERROR: tectonic.exe not found at {tectonic_path}")
            return
            
        try:
            res = subprocess.run([tectonic_path, "--version"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                self.result_signal.emit("tectonic", f"SUCCESS! {res.stdout.strip()}")
            else:
                self.result_signal.emit("tectonic", f"FAILED:\n{res.stderr}")
        except Exception as e:
            self.result_signal.emit("tectonic", f"FAILED:\n{e}")


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API Keys & Engine Diagnostics")
        self.resize(600, 450)
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
            QTextEdit {{
                background-color: {c.get('panel_card_bg', '#1e1e1e')};
                color: #10b981; 
                border: 1px solid {c['border_color']};
                font-family: {MONO_FONT};
                font-size: 13px;
                padding: 10px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        
        title = QLabel("System Diagnostics")
        title.setStyleSheet(f"font-size: 16px; font-weight: 800; letter-spacing: 1px; color: {c['text_primary']};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        btn_layout = QHBoxLayout()
        self.btn_gemini = QPushButton("Test Gemini API")
        self.btn_groq = QPushButton("Test Groq API")
        self.btn_tectonic = QPushButton("Test Tectonic")
        self.btn_active_model = QPushButton("Test Active Kestrel Model")
        
        self.btn_gemini.setStyleSheet(primary_button_qss(c))
        self.btn_groq.setStyleSheet(primary_button_qss(c))
        self.btn_tectonic.setStyleSheet(primary_button_qss(c))
        self.btn_active_model.setStyleSheet(primary_button_qss(c))
        
        self.btn_gemini.setMinimumHeight(40)
        self.btn_groq.setMinimumHeight(40)
        self.btn_tectonic.setMinimumHeight(40)
        
        self.btn_gemini.clicked.connect(lambda: self.run_test("gemini"))
        self.btn_groq.clicked.connect(lambda: self.run_test("groq"))
        self.btn_tectonic.clicked.connect(lambda: self.run_test("tectonic"))
        self.btn_active_model.clicked.connect(lambda: self.run_test("active_model"))
        
        btn_layout.addWidget(self.btn_gemini)
        btn_layout.addWidget(self.btn_groq)
        btn_layout.addWidget(self.btn_tectonic)
        layout.addLayout(btn_layout)
        layout.addWidget(self.btn_active_model)
        
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Click a button above to run diagnostics...")
        layout.addWidget(self.log_box)

        btn_close = QPushButton("CLOSE")
        btn_close.setStyleSheet(ghost_button_qss(c))
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)

    def run_test(self, target):
        self.log_box.append(f"\n--- Running test: {target.upper()} ---")
        if target == "active_model":
            from app.workers.model_readiness_worker import ModelReadinessWorker
            self.btn_active_model.setEnabled(False)
            self.btn_active_model.setText("TESTING COMPLETE PIPELINE...")
            self.model_worker = ModelReadinessWorker(self)
            self.model_worker.finished.connect(self._on_model_readiness_finished)
            self.model_worker.start()
            return
        if target == "gemini":
            self.btn_gemini.setEnabled(False)
            self.btn_gemini.setText("TESTING...")
        elif target == "groq":
            self.btn_groq.setEnabled(False)
            self.btn_groq.setText("TESTING...")
        else:
            self.btn_tectonic.setEnabled(False)
            self.btn_tectonic.setText("TESTING...")
            
        self.worker = ApiTester(target, self)
        self.worker.result_signal.connect(self.on_result)
        self.worker.start()
        
    def on_result(self, target, msg):
        self.log_box.append(msg)
        if target == "gemini":
            self.btn_gemini.setEnabled(True)
            self.btn_gemini.setText("Test Gemini API")
        elif target == "groq":
            self.btn_groq.setEnabled(True)
            self.btn_groq.setText("Test Groq API")
        else:
            self.btn_tectonic.setEnabled(True)
            self.btn_tectonic.setText("Test Tectonic")

    def _on_model_readiness_finished(self, result: dict):
        self.btn_active_model.setEnabled(True)
        self.btn_active_model.setText("Test Active Kestrel Model")
        state = "READY" if result.get("overall_ready") else "NOT READY"
        self.log_box.append(f"Active model: {result.get('provider')} / {result.get('model_id')} — {state}")
        for name, details in result.get("tests", {}).items():
            mark = "PASS" if details.get("pass") else "FAIL"
            error = f" — {details.get('error')}" if details.get("error") else ""
            self.log_box.append(f"  {mark}: {name} ({details.get('latency', 0):.2f}s){error}")
