# Configuration Reference

This guide details all environment variables, configuration files, directory structures, and external service requirements for Kestrel.

---

## 1. Environment Variables

Environment variables are loaded automatically from `backend/.env` and `.env` at startup.

| Variable | Target Scope | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `GROQ_API_KEY` | Backend | **Yes** (video pipeline) | `""` | API key from Groq Cloud for fast LLaMA-3 text and script generation. |
| `GOOGLE_API_KEY` | Backend & App | **Yes** (vision/RAG) | `""` | Google AI Studio API key used for Gemini Vision, OCR, and document embeddings. |
| `QDRANT_URL` | Backend | No | `http://localhost:6333` | Host URL for the Qdrant vector database instance. |
| `QDRANT_API_KEY` | Backend | No | `""` | API key for managed or authenticated Qdrant instances. |
| `DO_SPACES_KEY` | Backend (Modal) | Optional (Cloud) | `""` | DigitalOcean Spaces (S3 compatible) access key for hosted video storage. |
| `DO_SPACES_SECRET`| Backend (Modal) | Optional (Cloud) | `""` | DigitalOcean Spaces secret access key. |
| `DO_SPACES_BUCKET`| Backend (Modal) | Optional (Cloud) | `manim-videos` | S3 bucket name where rendered MP4 files are stored. |
| `DO_SPACES_REGION`| Backend (Modal) | Optional (Cloud) | `nyc3` | S3 datacenter region identifier. |
| `DO_SPACES_ENDPOINT`| Backend (Modal)| Optional (Cloud) | `https://nyc3.digitaloceanspaces.com` | Custom S3 endpoint URL. |
| `FIREBASE_CREDENTIALS_JSON` | Backend (Modal) | Optional (Cloud) | `{}` | JSON string containing Firebase Service Account credentials for persistent Firestore job records. |
| `TAVILY_API_KEY` | Backend | No | `""` | Tavily Web Search API key used as fallback context when Qdrant lacks relevant information for video annotations. |
| `QT_QPA_PLATFORM`| Desktop App | No | Platform default | Set to `offscreen` in headless or continuous integration testing environments. |

---

## 2. Configuration Files

### 2.1 `backend/.env`
The primary environment file loaded by `backend/local_server.py` and referenced by `backend/modal_app.py`. A starter template is provided at `backend/.env.example`:

```ini
# Groq API Key — used for LLM script calls (Llama 3.3 / 3.1)
GROQ_API_KEY=gsk_your_groq_api_key

# Google Gemini API Key — used for vision, OCR, and embeddings
GOOGLE_API_KEY=AIzaSy_your_gemini_api_key

# Qdrant Vector DB — collection: "manim-docs", size=768/3072
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_qdrant_api_key

# DigitalOcean Spaces (S3 compatible) — cloud video hosting
DO_SPACES_KEY=your_spaces_key
DO_SPACES_SECRET=your_spaces_secret
DO_SPACES_BUCKET=manim-videos
DO_SPACES_REGION=nyc3
DO_SPACES_ENDPOINT=https://nyc3.digitaloceanspaces.com

# Firebase / Firestore (cloud persistent job state)
FIREBASE_CREDENTIALS_JSON={}

# Tavily Web Search API (annotation search fallback)
TAVILY_API_KEY=your_tavily_api_key
```

---

## 3. Local Storage and Data Layout

All local state is persisted under the project root in `storage_data/` and `downloads/`. These directories are automatically initialized if missing and are excluded from Git tracking via `.gitignore`.

```
storage_data/
├── kestrel.db                # SQLite database (Users, Subjects, Materials, Videos, Concepts)
├── boards/                   # Canvas boards saved as JSON documents
│   └── board_*.json
├── git_notes_repo/           # Local Git repository for markdown study notes & boards
│   ├── .git/
│   └── boards/
├── latex_exports/            # Output folder for generated .tex and compiled .pdf files
└── plots/                    # Rendered Matplotlib PNG figures from the STEM solver
downloads/
└── downloads_index.json      # Cache index for downloaded curriculum materials
```

### Storage Directory Permissions
- Ensure the user executing `python app/main.py` and `python backend/local_server.py` possesses read and write permissions to the repository root so `storage_data/` can be dynamically provisioned.

---

## 4. Hardware Acceleration and Rendering Options

### 4.1 GPU Rendering (Manim OpenGL)
- **Cloud Containers**: Automatically utilizes NVIDIA A10G GPUs on Modal with `--renderer=opengl`.
- **Local Workstations**: Requires an OpenGL-capable display driver and compatible X11/Windows graphics context. If unavailable, Manim seamlessly falls back to Cairo software rendering.

### 4.2 GPU Video Encoding (`h264_nvenc`)
- At startup, `RendererAgent` inspects available encoders via `ffmpeg -encoders`.
- If `h264_nvenc` is available alongside an NVIDIA GPU (`nvidia-smi`), hardware video encoding is used (3–5x faster encode speed).
- If absent, the pipeline automatically falls back to CPU-based `libx264`.

---

## 5. Binary Executable Requirements

### 5.1 Tectonic (`tectonic.exe`)
- Used for compiling LaTeX source code into PDFs without requiring a full multi-gigabyte TeX Live distribution.
- **Windows**: The standalone binary is bundled directly at `tectonic.exe` in the project root.
- **Linux/macOS**: Install via package manager (`cargo install tectonic` or `apt-get install tectonic`).
- **Auto-Download**: If missing, endpoint `GET /api/diagnostics/tectonic` will attempt to fetch the official v0.17.0 binary release automatically.

### 5.2 FFmpeg
- Used for audio/video stream muxing and lossless annotation concatenation.
- Must be discoverable in system `PATH` or provided via the `imageio-ffmpeg` Python package.
