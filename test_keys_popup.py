import os
import sys
import subprocess
import requests
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QPushButton, QTextEdit, QLabel, QHBoxLayout, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# Add root to sys.path to find backend
root_dir = os.path.dirname(os.path.abspath(__file__))
sys.path = [root_dir] + [p for p in sys.path if p != root_dir]

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(root_dir, "backend", ".env"))
    load_dotenv(os.path.join(root_dir, ".env"))
except ImportError:
    pass

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
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            self.result_signal.emit("gemini", f"SUCCESS! Response: {text}")
        else:
            self.result_signal.emit("gemini", f"FAILED (Code {resp.status_code}):\n{resp.text}")

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
        
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            self.result_signal.emit("groq", f"SUCCESS! Response: {text}")
        else:
            self.result_signal.emit("groq", f"FAILED (Code {resp.status_code}):\n{resp.text}")

    def test_tectonic(self):
        tectonic_path = os.path.join(root_dir, "tectonic.exe")
        if not os.path.exists(tectonic_path):
            self.result_signal.emit("tectonic", f"ERROR: tectonic.exe not found at {tectonic_path}")
            return
            
        res = subprocess.run([tectonic_path, "--version"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            self.result_signal.emit("tectonic", f"SUCCESS! {res.stdout.strip()}")
        else:
            self.result_signal.emit("tectonic", f"FAILED:\n{res.stderr}")

class TesterWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("API Keys & Engine Diagnostics")
        self.setFixedSize(600, 400)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        title = QLabel("System Diagnostics")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        btn_layout = QHBoxLayout()
        self.btn_gemini = QPushButton("Test Gemini API")
        self.btn_groq = QPushButton("Test Groq API")
        self.btn_tectonic = QPushButton("Test Tectonic")
        
        self.btn_gemini.setMinimumHeight(40)
        self.btn_groq.setMinimumHeight(40)
        self.btn_tectonic.setMinimumHeight(40)
        
        self.btn_gemini.clicked.connect(lambda: self.run_test("gemini"))
        self.btn_groq.clicked.connect(lambda: self.run_test("groq"))
        self.btn_tectonic.clicked.connect(lambda: self.run_test("tectonic"))
        
        btn_layout.addWidget(self.btn_gemini)
        btn_layout.addWidget(self.btn_groq)
        btn_layout.addWidget(self.btn_tectonic)
        
        layout.addLayout(btn_layout)
        
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: Consolas;")
        layout.addWidget(self.log_box)
        
    def run_test(self, target):
        self.log_box.append(f"\n--- Running test: {target.upper()} ---")
        if target == "gemini":
            self.btn_gemini.setEnabled(False)
        elif target == "groq":
            self.btn_groq.setEnabled(False)
        else:
            self.btn_tectonic.setEnabled(False)
            
        self.worker = ApiTester(target)
        self.worker.result_signal.connect(self.on_result)
        self.worker.start()
        
    def on_result(self, target, msg):
        self.log_box.append(msg)
        if target == "gemini":
            self.btn_gemini.setEnabled(True)
        elif target == "groq":
            self.btn_groq.setEnabled(True)
        else:
            self.btn_tectonic.setEnabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TesterWindow()
    window.show()
    sys.exit(app.exec())
