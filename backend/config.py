import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# --- SERVER CONFIGURATION ---
BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
BACKEND_URL = os.getenv("BACKEND_URL", f"http://{BACKEND_HOST}:{BACKEND_PORT}")

# --- MODAL CLOUD CONFIGURATION ---
MODAL_WORKSPACE = os.getenv("MODAL_WORKSPACE", "your-workspace-name")
MODAL_APP_NAME = os.getenv("MODAL_APP_NAME", "manim-video-pipeline")

def _build_modal_url(endpoint: str) -> str:
    """Helper to construct Modal URLs predictably without string replace hacks."""
    # Example Modal format: https://workspace--appname-endpoint-dev.modal.run
    return f"https://{MODAL_WORKSPACE}--{MODAL_APP_NAME}-{endpoint}.modal.run"

MODAL_VIDEO_GENERATE_URL = os.getenv("MODAL_VIDEO_GENERATE_URL", _build_modal_url("generate"))
MODAL_VIDEO_STATUS_URL = os.getenv("MODAL_VIDEO_STATUS_URL", _build_modal_url("status"))
MODAL_LATEX_GENERATE_URL = os.getenv("MODAL_LATEX_GENERATE_URL", _build_modal_url("generate-latex"))
MODAL_LATEX_STATUS_URL = os.getenv("MODAL_LATEX_STATUS_URL", _build_modal_url("latex-status"))
MODAL_ANNOTATE_URL = os.getenv("MODAL_ANNOTATE_URL", _build_modal_url("annotate"))

# --- QDRANT CONFIGURATION ---
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")

# --- PATHS ---
def get_base_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WORKSPACE_DIR = os.path.join(get_base_dir(), "backend", "workspace")
VIDEOS_DIR = os.path.join(WORKSPACE_DIR, "videos")
PDFS_DIR = os.path.join(WORKSPACE_DIR, "pdfs")

os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(PDFS_DIR, exist_ok=True)
