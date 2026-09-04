"""
Manim AI Video Generator Integration Client (Modal Cloud GPU + Local Pipeline).

The client now sends the same logical request contract to local and Modal
backends, including optional structured whiteboard selection context.
"""

import base64
import json
import os
import sys
import uuid
import requests
from PyQt6.QtCore import QThread, pyqtSignal

# Ensure root workspace directory is on Python path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

LOCAL_SERVERS = [
    os.getenv("BACKEND_URL", "").rstrip("/"),
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:8888",
    "http://localhost:8888"
]
LOCAL_SERVERS = [s for s in LOCAL_SERVERS if s]

MODAL_ENDPOINT_URL = os.getenv("MODAL_URL", "https://dakshayaniramanesh--manim-app-generate.modal.run")

_PENDING_JOBS: dict[str, dict] = {}


def _get_active_server() -> str:
    for s in LOCAL_SERVERS:
        try:
            r = requests.get(f"{s}/docs", timeout=0.8)
            if r.status_code in [200, 404]:
                return s
        except Exception:
            continue
    return LOCAL_SERVERS[0] if LOCAL_SERVERS else "http://localhost:8000"


def request_video_generation(
    selected_text: str,
    pdf_path: str = None,
    page_range: str = "",
    emphasis_note: str = "",
    output_type: str = "video",
    subject_id: str = "",
    selection_payload: dict | None = None,
) -> str:
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    selection_payload = selection_payload or {}

    _PENDING_JOBS[job_id] = {
        "prompt": selected_text,
        "pdf_path": pdf_path,
        "page_range": page_range,
        "emphasis_note": emphasis_note,
        "output_type": output_type,
        "subject_id": subject_id,
        "selection_payload": selection_payload,
        "is_local_direct": True
    }

    # 1. Try local server
    for server_url in LOCAL_SERVERS:
        try:
            files = None
            file_handle = None
            if pdf_path and os.path.exists(pdf_path):
                file_handle = open(pdf_path, "rb")
                files = {"pdf": file_handle}
            try:
                resp = requests.post(
                    f"{server_url}/generate",
                    data={
                        "prompt": selected_text,
                        "page_range": page_range,
                        "emphasis_note": emphasis_note,
                        "output_type": output_type,
                        "subject_id": subject_id,
                        "selection_json": json.dumps(selection_payload, separators=(",", ":")),
                    },
                    files=files,
                    timeout=2.5,
                )
            finally:
                if file_handle:
                    file_handle.close()
            if resp.status_code in [200, 201, 202]:
                data = resp.json()
                ret_id = data.get("job_id", job_id)
                _PENDING_JOBS[ret_id] = _PENDING_JOBS.get(job_id, {})
                _PENDING_JOBS[ret_id]["is_local_direct"] = False
                _PENDING_JOBS[ret_id]["server_url"] = server_url
                return ret_id
        except Exception:
            continue

    # 2. Try Modal Cloud fallback
    try:
        pdf_b64 = ""
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                pdf_b64 = base64.b64encode(f.read()).decode("ascii")
        resp = requests.post(
            MODAL_ENDPOINT_URL,
            json={
                "job_id": job_id,
                "prompt": selected_text,
                "pdf_bytes": pdf_b64,
                "page_range": page_range,
                "emphasis_note": emphasis_note,
                "output_type": output_type,
                "subject_id": subject_id,
                "board_selection": selection_payload,
            },
            timeout=3.5,
        )
        if resp.status_code in [200, 201, 202]:
            data = resp.json()
            ret_id = data.get("job_id", job_id)
            _PENDING_JOBS[ret_id] = _PENDING_JOBS.get(job_id, {})
            _PENDING_JOBS[ret_id]["is_local_direct"] = False
            _PENDING_JOBS[ret_id]["server_url"] = MODAL_ENDPOINT_URL
            return ret_id
    except Exception:
        pass

    # No backend server running: will run in-process directly in worker
    return job_id


class ManimVideoPollWorker(QThread):
    """Executes or polls video generation without blocking the Qt event loop."""

    status_updated = pyqtSignal(str, str, int)
    video_ready = pyqtSignal(str, str)
    video_failed = pyqtSignal(str, str)

    def __init__(self, job_id: str, prompt: str, parent=None):
        super().__init__(parent)
        self.job_id = job_id
        self.prompt = prompt
        self._running = True

    def run(self):
        job_info = _PENDING_JOBS.get(self.job_id, {})
        is_direct = job_info.get("is_local_direct", True)
        server_url = job_info.get("server_url") or _get_active_server()

        # If no backend server responded at startup, execute the pipeline directly in-process
        if is_direct:
            self._run_direct_local(job_info)
            return

        attempts = 0
        max_attempts = 120
        while self._running and attempts < max_attempts:
            attempts += 1
            self.msleep(1500)
            try:
                r = requests.get(f"{server_url}/status/{self.job_id}", timeout=2.5)
                if r.status_code == 200:
                    data = r.json()
                    status = data.get("status", "processing")
                    video_url = data.get("video_url")
                    video_local_path = data.get("video_local_path")
                    progress = data.get("progress_percentage", min(95, attempts * 5))
                    stage = data.get("step", "Rendering Manim 2D Animation")
                    self.status_updated.emit(self.job_id, f"Manim: {stage}", int(progress))
                    if status in ["completed", "done", "success"]:
                        final_url = video_local_path if (video_local_path and os.path.exists(video_local_path)) else video_url
                        if final_url:
                            self.video_ready.emit(self.job_id, final_url)
                            return
                    elif status == "error":
                        self.video_failed.emit(self.job_id, data.get("error_message", "Manim pipeline error"))
                        return
                    continue
            except Exception:
                pass

            # If server dropped out after 10 failed connection attempts, fall back to direct local run
            if attempts > 10:
                print("[VideoClient] Backend server unreachable, falling back to in-process pipeline.")
                self._run_direct_local(job_info)
                return

            self.status_updated.emit(self.job_id, "Connecting to Video Engine...", min(40, attempts * 4))

        self._run_direct_local(job_info)

    def _run_direct_local(self, job_info: dict):
        """Executes the VideoGenerationPipeline directly in-process."""
        try:
            root_dir = ROOT_DIR
            if root_dir not in sys.path:
                sys.path.insert(0, root_dir)

            self.status_updated.emit(self.job_id, "Planning animation story & visual structure...", 20)

            from backend.video_generation.models import VideoJob, JobStatus
            from backend.video_generation.graph import VideoGenerationPipeline

            prompt_text = self.prompt or job_info.get("prompt", "")
            job = VideoJob(
                job_id=self.job_id,
                pdf_path=job_info.get("pdf_path") or "",
                user_prompt=prompt_text,
                document_text="",
                page_range=job_info.get("page_range") or None,
                emphasis_note=job_info.get("emphasis_note") or None,
                output_type=job_info.get("output_type", "video"),
                subject_id=job_info.get("subject_id") or None,
                board_selection=job_info.get("selection_payload") or {}
            )

            self.status_updated.emit(self.job_id, "Generating Manim 2D animation code...", 50)

            pipeline = VideoGenerationPipeline()
            self.status_updated.emit(self.job_id, "Rendering MP4 video with Manim...", 80)

            final_job = pipeline.run_pipeline(job)

            if final_job.status == JobStatus.ERROR or not final_job.video_path or not os.path.exists(final_job.video_path):
                err = final_job.error_message or "Video rendering did not output a valid MP4."
                self.video_failed.emit(self.job_id, err)
                return

            self.status_updated.emit(self.job_id, "Video Complete!", 100)
            self.video_ready.emit(self.job_id, final_job.video_path)
        except Exception as e:
            self.video_failed.emit(self.job_id, f"Video generation failed: {e}")

