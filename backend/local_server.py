import os
import uuid
import tempfile
import subprocess
import base64
import zipfile
import io
import json
import urllib.request
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)



# Permanent media directory where rendered videos are stored
MEDIA_DIR = os.path.join(os.path.dirname(__file__), "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

try:
    import imageio_ffmpeg
    ffmpeg_dir = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
    os.environ["PATH"] += os.pathsep + ffmpeg_dir
except ImportError:
    pass

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from backend.video_generation.models import VideoJob, AnnotationEvent, PathData, LatexJob, BoardSelection
from backend.video_generation.graph import VideoGenerationPipeline
from backend.math_engine.latex_graph import LatexGenerationPipeline
from backend.workspace.qdrant_store import QdrantRAGStore
from backend.video_qa.annotation_handler import AnnotationHandler

app = FastAPI(title="Manim AI Local Pipeline Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs_store: dict[str, VideoJob] = {}
pipeline = VideoGenerationPipeline()
latex_jobs_store: dict[str, LatexJob] = {}
latex_pipeline = LatexGenerationPipeline()


def run_job_background(job: VideoJob):
    try:
        final_job = pipeline.run_pipeline(job)
        jobs_store[job.job_id] = final_job
    except Exception as e:
        job.status = "error"
        job.error_message = str(e)
        jobs_store[job.job_id] = job


@app.post("/generate")
async def generate(
    background_tasks: BackgroundTasks,
    prompt: str = Form(...),
    pdf: UploadFile = File(None),
    page_range: str = Form(""),
    emphasis_note: str = Form(""),
    output_type: str = Form("video"),
    subject_id: str = Form(""),
    selection_json: str = Form(""),
):
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    pdf_path = ""
    if pdf:
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        content = await pdf.read()
        temp_pdf.write(content)
        temp_pdf.close()
        pdf_path = temp_pdf.name

    board_selection = None
    if selection_json:
        try:
            parsed = json.loads(selection_json)
            board_selection = BoardSelection.from_dict(parsed)
        except Exception as exc:
            return JSONResponse(
                {"error": f"Invalid selection_json: {exc}"},
                status_code=400,
            )

    job = VideoJob(
        job_id=job_id,
        pdf_path=pdf_path,
        user_prompt=prompt,
        document_text="",
        page_range=page_range if page_range else None,
        emphasis_note=emphasis_note if emphasis_note else None,
        output_type=output_type,
        subject_id=subject_id if subject_id else None,
        board_selection=board_selection,
    )
    jobs_store[job_id] = job
    background_tasks.add_task(run_job_background, job)
    return {
        "job_id": job_id,
        "status": "processing",
        "message": "Video generation pipeline started.",
        "whiteboard_selection": bool(board_selection and board_selection.has_content()),
    }


@app.get("/status/{job_id}")
async def status(job_id: str):
    if job_id not in jobs_store:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    job = jobs_store[job_id]

    # Determine the best video URL to return
    video_url = None
    video_local_path = None
    if job.video_path and os.path.exists(job.video_path):
        video_local_path = job.video_path
        filename = os.path.basename(job.video_path)
        video_url = f"http://localhost:8000/video/{filename}"
    elif job.video_url and job.video_url.startswith("http"):
        video_url = job.video_url

    return {
        "job_id": job.job_id,
        "status": job.status.value if hasattr(job.status, "value") else str(job.status),
        "step": job.step,
        "progress_percentage": job.progress_percentage,
        "video_url": video_url,
        "video_local_path": video_local_path,
        "error_message": job.error_message,
        "version": job.version,
        "story_script": job.story_script,
        "board_topic": getattr(job.board_ir, "probable_topic", "") if job.board_ir else "",
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
                comment=ann.get("comment", ""),
            )
        )
    handler = AnnotationHandler(QdrantRAGStore())
    updated_job = handler.process_annotations(job, parsed_annotations)
    jobs_store[job_id] = updated_job
    video_url = updated_job.video_url
    if updated_job.video_path and os.path.exists(updated_job.video_path):
        filename = os.path.basename(updated_job.video_path)
        video_url = f"http://localhost:8000/video/{filename}"
    return {
        "job_id": updated_job.job_id,
        "status": "updated",
        "version": updated_job.version,
        "video_url": video_url,
    }


@app.api_route("/video/{filename}", methods=["GET", "HEAD"])
async def serve_video(filename: str):
    # 1. Check the permanent media directory first
    media_path = os.path.join(MEDIA_DIR, filename)
    if os.path.exists(media_path):
        return FileResponse(media_path, media_type="video/mp4")
    # 2. Fall back to searching job store (handles temp dir paths still in memory)
    for job in jobs_store.values():
        if job.video_path and os.path.basename(job.video_path) == filename:
            if os.path.exists(job.video_path):
                return FileResponse(job.video_path, media_type="video/mp4")
    return JSONResponse({"error": f"Video file '{filename}' not found"}, status_code=404)


def run_latex_job_background(job: LatexJob):
    try:
        final_job = latex_pipeline.run_pipeline(job)
        latex_jobs_store[job.job_id] = final_job
    except Exception as e:
        job.status = "error"
        job.error_message = str(e)
        latex_jobs_store[job.job_id] = job


@app.post("/generate_latex")
async def generate_latex(
    background_tasks: BackgroundTasks,
    image_b64: str = Form(...),
    template_type: str = Form("Homework"),
    mode: str = Form("study"),
    classroom_action: str = Form("Solve Question"),
):
    job_id = f"latex_{uuid.uuid4().hex[:8]}"
    job = LatexJob(
        job_id=job_id,
        image_b64=image_b64,
        template_type=template_type,
        mode=mode,
        classroom_action=classroom_action,
    )
    latex_jobs_store[job_id] = job
    background_tasks.add_task(run_latex_job_background, job)
    return {
        "job_id": job_id,
        "status": "processing",
        "message": "LaTeX generation pipeline started.",
    }


@app.get("/latex_status/{job_id}")
async def latex_status(job_id: str):
    if job_id not in latex_jobs_store:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    job = latex_jobs_store[job_id]
    pdf_url = None
    if job.pdf_path and os.path.exists(job.pdf_path):
        filename = os.path.basename(job.pdf_path)
        pdf_url = f"http://localhost:8000/pdf/{filename}"
    return {
        "job_id": job.job_id,
        "status": job.status.value if hasattr(job.status, "value") else str(job.status),
        "step": job.step,
        "progress_percentage": job.progress_percentage,
        "pdf_url": pdf_url or job.pdf_url,
        "latex_code": job.final_tex_code or job.structured_latex or job.raw_transcription or "",
        "raw_transcription": job.raw_transcription or "",
        "structured_latex": job.structured_latex or "",
        "error_message": job.error_message,
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
        res = subprocess.run([tectonic_cmd, tex_path], cwd=temp_dir, capture_output=True, text=True, timeout=300)
        if res.returncode == 0 and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as pf:
                pdf_b64 = base64.b64encode(pf.read()).decode()
            return {"status": "ok", "pdf_b64": pdf_b64}
        err_msg = res.stderr or res.stdout or "Compilation error"
        return JSONResponse({"status": "error", "message": f"Compilation failed: {err_msg}"}, status_code=500)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.api_route("/pdf/{filename}", methods=["GET", "HEAD"])
async def serve_pdf(filename: str):
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
        client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[{"role": "user", "content": "Ping"}],
            max_tokens=5,
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
        last_err = None
        for model_name in ["gemini-3.5-flash-lite"]:
            try:
                # Use get_model instead of generate_content to avoid 10s timeout on overloaded API
                info = genai.get_model(f"models/{model_name}")
                return {"status": "ok", "message": f"Gemini connected ({info.name})"}
            except Exception as ex:
                last_err = ex
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
        pass

    try:
        url = "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.17.0/tectonic-0.17.0-x86_64-pc-windows-msvc.zip"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            zip_bytes = resp.read()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if name.endswith("tectonic.exe"):
                    with open(local_tectonic, "wb") as f:
                        f.write(zf.read(name))
                    break
        result = subprocess.run([local_tectonic, "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return {"status": "ok", "message": "Tectonic auto-downloaded & verified"}
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"Tectonic missing & auto-download failed: {e}"}, status_code=500)
    return JSONResponse({"status": "error", "message": "Tectonic binary not found"}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
