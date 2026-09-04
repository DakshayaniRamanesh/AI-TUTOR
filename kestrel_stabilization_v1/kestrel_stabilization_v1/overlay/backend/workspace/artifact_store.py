from __future__ import annotations

import os
import shutil
from typing import Optional


class ArtifactStore:
    """Small canonical store for generated video/PDF artifacts."""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            self.base_dir = os.path.abspath(base_dir)
        else:
            self.base_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "workspace",
                "artifacts",
            )
        os.makedirs(self.base_dir, exist_ok=True)

    def _get_path(self, job_id: str, key: str) -> str:
        safe_job = str(job_id).replace("/", "_").replace("\\", "_")
        safe_key = str(key).replace("/", "_").replace("\\", "_")
        return os.path.join(self.base_dir, f"{safe_job}_{safe_key}")

    def put(self, job_id: str, key: str, source_filepath: str) -> str:
        dest_path = self._get_path(job_id, key)
        source_abs = os.path.abspath(source_filepath)
        dest_abs = os.path.abspath(dest_path)
        if source_abs != dest_abs:
            shutil.copy2(source_abs, dest_abs)
        return dest_abs

    def put_bytes(self, job_id: str, key: str, data: bytes) -> str:
        dest_path = self._get_path(job_id, key)
        with open(dest_path, "wb") as f:
            f.write(data)
        return dest_path

    def get(self, job_id: str, key: str) -> Optional[str]:
        path = self._get_path(job_id, key)
        return path if os.path.isfile(path) else None

    def get_url(self, job_id: str, key: str, base_url: Optional[str] = None) -> str:
        # Avoid a second hard-coded localhost source of truth.
        if not base_url:
            base_url = os.getenv("ARTIFACT_BASE_URL") or os.getenv(
                "BACKEND_URL", "http://127.0.0.1:8000"
            )
        filename = os.path.basename(self._get_path(job_id, key))
        return f"{base_url.rstrip('/')}/artifacts/{filename}"


artifact_store = ArtifactStore()
