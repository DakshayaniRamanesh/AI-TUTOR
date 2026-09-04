import os
import uuid
import tempfile
import subprocess
import base64
import zipfile
import io
import urllib.request
from dotenv import load_dotenv

# Load backend/.env — explicit path takes precedence over CWD
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

try:
    import imageio_ffmpeg
    ffmpeg_dir = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
    os.environ["PATH"] += os.pathsep + ffmpeg_dir
except ImportError:
    pass

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, BackgroundTasks, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from backend.video_generation.models import (
    VideoJob, AnnotationEvent, PathData, LatexJob,
    VideoGenerationRequest, VideoGenerationResponse, VideoJobStatusResponse,
    LatexGenerationRequest, LatexGenerationResponse, LatexJobStatusResponse,
    BoardSelection
)
import backend.config as config
from backend.video_generation.graph import VideoGenerationPipeline
from backend.math_engine.latex_graph import LatexGenerationPipeline
from backend.workspace.qdrant_store import QdrantRAGStore
from backend.video_qa.annotation_handler import AnnotationHandler
from backend.workspace.artifact_store import artifact_store

app = FastAPI(title="Manim AI Local Pipeline Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for local jobs
jobs_store: dict[str, VideoJob] = {}
pipeline = VideoGenerationPipeline()

latex_jobs_store: dict[str, LatexJob] = {}
latex_pipeline = LatexGenerationPipeline()

# ── User-facing progress label map ────────────────────────────────────────────
_STEP_LABELS: dict[str, str] = {
    "init": "Starting...",
    "document_embedder": "Understanding your material...",
    "story_agent": "Designing visual explanation...",
    "validator_agent": "Reviewing lesson structure...",
    "codegen_agent": "Generating animation...",
    "ci": "Checking animation quality...",
    "renderer_agent": "Rendering video...",
    "uploader_agent": "Finalizing video...",
    "notes_generator": "Generating study notes...",
}

# ── User-facing error code map ─────────────────────────────────────────────────
_ERROR_LABELS: dict[str, str] = {
    "CODEGEN_MAX_RETRIES": (
        "Kestrel couldn't generate this animation after 3 attempts. "
        "Try rephrasing your topic or using a simpler subject."
    ),
    "PAGE_LIMIT": "Your document selection is too large. Please select 30 or fewer pages.",
    "No animation code": "No animation was produced. Please try again.",
    "Manim render failed": "The animation could not be rendered. Kestrel is retrying.",
    "Rendering failed unexpectedly": "An unexpected rendering error occurred. Please try again.",
}


def _friendly_error(raw_error: str | None) -> str:
    """Map internal error messages to user-friendly strings."""
    if not raw_error:
        return ""
    for key, friendly in _ERROR_LABELS.items():
        if key in raw_error:
            return friendly
    # Strip internal stack details but keep a useful one-line description
    first_line = raw_error.split("\n")[0][:200]
    return f"Something went wrong: {first_line}"


def run_job_background(job: VideoJob):
    try:
        final_job = pipeline.run_pipeline(job)
        jobs_store[job.job_id] = final_job
    except Exception as e:
        job.status = "error"
        job.error_message = str(e)
        jobs_store[job.job_id] = job

@app.post("/generate", response_model=VideoGenerationResponse)
async def generate(
    background_tasks: BackgroundTasks,
    request: VideoGenerationRequest = Body(...)
):
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    
    # Optional logic for decoding document text back to a local PDF for the pipeline
    pdf_path = request.pdf_path
    if request.document_text and not pdf_path:
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        temp_pdf.write(base64.b64decode(request.document_text))
        temp_pdf.close()
        pdf_path = temp_pdf.name

    board_selection = None
    if request.board_selection:
        board_selection = BoardSelection.from_dict(request.board_selection)

    job = VideoJob(
        job_id=job_id,
        pdf_path=pdf_path,
        user_prompt=request.user_prompt,
        document_text="",
        page_range=request.page_range,
        emphasis_note=request.emphasis_note,
        output_type=request.output_type,
        subject_id=request.subject_id,
        board_selection=board_selection,
    )
    jobs_store[job_id] = job
    background_tasks.add_task(run_job_background, job)

    return VideoGenerationResponse(
        job_id=job_id,
        backend="local",
        status_endpoint=f"{config.BACKEND_URL}/status/{job_id}"
    )

def get_base_url() -> str:
    return config.BACKEND_URL

@app.get("/status/{job_id}")
async def status(job_id: str):
    if job_id not in jobs_store:
        return JSONResponse({"error": "Job not found"}, status_code=404)

    job = jobs_store[job_id]

    video_url = job.video_url
    if not video_url and job.video_path and os.path.exists(job.video_path):
        filename = os.path.basename(job.video_path)
        video_url = f"{get_base_url()}/artifacts/{filename}"

    job_status = job.status.value if hasattr(job.status, "value") else str(job.status)
    internal_step = job.step
    friendly_step = job.friendly_step or _STEP_LABELS.get(internal_step, internal_step)

    return {
        "job_id": job.job_id,
        "status": job_status,
        # Internal fields (for developer/debugging)
        "step": internal_step,
        "progress_percentage": job.progress_percentage,
        # User-facing fields
        "friendly_step": friendly_step,
        "friendly_error": _friendly_error(job.error_message),
        "topic_subject": job.topic_subject,
        "model_used": job.model_used,
        "render_quality": job.render_quality,
        "source_document": job.source_document,
        "pipeline_version": job.pipeline_version,
        # Video output
        "video_url": video_url or job.video_url,
        "video_local_path": job.video_path,
        # Raw error (for developer details panel)
        "error_message": job.error_message,
        "version": job.version,
        "story_script": job.story_script,
        "metadata": job.metadata,
    }

@app.post("/annotate")
async def annotate(payload: dict):
    job_id = payload.get("job_id", "")
    annotations_raw = payload.get("annotations", [])
    
    if job_id not in jobs_store:
        return JSONResponse({"error": "Job not found"}, status_code=404)
        
    job = jobs_store[job_id]
    
    parsed_annotations = []
    for ann in annotations_raw:
        raw_paths = ann.get("paths", [])
        parsed_paths = [
            PathData(
                points=[(pt[0], pt[1]) for pt in p.get("points", [])],
                stroke_color=p.get("stroke_color", "#ef4444"),
                stroke_width=p.get("stroke_width", 3),
            )
            for p in raw_paths
        ]
        parsed_annotations.append(
            AnnotationEvent(
                timestamp=ann.get("timestamp", 0.0),
                frame_image=ann.get("frame_image", ""),
                paths=parsed_paths,
                comment=ann.get("comment", "")
            )
        )

    handler = AnnotationHandler(QdrantRAGStore())
    updated_job = handler.process_annotations(job, parsed_annotations)
    jobs_store[job_id] = updated_job

    video_url = updated_job.video_url
    if updated_job.video_path and os.path.exists(updated_job.video_path):
        filename = os.path.basename(updated_job.video_path)
        video_url = f"{get_base_url()}/video/{filename}"

    return {
        "job_id": updated_job.job_id,
        "status": "updated",
        "version": updated_job.version,
        "video_url": video_url
    }

@app.api_route("/artifacts/{filename}", methods=["GET", "HEAD"])
async def serve_artifact(filename: str):
    path = os.path.join(artifact_store.base_dir, filename)
    if os.path.exists(path) and os.path.isfile(path):
        import mimetypes
        mt, _ = mimetypes.guess_type(path)
        return FileResponse(path, media_type=mt or "application/octet-stream")
    return JSONResponse({"error": "Artifact not found"}, status_code=404)

@app.api_route("/video/{filename}", methods=["GET", "HEAD"])
async def serve_video(filename: str):
    # Backward compatibility: Redirect to artifact store
    path = os.path.join(artifact_store.base_dir, filename)
    if os.path.exists(path) and os.path.isfile(path):
        import mimetypes
        mt, _ = mimetypes.guess_type(path)
        return FileResponse(path, media_type=mt or "video/mp4")
    # Fallback to older search
    for job in jobs_store.values():
        if job.video_path and os.path.basename(job.video_path) == filename:
            if os.path.exists(job.video_path):
                return FileResponse(job.video_path, media_type="video/mp4")
    return JSONResponse({"error": "Video file not found"}, status_code=404)


def run_latex_job_background(job: LatexJob):
    try:
        final_job = latex_pipeline.run_pipeline(job)
        latex_jobs_store[job.job_id] = final_job
    except Exception as e:
        job.status = "error"
        job.error_message = str(e)
        latex_jobs_store[job.job_id] = job

@app.post("/generate_latex", response_model=LatexGenerationResponse)
async def generate_latex(
    background_tasks: BackgroundTasks,
    request: LatexGenerationRequest = Body(...)
):
    job_id = f"latex_{uuid.uuid4().hex[:8]}"
    
    job = LatexJob(
        job_id=job_id,
        image_b64=request.image_b64,
        template_type=request.template_type,
        mode=request.mode,
        classroom_action=request.classroom_action 
    )
    latex_jobs_store[job_id] = job

    background_tasks.add_task(run_latex_job_background, job)

    return LatexGenerationResponse(
        job_id=job_id,
        backend="local",
        status_endpoint=f"{config.BACKEND_URL}/latex_status/{job_id}"
    )

@app.get("/latex_status/{job_id}")
async def latex_status(job_id: str):
    if job_id not in latex_jobs_store:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    
    job = latex_jobs_store[job_id]
    
    pdf_url = None
    if job.pdf_path and os.path.exists(job.pdf_path):
        filename = os.path.basename(job.pdf_path)
        pdf_url = f"{get_base_url()}/artifacts/{filename}"

    return {
        "job_id": job.job_id,
        "status": job.status.value if hasattr(job.status, "value") else str(job.status),
        "step": job.step,
        "progress_percentage": job.progress_percentage,
        "pdf_url": pdf_url or job.pdf_url,
        "latex_code": job.final_tex_code or job.structured_latex or job.raw_transcription or "",
        "raw_transcription": job.raw_transcription or "",
        "structured_latex": job.structured_latex or "",
        "error_message": job.error_message
    }

@app.post("/compile_pdf")
async def compile_pdf(payload: dict):
    latex_code = payload.get("latex_code", "").strip()
    if not latex_code:
        return JSONResponse({"status": "error", "message": "No LaTeX code provided."}, status_code=400)

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_tectonic = os.path.join(project_root, "tectonic.exe")
    tectonic_cmd = local_tectonic if os.path.exists(local_tectonic) else "tectonic"

    temp_dir = tempfile.mkdtemp()
    tex_path = os.path.join(temp_dir, "document.tex")
    pdf_path = os.path.join(temp_dir, "document.pdf")

    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(latex_code)

    try:
        import asyncio
        res = await asyncio.to_thread(
            subprocess.run,
            [tectonic_cmd, tex_path],
            cwd=temp_dir,
            capture_output=True,
            text=True,
            timeout=300
        )
        if res.returncode == 0 and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as pf:
                pdf_b64 = base64.b64encode(pf.read()).decode()
            return {"status": "ok", "pdf_b64": pdf_b64}
        else:
            err_msg = res.stderr or res.stdout or "Compilation error"
            return JSONResponse({"status": "error", "message": f"Compilation failed: {err_msg}"}, status_code=500)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
    finally:
        import shutil
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

@app.api_route("/pdf/{filename}", methods=["GET", "HEAD"])
async def serve_pdf(filename: str):
    # Backward compatibility: Redirect to artifact store
    path = os.path.join(artifact_store.base_dir, filename)
    if os.path.exists(path) and os.path.isfile(path):
        import mimetypes
        mt, _ = mimetypes.guess_type(path)
        return FileResponse(path, media_type=mt or "application/pdf")
    # Fallback to older search
    for job in latex_jobs_store.values():
        if job.pdf_path and os.path.basename(job.pdf_path) == filename:
            if os.path.exists(job.pdf_path):
                return FileResponse(job.pdf_path, media_type="application/pdf")
    return JSONResponse({"error": "PDF file not found"}, status_code=404)

@app.get("/api/diagnostics/groq")
async def test_groq():
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key or api_key.startswith("your_"):
        return JSONResponse({"status": "error", "message": "GROQ_API_KEY is not configured (placeholder detected in backend/.env)"}, status_code=400)
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[{"role": "user", "content": "Ping"}],
            max_tokens=5
        )
        return {"status": "ok", "message": "Groq connected"}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/api/diagnostics/gemini")
async def test_gemini():
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key or api_key.startswith("your_"):
        return JSONResponse({"status": "error", "message": "GOOGLE_API_KEY is not configured (placeholder detected in backend/.env)"}, status_code=400)
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        # Try available Gemini models
        last_err = None
        for m in ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-3.5-flash-lite']:
            try:
                model = genai.GenerativeModel(m)
                resp = model.generate_content("Ping")
                return {"status": "ok", "message": f"Gemini connected ({m})"}
            except Exception as ex:
                last_err = ex
                continue
        return JSONResponse({"status": "error", "message": str(last_err)}, status_code=500)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/api/diagnostics/tectonic")
async def test_tectonic():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_tectonic = os.path.join(project_root, "tectonic.exe")
    tectonic_cmd = local_tectonic if os.path.exists(local_tectonic) else "tectonic"

    try:
        result = subprocess.run([tectonic_cmd, "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return {"status": "ok", "message": "Tectonic found"}
    except (FileNotFoundError, Exception):
        return JSONResponse({"status": "error", "message": "Tectonic binary not found"}, status_code=500)

    return JSONResponse({"status": "error", "message": "Tectonic binary not found"}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    import socket

    def _is_port_bindable(p: int, host: str = "0.0.0.0") -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, p))
                return True
            except OSError:
                return False

    desired_port = config.BACKEND_PORT
    selected_port = desired_port

    if not _is_port_bindable(selected_port):
        # On Windows, ports like 8000 are frequently blocked by Windows NAT / Hyper-V exclusion ranges (WinError 10013)
        fallbacks = [8888, 5050, 5000, 9000]
        for fb in fallbacks:
            if _is_port_bindable(fb):
                print(f"[LocalServer] Port {selected_port} is blocked/unavailable. Automatically falling back to port {fb}.")
                selected_port = fb
                os.environ["PORT"] = str(fb)
                config.BACKEND_URL = f"http://localhost:{fb}"
                break

    uvicorn.run(app, host="0.0.0.0", port=selected_port)
