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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

LOCAL_SERVER_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
MODAL_ENDPOINT_URL = os.getenv("MODAL_URL", "https://dakshayaniramanesh--manim-app-generate.modal.run")


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

    # 1. Try local server. The selection is JSON inside multipart/form-data so
    # existing PDF upload behavior remains backward-compatible.
    try:
        files = None
        file_handle = None
        if pdf_path and os.path.exists(pdf_path):
            file_handle = open(pdf_path, "rb")
            files = {"pdf": file_handle}
        try:
            resp = requests.post(
                f"{LOCAL_SERVER_URL}/generate",
                data={
                    "prompt": selected_text,
                    "page_range": page_range,
                    "emphasis_note": emphasis_note,
                    "output_type": output_type,
                    "subject_id": subject_id,
                    "selection_json": json.dumps(selection_payload, separators=(",", ":")),
                },
                files=files,
                timeout=3,
            )
        finally:
            if file_handle:
                file_handle.close()
        if resp.status_code == 200:
            data = resp.json()
            return data.get("job_id", job_id)
    except Exception:
        pass

    # 2. Try Modal with the same request fields. PDF bytes are forwarded rather
    # than silently disappearing on the cloud fallback path.
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
            timeout=4,
        )
        if resp.status_code in [200, 201, 202]:
            data = resp.json()
            return data.get("job_id", job_id)
    except Exception:
        pass

    return job_id


class ManimVideoPollWorker(QThread):
    """Poll video generation without blocking the Qt event loop."""

    status_updated = pyqtSignal(str, str, int)
    video_ready = pyqtSignal(str, str)
    video_failed = pyqtSignal(str, str)

    def __init__(self, job_id: str, prompt: str, parent=None):
        super().__init__(parent)
        self.job_id = job_id
        self.prompt = prompt
        self._running = True

    def run(self):
        attempts = 0
        max_attempts = 300
        while self._running and attempts < max_attempts:
            attempts += 1
            self.msleep(1500)
            try:
                r = requests.get(f"{LOCAL_SERVER_URL}/status/{self.job_id}", timeout=2)
                if r.status_code == 200:
                    data = r.json()
                    status = data.get("status", "processing")
                    video_url = data.get("video_url")
                    video_local_path = data.get("video_local_path")
                    progress = data.get("progress_percentage", min(95, attempts * 6))
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
            except Exception:
                pass

            stage_name = (
                "Board/Story Analysis" if attempts < 4
                else "Scene Planning / Manim Compilation" if attempts < 10
                else "RendererAgent: Rendering MP4 Video"
            )
            self.status_updated.emit(self.job_id, f"▷ {stage_name}...", min(92, attempts * 4))

        self.video_failed.emit(self.job_id, "Timed out waiting for video. Server may still be rendering — check backend logs.")
