from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent

# Keep environment loading deterministic. Existing process environment wins.
load_dotenv(ROOT_DIR / ".env", override=False)
load_dotenv(BACKEND_DIR / ".env", override=False)

# Local backend
BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1").strip() or "127.0.0.1"
BACKEND_PORT = int(os.getenv("BACKEND_PORT", os.getenv("PORT", "8000")))
BACKEND_URL = os.getenv(
    "BACKEND_URL",
    f"http://{BACKEND_HOST}:{BACKEND_PORT}",
).rstrip("/")

# Modal. Explicit endpoint variables always win. The defaults match modal_app.py.
MODAL_WORKSPACE = os.getenv("MODAL_WORKSPACE", "dakshayaniramanesh").strip()
MODAL_APP_NAME = os.getenv("MODAL_APP_NAME", "manim-app").strip()


def _build_modal_url(endpoint: str) -> str:
    endpoint = endpoint.strip("-").replace("_", "-")
    return f"https://{MODAL_WORKSPACE}--{MODAL_APP_NAME}-{endpoint}.modal.run"


# Backward compatibility with the old MODAL_URL variable for video generation.
_LEGACY_MODAL_URL = os.getenv("MODAL_URL", "").strip()

MODAL_VIDEO_GENERATE_URL = (
    os.getenv("MODAL_VIDEO_GENERATE_URL", "").strip()
    or _LEGACY_MODAL_URL
    or _build_modal_url("generate")
)
MODAL_VIDEO_STATUS_URL = (
    os.getenv("MODAL_VIDEO_STATUS_URL", "").strip()
    or _build_modal_url("status")
)
MODAL_LATEX_GENERATE_URL = (
    os.getenv("MODAL_LATEX_GENERATE_URL", "").strip()
    or _build_modal_url("generate-latex")
)
MODAL_LATEX_STATUS_URL = (
    os.getenv("MODAL_LATEX_STATUS_URL", "").strip()
    or _build_modal_url("latex-status")
)
MODAL_ANNOTATE_URL = (
    os.getenv("MODAL_ANNOTATE_URL", "").strip()
    or _build_modal_url("annotate")
)

# Optional runtime tools.
TECTONIC_BIN = os.getenv("TECTONIC_BIN", "").strip()

# Qdrant
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333").strip()
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "").strip()

# Artifacts
WORKSPACE_DIR = str(BACKEND_DIR / "workspace")
VIDEOS_DIR = str(BACKEND_DIR / "workspace" / "videos")
PDFS_DIR = str(BACKEND_DIR / "workspace" / "pdfs")
ARTIFACTS_DIR = str(BACKEND_DIR / "workspace" / "artifacts")
ARTIFACT_BASE_URL = os.getenv("ARTIFACT_BASE_URL", BACKEND_URL).rstrip("/")

for directory in (VIDEOS_DIR, PDFS_DIR, ARTIFACTS_DIR):
    os.makedirs(directory, exist_ok=True)
