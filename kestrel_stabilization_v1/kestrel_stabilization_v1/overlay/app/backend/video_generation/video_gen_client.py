"""
Video generation desktop client.

Important contract:
- a request is successful only when a backend actually accepted it;
- the worker polls the same backend that accepted the job;
- no synthetic/fake job IDs are returned after submission failure.
"""

from __future__ import annotations

import base64
import os
import sys
from urllib.parse import quote

import requests
from PyQt6.QtCore import QThread, pyqtSignal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from backend.config import (
    BACKEND_URL,
    MODAL_VIDEO_GENERATE_URL,
    MODAL_VIDEO_STATUS_URL,
)


class VideoSubmissionError(RuntimeError):
    pass


# Backward-compatible public API still returns a string job_id. The registry keeps
# the missing backend identity without forcing a large UI rewrite in this rescue pass.
_JOB_STATUS_ENDPOINTS: dict[str, str] = {}


def _read_pdf_b64(pdf_path: str | None) -> str:
    if not pdf_path or not os.path.exists(pdf_path):
        return ""
    with open(pdf_path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _register_status(job_id: str, endpoint: str) -> str:
    if not job_id:
        raise VideoSubmissionError("Backend accepted the request but returned no job_id.")
    _JOB_STATUS_ENDPOINTS[job_id] = endpoint
    return job_id


def request_video_generation(
    selected_text: str,
    pdf_path: str | None = None,
    page_range: str = "",
    emphasis_note: str = "",
    output_type: str = "video",
    subject_id: str = "",
    selection_payload: dict | None = None,
) -> str:
    selection_payload = selection_payload or {}
    pdf_b64 = _read_pdf_b64(pdf_path)

    payload = {
        "user_prompt": selected_text,
        # A local path is useful to the local server only. Cloud submission below
        # intentionally clears it and relies on document_text (base64 PDF bytes).
        "pdf_path": pdf_path or "",
        "document_text": pdf_b64,
        "page_range": page_range or None,
        "emphasis_note": emphasis_note or None,
        "output_type": output_type,
        "subject_id": subject_id or None,
        "board_selection": selection_payload or None,
    }

    failures: list[str] = []

    # Local first.
    try:
        resp = requests.post(f"{BACKEND_URL}/generate", json=payload, timeout=5)
        if resp.status_code in (200, 201, 202):
            data = resp.json()
            job_id = str(data.get("job_id") or "")
            status_endpoint = str(
                data.get("status_endpoint") or f"{BACKEND_URL}/status/{quote(job_id)}"
            )
            return _register_status(job_id, status_endpoint)
        failures.append(f"local HTTP {resp.status_code}: {resp.text[:180]}")
    except Exception as exc:
        failures.append(f"local: {type(exc).__name__}: {exc}")

    # Modal fallback, same logical request contract.
    try:
        modal_payload = dict(payload)
        modal_payload["pdf_path"] = ""
        resp = requests.post(MODAL_VIDEO_GENERATE_URL, json=modal_payload, timeout=8)
        if resp.status_code in (200, 201, 202):
            data = resp.json()
            job_id = str(data.get("job_id") or "")
            status_endpoint = str(
                data.get("status_endpoint")
                or f"{MODAL_VIDEO_STATUS_URL}?job_id={quote(job_id)}"
            )
            return _register_status(job_id, status_endpoint)
        failures.append(f"modal HTTP {resp.status_code}: {resp.text[:180]}")
    except Exception as exc:
        failures.append(f"modal: {type(exc).__name__}: {exc}")

    raise VideoSubmissionError(
        "Video submission failed on both local and Modal backends. "
        + " | ".join(failures)
    )


class ManimVideoPollWorker(QThread):
    """Poll the backend that actually accepted the job."""

    status_updated = pyqtSignal(str, str, int)
    video_ready = pyqtSignal(str, str)
    video_failed = pyqtSignal(str, str)

    def __init__(self, job_id: str, prompt: str = "", parent=None):
        super().__init__(parent)
        self.job_id = job_id
        self.prompt = prompt
        self._running = True
        self.status_url = _JOB_STATUS_ENDPOINTS.get(
            job_id, f"{BACKEND_URL}/status/{quote(job_id)}"
        )

    def stop(self):
        self._running = False

    def run(self):
        # 240 * 1.5 s = 6 minutes. Long enough for a real render without leaving
        # a dead poller alive for 30 minutes.
        max_attempts = 240
        request_failures = 0

        for attempt in range(1, max_attempts + 1):
            if not self._running:
                return
            self.msleep(1500)

            try:
                r = requests.get(self.status_url, timeout=4)
            except Exception as exc:
                request_failures += 1
                if request_failures >= 8:
                    self.video_failed.emit(
                        self.job_id,
                        f"Lost connection while polling video job: {exc}",
                    )
                    return
                continue

            if r.status_code == 404:
                self.video_failed.emit(
                    self.job_id,
                    "Video job was not found by the backend that accepted it.",
                )
                return

            if r.status_code >= 400:
                request_failures += 1
                if request_failures >= 5:
                    self.video_failed.emit(
                        self.job_id,
                        f"Video status endpoint returned HTTP {r.status_code}: {r.text[:200]}",
                    )
                    return
                continue

            request_failures = 0
            try:
                data = r.json()
            except Exception:
                self.video_failed.emit(self.job_id, "Video status response was not valid JSON.")
                return

            status = str(data.get("status", "processing")).lower()
            stage = (
                data.get("friendly_step")
                or data.get("current_stage")
                or data.get("step")
                or "Processing video"
            )
            progress = data.get("progress_percentage")
            if progress is None:
                progress = min(95, 5 + attempt // 2)

            self.status_updated.emit(self.job_id, str(stage), int(progress))

            if status in {"completed", "done", "success"}:
                video_url = data.get("video_url")
                local_path = data.get("video_local_path")
                if local_path and os.path.exists(local_path):
                    self.video_ready.emit(self.job_id, local_path)
                    return
                if video_url:
                    self.video_ready.emit(self.job_id, str(video_url))
                    return
                self.video_failed.emit(
                    self.job_id,
                    "Backend marked the video job complete but returned no video artifact.",
                )
                return

            if status in {"error", "failed", "not_found"}:
                self.video_failed.emit(
                    self.job_id,
                    str(data.get("error_message") or data.get("friendly_error") or "Video pipeline failed."),
                )
                return

        self.video_failed.emit(
            self.job_id,
            "Timed out waiting for video generation. Check backend logs for the job ID.",
        )
