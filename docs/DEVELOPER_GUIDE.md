# Developer Guide

This guide covers developer onboarding, local environment setup, testing standards, debugging workflows, and deployment procedures for Kestrel.

---

## 1. Prerequisites

Before setting up the project, ensure your environment meets the following baseline requirements:

| Tool | Version Requirement | Purpose |
| :--- | :--- | :--- |
| **Python** | 3.10 to 3.13 (3.11 recommended) | Runtime environment for both client and backend. |
| **Git** | &ge; 2.30.0 | Source control and Git-backed study notes engine. |
| **FFmpeg** | &ge; 5.0 (or `imageio-ffmpeg`) | Video stream muxing and stream-copy stitching. |
| **Tectonic** | 0.17.0+ (bundled on Windows) | Standalone XeTeX compiler for LaTeX generation. |
| **Modal CLI** | Optional (`pip install modal`) | Required only for cloud GPU deployment. |

---

## 2. Environment Setup

### 2.1 Clone Repository and Create Virtual Environment

```bash
git clone https://github.com/DakshayaniRamanesh/AI-TUTOR.git
cd AI-TUTOR

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate
```

### 2.2 Install Dependencies

Install all core and desktop dependencies:

```bash
pip install -r requirements.txt
```

### 2.3 Configure API Keys

Copy the template configuration and supply valid credentials:

```bash
cp backend/.env.example backend/.env
```

At minimum, set:
- `GROQ_API_KEY`: Required for LLM narrative script generation.
- `GOOGLE_API_KEY`: Required for multimodal handwriting OCR and Gemini embeddings.

---

## 3. Running Locally

### 3.1 Start the Backend Server

Start the local FastAPI pipeline server in a dedicated terminal:

```bash
python backend/local_server.py
```

Expected output:
```
INFO:     Started server process [PID]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

The interactive API documentation is available at `http://localhost:8000/docs`.

### 3.2 Start the Desktop Client

In a second terminal with the virtual environment activated:

```bash
python app/main.py
```

The application will launch the main window with Fusion styling and verify that `storage_data/` directories and the SQLite database (`storage_data/kestrel.db`) exist.

---

## 4. Testing

### 4.1 Running the Test Suite

Run all unit and integration tests using pytest:

```bash
python -m pytest app/tests
```

> **Note**: Always invoke pytest using `python -m pytest` rather than `pytest` directly. This guarantees the repository root is placed on `sys.path`, allowing `app.*` and `backend.*` imports to resolve correctly.

### 4.2 Running Specific Test Suites

```bash
# Test canvas serialization & state persistence
python -m pytest app/tests/test_save_load.py

# Test geometric shape detection algorithms
python -m pytest app/tests/test_shape_fitting.py

# Test PenEcho scientific diagram generation
python -m pytest app/tests/test_penecho_integration.py

# Test stroke smoothing and stabilization
python -m pytest app/tests/test_stroke_processor.py

# Test theme manager and LaTeX editor
python -m pytest app/tests/test_theme_and_latex_editor.py
```

### 4.3 Headless / CI Testing

When executing tests in environments without an active X11, Wayland, or Windows desktop session (such as GitHub Actions), set the Qt offscreen platform flag:

```bash
# Windows PowerShell
$env:QT_QPA_PLATFORM="offscreen"
python -m pytest app/tests

# Linux / macOS
QT_QPA_PLATFORM=offscreen python -m pytest app/tests
```

---

## 5. Cloud Deployment via Modal

For production GPU rendering on NVIDIA A10G infrastructure:

### 5.1 Authenticate Modal CLI

```bash
modal setup
```

### 5.2 Test Deployment in Ephemeral Dev Mode

```bash
modal serve backend/modal_app.py
```

Modal provisions the Debian container image with Cairo, Pango, and TeX Live, binds secrets from `backend/.env`, and outputs a development endpoint URL.

### 5.3 Deploy Production Cluster

```bash
modal deploy backend/modal_app.py
```

---

## 6. Troubleshooting & Common Issues

### 6.1 `sqlite3.OperationalError: unable to open database file`
- **Cause**: The parent directory `storage_data/` does not exist on disk.
- **Resolution**: `app/storage/database.py` includes `os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)` before `create_engine`. If running custom scripts, ensure `storage_data/` is created beforehand.

### 6.2 `RuntimeError: Form data requires "python-multipart" to be installed`
- **Cause**: FastAPI requires `python-multipart` for endpoints that accept `UploadFile` or `Form(...)`.
- **Resolution**: Verify `python-multipart` is installed in your active virtual environment (`pip install python-multipart`).

### 6.3 Diagnostic Check Returns `401 Unauthorized` / `500 Internal Server Error`
- **Cause**: `GROQ_API_KEY` or `GOOGLE_API_KEY` is empty or using the default placeholder string `your_groq_api_key`.
- **Resolution**: Update `backend/.env` with valid keys and restart the server. Test keys directly via:
  ```bash
  curl http://localhost:8000/api/diagnostics/groq
  curl http://localhost:8000/api/diagnostics/gemini
  ```

### 6.4 `Tectonic binary not found`
- **Cause**: `tectonic.exe` is missing from the project root and is not installed on system `PATH`.
- **Resolution**: Call `GET http://localhost:8000/api/diagnostics/tectonic` to trigger an automatic binary download, or place the `tectonic` executable in the project root.
