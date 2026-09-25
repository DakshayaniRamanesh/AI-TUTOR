import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# --- SERVER CONFIGURATION ---
BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
BACKEND_URL = os.getenv("BACKEND_URL", f"http://{BACKEND_HOST}:{BACKEND_PORT}")

# --- VIDEO BACKEND CONFIGURATION ---
# "latex" (active default): reliable, high-resolution LaTeX animated frame pipeline
# "manim": legacy experimental Manim Python code generation pipeline
VIDEO_RENDERER = os.getenv("VIDEO_RENDERER", "latex").strip().lower()

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

# --- VOICE NARRATION (Edge TTS narration) ---
# When true (default), Edge TTS narration is synthesized and muxed with video frames.
VOICE_ENABLED = os.getenv("VOICE_ENABLED", "true").strip().lower() == "true"
# TTS provider identifier — extensible for future providers.
VOICE_PROVIDER = os.getenv("VOICE_PROVIDER", "edge_tts")
# Edge TTS neural voice name. Warm, expressive British English professional teacher voice:
# en-GB-RyanNeural  — male,   warm & professional (default)
# en-GB-SoniaNeural — female, clear & expressive
# en-GB-LibbyNeural — female, friendly & natural
VOICE_LANG = os.getenv("VOICE_LANG", "en-GB-RyanNeural")
# Voice speed and pitch modulation (+4% provides active, energetic delivery)
VOICE_RATE = os.getenv("VOICE_RATE", "+4%")
VOICE_PITCH = os.getenv("VOICE_PITCH", "+0Hz")
# Directory where per-segment MP3 audio files are stored.
AUDIO_DIR = os.path.join(WORKSPACE_DIR, "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

# LLM models for pedagogical teacher narration
NARRATION_MODEL_GROQ = os.getenv("NARRATION_MODEL_GROQ", "qwen/qwen3.8-27b")
NARRATION_MODEL_GEMINI = os.getenv("NARRATION_MODEL_GEMINI", "gemini-2.5-flash")
NARRATION_MAX_WORDS_PER_FRAME = int(os.getenv("NARRATION_MAX_WORDS_PER_FRAME", "25"))
