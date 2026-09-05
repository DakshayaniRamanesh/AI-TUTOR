"""
Latex Client
Connects the frontend to the backend LaTeX generation endpoints,
with an instant, resilient in-process local pipeline fallback.
"""

import os
import sys
import uuid
import requests
import base64
from PyQt6.QtCore import QThread, pyqtSignal

# Ensure root workspace directory is on Python path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

LOCAL_SERVER_URL = os.getenv("BACKEND_URL", f"http://localhost:{os.getenv('PORT', '8888')}")
MODAL_ENDPOINT_URL = os.getenv("MODAL_URL", "https://dakshayaniramanesh--manim-app-generate.modal.run")


def request_latex_generation(image_b64: str, template_type: str, mode: str = "study", classroom_action: str = "Solve Question") -> tuple[str, bool]:
    """
    Submits a LaTeX generation request.
    Returns (job_id, is_local_direct).
    """
    job_id = f"latex_{uuid.uuid4().hex[:8]}"

    # 1. Try local HTTP server first
    try:
        resp = requests.post(
            f"{LOCAL_SERVER_URL}/generate_latex",
            data={"image_b64": image_b64, "template_type": template_type, "mode": mode, "classroom_action": classroom_action},
            timeout=1.5
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("job_id", job_id), False
    except Exception:
        pass

    # 2. Try Modal web endpoint if local server is not running
    try:
        modal_url = MODAL_ENDPOINT_URL.replace("/generate", "/generate_latex")
        resp = requests.post(
            modal_url,
            json={"job_id": job_id, "image_b64": image_b64, "template_type": template_type},
            timeout=2.0
        )
        if resp.status_code in [200, 201, 202]:
            data = resp.json()
            return data.get("job_id", job_id), False
    except Exception:
        pass

    # 3. Fallback to direct in-process pipeline
    return job_id, True


def compile_custom_latex_pdf(latex_code: str, target_path: str) -> tuple[bool, str]:
    """
    Submits raw LaTeX code to compiler (via HTTP or in-process Tectonic binary), and saves result to target_path.
    """
    # 1. Try local server endpoint
    try:
        resp = requests.post(
            f"{LOCAL_SERVER_URL}/compile_pdf",
            json={"latex_code": latex_code},
            timeout=10
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
    except Exception:
        pass

    # 2. Fallback: Run local tectonic.exe binary directly
    try:
        import tempfile
        import subprocess
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        local_tectonic = os.path.join(project_root, "tectonic.exe")
        tectonic_cmd = local_tectonic if os.path.exists(local_tectonic) else "tectonic"

        temp_dir = tempfile.mkdtemp()
        tex_path = os.path.join(temp_dir, "document.tex")
        pdf_path = os.path.join(temp_dir, "document.pdf")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_code)

        res = subprocess.run([tectonic_cmd, tex_path], cwd=temp_dir, capture_output=True, text=True, timeout=60)
        if res.returncode == 0 and os.path.exists(pdf_path):
            os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
            import shutil
            shutil.copy2(pdf_path, target_path)
            return True, target_path
        else:
            err = res.stderr or res.stdout or "Compilation failed"
            return False, err
    except Exception as e:
        return False, str(e)


class LatexPollWorker(QThread):
    """
    Background worker that runs or polls the LaTeX generation pipeline asynchronously.
    """
    status_updated = pyqtSignal(str, str, int) # job_id, stage, progress_percent
    pdf_ready = pyqtSignal(str, str, str)      # job_id, pdf_url (if local), pdf_b64 (if modal)
    latex_ready = pyqtSignal(str, str)         # job_id, latex_code
    pdf_failed = pyqtSignal(str, str)          # job_id, error_message

    def __init__(
        self,
        job_id: str,
        image_b64: str = "",
        template_type: str = "Homework",
        mode: str = "study",
        classroom_action: str = "Solve Question",
        is_local_direct: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self.job_id = job_id
        self.image_b64 = image_b64
        self.template_type = template_type
        self.mode = mode
        self.classroom_action = classroom_action
        self.is_local_direct = is_local_direct
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        if self.is_local_direct:
            self._run_direct_local()
            return

        attempts = 0
        max_attempts = 120
        
        while self._running and attempts < max_attempts:
            attempts += 1
            self.msleep(1200)

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
                # If server went offline, switch to direct execution
                if attempts > 3:
                    self._run_direct_local()
                    return

            stage_name = "Transcribing & Structuring" if attempts < 10 else "Processing LaTeX"
            self.status_updated.emit(self.job_id, f"{stage_name} ({attempts*2}s)...", min(95, attempts * 3))

        # Fallback to direct local if polling timed out
        if self._running:
            self._run_direct_local()

    def _run_direct_local(self):
        """Executes the pipeline directly in-process when the backend server is not running."""
        try:
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
            # CRITICAL: Ensure root_dir is FIRST on sys.path so root 'backend' wins over app/backend
            sys.path = [root_dir] + [p for p in sys.path if p != root_dir]

            # Use importlib with absolute file paths to bypass the app/backend vs backend namespace collision
            import importlib.util

            def _load_module(name, filepath):
                """Load a module from absolute path and register it in sys.modules."""
                if name in sys.modules:
                    return sys.modules[name]
                spec = importlib.util.spec_from_file_location(name, filepath)
                mod = importlib.util.module_from_spec(spec)
                sys.modules[name] = mod
                spec.loader.exec_module(mod)
                return mod

            # Load models
            _models = _load_module(
                "_kestrel_latex_models",
                os.path.join(root_dir, "backend", "video_generation", "models.py")
            )
            LatexJob = _models.LatexJob
            JobStatus = _models.JobStatus

            # Load agents (latex_agents imports from backend.video_generation.models)
            _agents = _load_module(
                "_kestrel_latex_agents",
                os.path.join(root_dir, "backend", "video_generation", "agents", "latex_agents.py")
            )

            # Load graph pipeline
            _graph = _load_module(
                "_kestrel_latex_graph",
                os.path.join(root_dir, "backend", "math_engine", "latex_graph.py")
            )
            LatexGenerationPipeline = _graph.LatexGenerationPipeline

            self.status_updated.emit(self.job_id, "LaTeX: Transcribing handwriting...", 20)

            job = LatexJob(
                job_id=self.job_id,
                image_b64=self.image_b64,
                template_type=self.template_type,
                mode=self.mode,
                classroom_action=self.classroom_action
            )

            pipeline = LatexGenerationPipeline()
            self.status_updated.emit(self.job_id, "LaTeX: Structuring & Solving Math...", 50)
            final_job = pipeline.run_pipeline(job)

            if final_job.status == JobStatus.ERROR:
                self.pdf_failed.emit(self.job_id, final_job.error_message or "LaTeX generation failed.")
                return

            latex_code = final_job.final_tex_code or final_job.structured_latex or final_job.raw_transcription or ""
            self.status_updated.emit(self.job_id, "LaTeX: Generated", 100)

            if latex_code:
                self.latex_ready.emit(self.job_id, latex_code)

            if final_job.pdf_path and os.path.exists(final_job.pdf_path):
                try:
                    with open(final_job.pdf_path, "rb") as pf:
                        pdf_b64 = base64.b64encode(pf.read()).decode()
                    self.pdf_ready.emit(self.job_id, "", pdf_b64)
                except Exception:
                    pass
        except Exception as e:
            import traceback
            self.pdf_failed.emit(self.job_id, f"In-process LaTeX generation error: {str(e)}\n{traceback.format_exc()}")

