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
from typing import Optional
from PyQt6.QtCore import QThread, pyqtSignal
from shared.contracts.video import VideoGenerationRequest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from backend.config import BACKEND_URL, MODAL_VIDEO_GENERATE_URL, MODAL_VIDEO_STATUS_URL
except ImportError:
    BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
    MODAL_VIDEO_GENERATE_URL = os.getenv("MODAL_URL", "https://dakshayaniramanesh--manim-app-generate.modal.run")
    MODAL_VIDEO_STATUS_URL = MODAL_VIDEO_GENERATE_URL.replace("/generate", "/status")

LOCAL_SERVERS = [
    BACKEND_URL.rstrip("/"),
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:8888",
    "http://localhost:8888"
]
LOCAL_SERVERS = list(dict.fromkeys([s for s in LOCAL_SERVERS if s]))

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
    request: Optional[VideoGenerationRequest] = None,
    *,
    selected_text: Optional[str] = None,
    subject_id: Optional[str] = None,
    selection_payload: Optional[dict] = None,
    notebook_id: Optional[str] = None,
    user_instruction: Optional[str] = None,
    **kwargs
) -> str:
    """Queue a request immediately; network submission happens in the poll worker."""
    if request is None:
        goal = (selected_text or user_instruction or "").strip() or "Explain the selected content."
        request = VideoGenerationRequest(
            request_id=f"job_{uuid.uuid4().hex[:8]}",
            explanation_goal=goal,
            recognized_content=selected_text or "",
            subject_id=subject_id or None,
            notebook_id=notebook_id or None,
            selection_payload=selection_payload,
            **{k: v for k, v in kwargs.items() if hasattr(VideoGenerationRequest, k)}
        )

    job_id = request.request_id
    _PENDING_JOBS[job_id] = {
        "prompt": request.explanation_goal,
        "subject_id": request.subject_id,
        "pdf_path": request.pdf_path,
        "page_range": request.page_range,
        "emphasis_note": request.emphasis_note,
        "output_type": request.output_type,
        "selection_payload": request.selection_payload,
        "is_local_direct": True,
        "needs_submit": True,
        "request_payload": request.model_dump(mode="json"),
    }
    return job_id


def _submit_video_request(job_id: str, job_info: dict) -> tuple[str, dict]:
    payload = job_info["request_payload"]
    for server_url in LOCAL_SERVERS:
        try:
            resp = requests.post(
                f"{server_url}/generate",
                json=payload,
                timeout=2.5,
            )
            if resp.status_code in [200, 201, 202]:
                data = resp.json()
                ret_id = data.get("job_id", job_id)
                job_info.update(is_local_direct=False, needs_submit=False, server_url=server_url,
                                status_url=data.get("status_url") or f"{server_url}/status/{ret_id}")
                _PENDING_JOBS[ret_id] = job_info
                return ret_id, job_info
        except Exception:
            continue

    try:
        resp = requests.post(
            MODAL_VIDEO_GENERATE_URL,
            json=payload,
            timeout=3.5,
        )
        if resp.status_code in [200, 201, 202]:
            data = resp.json()
            ret_id = data.get("job_id", job_id)
            job_info.update(is_local_direct=False, needs_submit=False,
                            status_url=data.get("status_url") or f"{MODAL_VIDEO_STATUS_URL.rstrip('/')}/{ret_id}")
            _PENDING_JOBS[ret_id] = job_info
            return ret_id, job_info
    except Exception:
        pass
    job_info["needs_submit"] = False
    return job_id, job_info


_ACTIVE_WORKERS = set()


class ManimVideoPollWorker(QThread):
    """Executes or polls video generation without blocking the Qt event loop."""

    status_updated = pyqtSignal(str, str, int)
    video_ready = pyqtSignal(str, str)
    video_failed = pyqtSignal(str, str)

    def __init__(self, job_id: str, prompt: str, parent=None):
        # Always initialize with parent=None: QThreads must never be owned by QWidgets
        super().__init__(None)
        self.job_id = job_id
        self.prompt = prompt
        self._running = True
        _ACTIVE_WORKERS.add(self)
        self.finished.connect(self._on_worker_finished)

    def _on_worker_finished(self):
        _ACTIVE_WORKERS.discard(self)
        self.deleteLater()

    def stop(self):
        self._running = False

    def run(self):
        job_info = _PENDING_JOBS.get(self.job_id, {})
        if job_info.get("needs_submit"):
            self.status_updated.emit(self.job_id, "Connecting to Video Engine...", 5)
            self.job_id, job_info = _submit_video_request(self.job_id, job_info)
        is_direct = job_info.get("is_local_direct", True)
        server_url = job_info.get("server_url") or _get_active_server()
        status_url = job_info.get("status_url")

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
                r = requests.get(status_url or f"{server_url}/status/{self.job_id}", timeout=2.5)
                if r.status_code == 200:
                    data = r.json()
                    status = data.get("status", "processing")
                    video_url = data.get("video_url")
                    video_local_path = data.get("video_local_path")
                    progress = data.get("progress_percentage", min(95, attempts * 5))
                    stage = data.get("friendly_step") or data.get("step", "Rendering Lesson Video")
                    self.status_updated.emit(self.job_id, stage, int(progress))
                    if status in ["completed", "done", "success"]:
                        final_url = video_local_path if (video_local_path and os.path.exists(video_local_path)) else video_url
                        if final_url:
                            self.video_ready.emit(self.job_id, final_url)
                            return
                    elif status == "error":
                        self.video_failed.emit(self.job_id, data.get("friendly_error") or data.get("error_message", "Video generation failed"))
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

            self.status_updated.emit(self.job_id, "Understanding your material...", 20)

            from backend.video_generation.models import VideoJob, JobStatus, BoardSelection
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
                board_selection=BoardSelection.from_dict(job_info.get("selection_payload"))
            )

            self.status_updated.emit(self.job_id, "Structuring explanation & presentation...", 45)

            pipeline = VideoGenerationPipeline()
            self.status_updated.emit(self.job_id, "Rendering animated lesson video...", 75)

            final_job = pipeline.run_pipeline(job)

            if final_job.status == JobStatus.ERROR or not final_job.video_path or not os.path.exists(final_job.video_path):
                err = final_job.error_message or "Video rendering did not output a valid MP4."
                self.video_failed.emit(self.job_id, err)
                return

            self.status_updated.emit(self.job_id, "Video Complete!", 100)
            self.video_ready.emit(self.job_id, final_job.video_path)
        except Exception as e:
            self.video_failed.emit(self.job_id, f"Video generation failed: {e}")
