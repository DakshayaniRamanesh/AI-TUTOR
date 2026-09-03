"""
Latex Client
Connects the frontend to the backend LaTeX generation endpoints.
"""

import os
import sys
import uuid
import requests
import base64
from PyQt6.QtCore import QThread, pyqtSignal

# Ensure root workspace is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

LOCAL_SERVER_URL = os.getenv("BACKEND_URL", f"http://localhost:{os.getenv('PORT', '8888')}")
MODAL_ENDPOINT_URL = os.getenv("MODAL_URL", "https://dakshayaniramanesh--manim-app-generate.modal.run")
# Replace modal url to the specific endpoints for latex if needed. 
# We'll use local server URL for now, modal fallback can be added if endpoints match.

def request_latex_generation(image_b64: str, template_type: str,  mode: str = "study", classroom_action: str= "Solve Question") -> str:
    """
    Submits a LaTeX generation request.
    """
    job_id = f"latex_{uuid.uuid4().hex[:8]}"
    
    # 1. Try local server
    try:
        resp = requests.post(
            f"{LOCAL_SERVER_URL}/generate_latex",
            data={"image_b64": image_b64, "template_type": template_type, "mode": mode, "classroom_action": classroom_action},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("job_id", job_id)
    except Exception:
        pass

    # 2. Try Modal web endpoint if local fails
    try:
        # Using the same domain but /generate_latex path 
        modal_url = MODAL_ENDPOINT_URL.replace("/generate", "/generate_latex")
        resp = requests.post(
            modal_url,
            json={"job_id": job_id, "image_b64": image_b64, "template_type": template_type},
            timeout=10
        )
        if resp.status_code in [200, 201, 202]:
            data = resp.json()
            return data.get("job_id", job_id)
    except Exception as e:
        print(f"Modal request failed: {e}")

    return job_id


def compile_custom_latex_pdf(latex_code: str, target_path: str) -> tuple[bool, str]:
    """
    Submits raw LaTeX code to backend /compile_pdf endpoint on demand, and saves the result to target_path.
    """
    try:
        resp = requests.post(
            f"{LOCAL_SERVER_URL}/compile_pdf",
            json={"latex_code": latex_code},
            timeout=60
        )
        if resp.status_code == 200:
            data = resp.json()
            pdf_b64 = data.get("pdf_b64")
            if pdf_b64:
                pdf_bytes = base64.b64decode(pdf_b64)
                os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
                with open(target_path, "wb") as f:
                    f.write(pdf_bytes)
                return True, target_path
            return False, "No PDF data returned from compiler."
        else:
            err_msg = resp.json().get("message", "Compilation failed")
            return False, err_msg
    except Exception as e:
        return False, str(e)


class LatexPollWorker(QThread):
    """
    Background worker that polls the LaTeX generation pipeline asynchronously.
    """
    status_updated = pyqtSignal(str, str, int) # job_id, stage, progress_percent
    pdf_ready = pyqtSignal(str, str, str)      # job_id, pdf_url (if local), pdf_b64 (if modal)
    latex_ready = pyqtSignal(str, str)         # job_id, latex_code
    pdf_failed = pyqtSignal(str, str)          # job_id, error_message

    def __init__(self, job_id: str, parent=None):
        super().__init__(parent)
        self.job_id = job_id
        self._running = True

    def run(self):
        attempts = 0
        max_attempts = 1200
        
        while self._running and attempts < max_attempts:
            attempts += 1
            self.msleep(1500)

            # Check local server
            try:
                r = requests.get(f"{LOCAL_SERVER_URL}/latex_status/{self.job_id}", timeout=2)
                if r.status_code == 200:
                    data = r.json()
                    status = data.get("status", "processing")
                    pdf_url = data.get("pdf_url")
                    pdf_b64 = data.get("pdf_b64")
                    latex_code = data.get("latex_code")
                    progress = data.get("progress_percentage", min(95, attempts * 5))
                    stage = data.get("step", "Processing")

                    self.status_updated.emit(self.job_id, f"LaTeX: {stage}", int(progress))

                    if status in ["completed", "done", "success"]:
                        if latex_code:
                            self.latex_ready.emit(self.job_id, latex_code)
                        if pdf_url or pdf_b64:
                            self.pdf_ready.emit(self.job_id, pdf_url or "", pdf_b64 or "")
                        return
                    elif status == "error":
                        err_msg = data.get("error_message", "LaTeX pipeline error")
                        self.pdf_failed.emit(self.job_id, err_msg)
                        return
                    continue
            except Exception:
                try:
                    modal_url = MODAL_ENDPOINT_URL.replace("/generate", "/latex_status")
                    r = requests.get(f"{modal_url}?job_id={self.job_id}", timeout=2)
                    if r.status_code == 200:
                        data = r.json()
                        status = data.get("status", "processing")
                        pdf_b64 = data.get("pdf_b64")
                        latex_code = data.get("latex_code")
                        progress = data.get("progress_percentage", min(95, attempts * 5))
                        stage = data.get("step", "Processing")
                        
                        self.status_updated.emit(self.job_id, f"LaTeX: {stage}", int(progress))
                        
                        if status in ["completed", "done", "success"]:
                            if latex_code:
                                self.latex_ready.emit(self.job_id, latex_code)
                            if pdf_b64:
                                self.pdf_ready.emit(self.job_id, "", pdf_b64)
                            return
                        elif status == "error":
                            err_msg = data.get("error_message", "LaTeX pipeline error")
                            self.pdf_failed.emit(self.job_id, err_msg)
                            return
                        continue
                except Exception:
                    pass

            stage_name = "Transcribing & Structuring" if attempts < 10 else "Processing LaTeX"
            self.status_updated.emit(self.job_id, f"📝 {stage_name} ({attempts*2}s)...", min(95, attempts * 3))

        self.pdf_failed.emit(self.job_id, "Timeout while generating LaTeX document.")

