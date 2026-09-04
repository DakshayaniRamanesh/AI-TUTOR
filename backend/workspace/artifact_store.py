import os
import shutil
from typing import Optional

class ArtifactStore:
    """
    Unified ArtifactStore abstraction.
    Manages persistent artifacts (videos, pdfs, etc.) across environments.
    """
    def __init__(self, base_dir: Optional[str] = None):
        if not base_dir:
            # Default to backend/workspace/artifacts
            self.base_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                "workspace", 
                "artifacts"
            )
        else:
            self.base_dir = base_dir
            
        os.makedirs(self.base_dir, exist_ok=True)

    def _get_path(self, job_id: str, key: str) -> str:
        return os.path.join(self.base_dir, f"{job_id}_{key}")

    def put(self, job_id: str, key: str, source_filepath: str) -> str:
        """Store an artifact and return its persistent path."""
        dest_path = self._get_path(job_id, key)
        shutil.copy2(source_filepath, dest_path)
        return dest_path
        
    def put_bytes(self, job_id: str, key: str, data: bytes) -> str:
        """Store raw bytes and return its persistent path."""
        dest_path = self._get_path(job_id, key)
        with open(dest_path, "wb") as f:
            f.write(data)
        return dest_path

    def get(self, job_id: str, key: str) -> Optional[str]:
        """Return the persistent path if it exists."""
        path = self._get_path(job_id, key)
        if os.path.exists(path):
            return path
        return None

    def get_url(self, job_id: str, key: str, base_url: str = "http://localhost:8000") -> str:
        """Generate a URL to access the artifact."""
        filename = f"{job_id}_{key}"
        return f"{base_url}/artifacts/{filename}"

# Global singleton
artifact_store = ArtifactStore()
