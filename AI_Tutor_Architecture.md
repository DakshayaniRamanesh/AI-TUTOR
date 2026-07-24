# AI-TUTOR (Kestrel) - System Architecture & Codebase Overview

This document provides a comprehensive overview of the **AI-TUTOR (Kestrel)** project. It is designed to give an AI complete context on the system's architecture, components, and workflows.

## 1. High-Level Architecture
Kestrel is an AI-powered educational application that generates **Manim (math animation) videos** from PDF documents and user prompts. It also provides an interactive UI with a drawing canvas and a built-in mathematical symbolic solver.

The system is split into two primary layers:
1. **Frontend (PyQt6 Desktop Client):** Located in the `app/` directory. Provides the graphical user interface, manages canvas interactions, and routes requests to the backend.
2. **Backend (FastAPI / Modal Cloud GPU):** Located in the `backend/` directory. A heavy compute pipeline that orchestrates multiple AI agents using **LangGraph** to parse PDFs, write Manim scripts, validate them, and render MP4 videos.

---

## 2. Frontend (`app/`)
The frontend is a desktop application built with PyQt6. It acts as the client interacting with the user and the backend API.

### Key Components:
- **`app/main.py`**: The entry point of the PyQt6 application. It bootstraps the environment and initializes the main window (`MainWindow`).
- **`app/ui/`**: Contains the UI logic. Includes a canvas for drawing and annotations (`canvas_view.py`, `canvas_scene.py`), and the main window structure (`main_window.py`).
- **`app/backend/stem_solver.py`**: A local mathematical symbolic solver built using `SymPy`. It parses natural language math queries, cleans them, applies symbolic integration/differentiation or limits, and elegantly formats the output. If a graph is relevant (e.g., limits, integrals, derivatives), it uses `matplotlib` to generate and save beautifully styled function plots.
- **`app/backend/video_gen_client.py`**: The client that bridges the frontend UI and the backend API. It attempts to connect to a local FastAPI server first, and if unavailable, falls back to a remote Modal cloud endpoint. It uses `ManimVideoPollWorker` to asynchronously poll the backend (via `/status/{job_id}`) for pipeline progress updates without freezing the main UI thread.

---

## 3. Backend Pipeline (`backend/`)
The backend is a robust Python server that orchestrates the heavy lifting of RAG and video generation.

### 3.1. Server Deployment (Local vs. Cloud)
- **`backend/local_server.py`**: A standard FastAPI application that runs locally. It accepts requests via `/generate` (receiving a PDF and a prompt) and runs the video generation pipeline in a `BackgroundTasks` thread. It also handles `/annotate` to overlay user drawings onto generated videos.
- **`backend/modal_app.py`**: A cloud-deployed version of the backend using **Modal** (serverless GPU provider). It provisions `A10G` GPU instances on-demand. Notably, it checks the **cache** before spawning a GPU job: if another user requested a video for the exact same PDF section and prompt, it serves the cached video instantly. It also supports Server-Sent Events (SSE) via `/stream_status` to stream real-time progress to clients.

### 3.2. LangGraph Orchestration (`backend/pipeline/graph.py`)
The video generation process is modeled as a State Graph using **LangGraph**. The graph manages state transitions across several specialized AI agents:
1. **Document Embedder (`embed`)**: Reads the PDF, chunks it, and stores the embeddings in Qdrant.
2. **Story Agent (`story`)**: Generates a storyboard and pedagogical script based on the retrieved document context.
3. **Validator Agent (`validate`)**: Reviews the storyboard. If it needs revision, it routes back to the Story Agent. Otherwise, it proceeds to CodeGen.
4. **CodeGen Agent (`codegen`)**: Translates the approved storyboard into valid Python code using the `manim` library.
5. **CI Harness (`ci`)**: An automated testing node that runs the generated Manim code in a sandboxed or verified environment. 
   - **Self-Healing Loop**: If the build fails, the CI node returns the error trace back to the **CodeGen** node. The CodeGen agent then tries to fix the error. This retry loop is allowed up to 3 times before failing the job.
6. **Renderer Agent (`render`)**: If CI passes, this agent triggers the actual FFmpeg/Manim rendering process to output an MP4 file.
7. **Uploader Agent (`upload`)**: Uploads the final video and updates the state.

### 3.3. RAG and Caching (`backend/rag/qdrant_store.py`)
The system utilizes **Qdrant** as its vector database and uses Google **Gemini** embeddings (`models/text-embedding-004`).

The `QdrantRAGStore` manages two collections:
1. **`manim-docs-v4`**: Stores vector embeddings for document chunks uploaded by the user to provide context for the LLM.
2. **`manim-video-cache-v3` (Cross-Student Cache)**: Prevents redundant heavy compute. When a video is requested, a unique hash is generated from the user's prompt and the first 2000 characters of the PDF. If this hash exists in the cache (exact match) or if a semantic similarity query exceeds a `0.92` threshold (semantic match), the system instantly returns the previously generated video URL instead of running the LangGraph pipeline.

### 3.4. Annotations (`backend/pipeline/annotation_handler.py`)
Users can pause a video, draw on the frontend canvas, and submit those annotations to the backend. The backend reconstructs these strokes (timestamp, color, coordinates) and stitches them into the video frames, effectively allowing dynamic visual interactions over the generated AI tutorials.

---

## 4. Technology Stack
- **Languages**: Python
- **Frontend GUI**: PyQt6
- **Video Generation API**: Manim (Mathematical Animation Framework)
- **Agent Orchestration**: LangGraph, LangChain
- **LLM / Embeddings**: Google Gemini, Groq (for fast testing API fallback)
- **Vector Database**: Qdrant
- **Cloud Compute**: Modal (for on-demand A10G GPUs)
- **Math Engine**: SymPy, NumPy, Matplotlib

## 5. Typical Workflow
1. User uploads a PDF and types a prompt in the PyQt6 UI.
2. `video_gen_client.py` sends the payload to `modal_app.py` or `local_server.py`.
3. Backend hashes the PDF + prompt. If a cache hit occurs in Qdrant, the video is returned immediately.
4. If it's a cache miss, LangGraph initiates: Embed PDF -> Write Storyboard -> Validate -> Generate Manim Code.
5. CI node tests the Manim code. If it crashes, CodeGen attempts to fix it (up to 3 retries).
6. Once passed, the GPU renders the MP4 file and it is uploaded/cached.
7. The desktop app continuously polls (or uses SSE) for status and plays the final MP4 when complete.
