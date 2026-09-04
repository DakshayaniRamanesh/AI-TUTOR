"""
Desktop LaTeX client.

The local and Modal endpoints use the same JSON contract. A job ID is only
returned after a backend actually accepts the request.
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
    MODAL_LATEX_GENERATE_URL,
    MODAL_LATEX_STATUS_URL,
)


class LatexSubmissionError(RuntimeError):
    pass


_LATEX_STATUS_ENDPOINTS: dict[str, str] = {}


def _register_status(job_id: str, endpoint: str) -> str:
    if not job_id:
        raise LatexSubmissionError("Backend accepted the LaTeX request but returned no job_id.")
    _LATEX_STATUS_ENDPOINTS[job_id] = endpoint
    return job_id


def request_latex_generation(
    image_b64: str,
    template_type: str,
    mode: str = "study",
    classroom_action: str = "Solve Question",
) -> str:
    payload = {
        "image_b64": image_b64,
        "template_type": template_type,
        "mode": mode,
        "classroom_action": classroom_action,
    }
    failures: list[str] = []

    # New local_server.py expects JSON/Pydantic, not multipart form data.
    try:
        resp = requests.post(
            f"{BACKEND_URL}/generate_latex",
            json=payload,
            timeout=12,
        )
        if resp.status_code in (200, 201, 202):
            data = resp.json()
            job_id = str(data.get("job_id") or "")
            endpoint = str(
                data.get("status_endpoint")
                or f"{BACKEND_URL}/latex_status/{quote(job_id)}"
            )
            return _register_status(job_id, endpoint)
        failures.append(f"local HTTP {resp.status_code}: {resp.text[:180]}")
    except Exception as exc:
        failures.append(f"local: {type(exc).__name__}: {exc}")

    # Modal fallback with all mode fields preserved.
    try:
        resp = requests.post(
            MODAL_LATEX_GENERATE_URL,
            json=payload,
            timeout=12,
        )
        if resp.status_code in (200, 201, 202):
            data = resp.json()
            job_id = str(data.get("job_id") or "")
            endpoint = str(
                data.get("status_endpoint")
                or f"{MODAL_LATEX_STATUS_URL}?job_id={quote(job_id)}"
            )
            return _register_status(job_id, endpoint)
        failures.append(f"modal HTTP {resp.status_code}: {resp.text[:180]}")
    except Exception as exc:
        failures.append(f"modal: {type(exc).__name__}: {exc}")

    raise LatexSubmissionError(
        "LaTeX submission failed on both local and Modal backends. "
        + " | ".join(failures)
    )


def compile_custom_latex_pdf(latex_code: str, target_path: str) -> tuple[bool, str]:
    """Compile edited LaTeX through the local backend and save the returned PDF."""
    try:
        resp = requests.post(
            f"{BACKEND_URL}/compile_pdf",
            json={"latex_code": latex_code},
            timeout=90,
        )
        if resp.status_code == 200:
            data = resp.json()
            pdf_b64 = data.get("pdf_b64")
            if not pdf_b64:
                return False, "No PDF data returned from compiler."
            pdf_bytes = base64.b64decode(pdf_b64)
            os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
            with open(target_path, "wb") as f:
                f.write(pdf_bytes)
            return True, target_path

        try:
            message = resp.json().get("message", "Compilation failed")
        except Exception:
            message = resp.text[:500] or "Compilation failed"
        return False, message
    except Exception as exc:
        return False, str(exc)


class LatexPollWorker(QThread):
    status_updated = pyqtSignal(str, str, int)
    pdf_ready = pyqtSignal(str, str, str)
    latex_ready = pyqtSignal(str, str)
    pdf_failed = pyqtSignal(str, str)

    def __init__(self, job_id: str, parent=None):
        super().__init__(parent)
        self.job_id = job_id
        self._running = True
        self.status_url = _LATEX_STATUS_ENDPOINTS.get(
            job_id, f"{BACKEND_URL}/latex_status/{quote(job_id)}"
        )

    def stop(self):
        self._running = False

    def run(self):
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
                    self.pdf_failed.emit(
                        self.job_id,
                        f"Lost connection while polling LaTeX job: {exc}",
                    )
                    return
                continue

            if r.status_code == 404:
                self.pdf_failed.emit(
                    self.job_id,
                    "LaTeX job was not found by the backend that accepted it.",
                )
                return

            if r.status_code >= 400:
                request_failures += 1
                if request_failures >= 5:
                    self.pdf_failed.emit(
                        self.job_id,
                        f"LaTeX status endpoint returned HTTP {r.status_code}: {r.text[:200]}",
                    )
                    return
                continue

            request_failures = 0
            try:
                data = r.json()
            except Exception:
                self.pdf_failed.emit(self.job_id, "LaTeX status response was not valid JSON.")
                return

            status = str(data.get("status", "processing")).lower()
            stage = data.get("step") or data.get("current_stage") or "Processing LaTeX"
            progress = data.get("progress_percentage")
            if progress is None:
                progress = min(95, 5 + attempt // 2)

            self.status_updated.emit(self.job_id, f"LaTeX: {stage}", int(progress))

            if status in {"completed", "done", "success"}:
                latex_code = (
                    data.get("final_tex_code")
                    or data.get("latex_code")
                    or data.get("structured_latex")
                    or ""
                )
                if latex_code:
                    self.latex_ready.emit(self.job_id, str(latex_code))

                pdf_url = str(data.get("pdf_url") or "")
                pdf_b64 = str(data.get("pdf_b64") or "")
                if pdf_url or pdf_b64:
                    self.pdf_ready.emit(self.job_id, pdf_url, pdf_b64)

                if latex_code or pdf_url or pdf_b64:
                    return

                self.pdf_failed.emit(
                    self.job_id,
                    "Backend marked the LaTeX job complete but returned neither LaTeX nor PDF output.",
                )
                return

            if status in {"error", "failed", "not_found"}:
                self.pdf_failed.emit(
                    self.job_id,
                    str(data.get("error_message") or "LaTeX pipeline failed."),
                )
                return

        self.pdf_failed.emit(
            self.job_id,
            "Timed out waiting for LaTeX generation. Check backend logs for the job ID.",
        )
