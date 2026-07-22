import os
import uuid
import tempfile
from dotenv import load_dotenv

# Load backend/.env environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

try:
    import imageio_ffmpeg
    ffmpeg_dir = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
    os.environ["PATH"] += os.pathsep + ffmpeg_dir
    print(f"[Setup] Injected FFmpeg into PATH from {ffmpeg_dir}")
except ImportError:
    pass

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from backend.pipeline.models import VideoJob, AnnotationEvent, PathData
from backend.pipeline.graph import VideoGenerationPipeline
from backend.rag.qdrant_store import QdrantRAGStore
from backend.pipeline.annotation_handler import AnnotationHandler

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
    pdf: UploadFile = File(None)
):
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    pdf_path = ""
    
    if pdf:
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        content = await pdf.read()
        temp_pdf.write(content)
        temp_pdf.close()
        pdf_path = temp_pdf.name

    job = VideoJob(
        job_id=job_id,
        pdf_path=pdf_path,
        user_prompt=prompt,
        document_text="",
    )
    jobs_store[job_id] = job

    background_tasks.add_task(run_job_background, job)

    return {
        "job_id": job_id,
        "status": "processing",
        "message": "Video generation pipeline started for uploaded document."
    }

@app.get("/status/{job_id}")
async def status(job_id: str):
    if job_id not in jobs_store:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    
    job = jobs_store[job_id]
    
    video_url = None
    if job.video_path and os.path.exists(job.video_path):
        filename = os.path.basename(job.video_path)
        video_url = f"http://localhost:8000/video/{filename}"

    return {
        "job_id": job.job_id,
        "status": job.status.value if hasattr(job.status, "value") else str(job.status),
        "step": job.step,
        "progress_percentage": job.progress_percentage,
        "video_url": video_url or job.video_url,
        "error_message": job.error_message,
        "version": job.version,
        "story_script": job.story_script
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
        video_url = f"http://localhost:8000/video/{filename}"

    return {
        "job_id": updated_job.job_id,
        "status": "updated",
        "version": updated_job.version,
        "video_url": video_url
    }

@app.api_route("/video/{filename}", methods=["GET", "HEAD"])
async def serve_video(filename: str):
    # Find matching file in temp or job directories
    for job in jobs_store.values():
        if job.video_path and os.path.basename(job.video_path) == filename:
            if os.path.exists(job.video_path):
                return FileResponse(job.video_path, media_type="video/mp4")
    return JSONResponse({"error": "Video file not found"}, status_code=404)

@app.get("/test-llm")
async def test_llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return JSONResponse({"status": "error", "message": "GROQ_API_KEY is missing from backend/.env"}, status_code=400)
    
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant", # Fast/cheap model for testing
            messages=[{"role": "user", "content": "Reply with exactly one word: OK"}],
            max_tokens=10
        )
        reply = resp.choices[0].message.content
        if reply:
            return {"status": "success", "message": f"Groq API working! (Response: {reply.strip()})"}
                
        return JSONResponse({"status": "error", "message": "LLM returned empty response."}, status_code=500)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
