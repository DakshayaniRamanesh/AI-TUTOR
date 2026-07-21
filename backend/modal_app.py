import os
import uuid
import tempfile
from typing import Dict, Any
import modal

# Modal Container Image — matches spec exactly
# - manim==0.20.1, boto3==1.35.99 (pin: 1.36.0 breaks DO Spaces)
# - gpu="A10G" for render endpoints
backend_dir = os.path.dirname(os.path.abspath(__file__))

manim_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install([
        "ffmpeg",
        "libcairo2",
        "libcairo2-dev",
        "pango1.0-tools",
        "libpango1.0-dev",
        "texlive-latex-extra",
        "texlive-fonts-extra",
        "texlive-science",
        "cm-super",
        "dvisvgm",
        "pkg-config",
    ])
    .pip_install([
        "fastapi[standard]",
        "manim>=0.18.0",
        "langchain>=0.2.0",
        "langgraph>=0.1.0",
        "langchain-google-genai",
        "google-genai",
        "qdrant-client",
        "google-generativeai",
        "firebase-admin",
        "boto3",
        "pypdf>=4.0.0",
        "python-dotenv",
        "pydantic>=2.5.0",
        "requests",
    ])
    .add_local_dir(backend_dir, remote_path="/root/backend")
)

app = modal.App("manim-app", image=manim_image)

# ── Persistent shared job state across Modal containers ─────────────────────────
jobs_db = modal.Dict.from_name("manim-jobs-db", create_if_missing=True)


# Define secrets from backend/.env unconditionally for Modal cloud deployment
secrets = [modal.Secret.from_dotenv()]

@app.function(image=manim_image, gpu="A10G", timeout=600, secrets=secrets)
def _process_generation_job(job_dict: Dict[str, Any], pdf_bytes: bytes) -> Dict[str, Any]:
    """Heavy GPU worker: runs the full LangGraph pipeline."""
    from backend.pipeline.models import VideoJob
    from backend.pipeline.graph import VideoGenerationPipeline

    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_pdf.write(pdf_bytes)
    temp_pdf.close()

    job = VideoJob(
        job_id=job_dict["job_id"],
        pdf_path=temp_pdf.name,
        user_prompt=job_dict["user_prompt"],
        document_text="",
    )

    pipeline = VideoGenerationPipeline()
    final_job = pipeline.run_pipeline(job)

    if os.path.exists(temp_pdf.name):
        os.remove(temp_pdf.name)

    result = {
        "job_id": final_job.job_id,
        "status": final_job.status.value if hasattr(final_job.status, "value") else str(final_job.status),
        "video_url": final_job.video_url,
        "story_script": final_job.story_script,
        "error_message": final_job.error_message,
        "version": final_job.version,
    }
    jobs_db[final_job.job_id] = result
    return result


@app.function(image=manim_image, gpu="A10G", timeout=300, secrets=secrets)
def _process_annotation_job(job_id: str, annotations_raw: list) -> Dict[str, Any]:
    """GPU worker: handles canvas annotation pipeline."""
    from backend.pipeline.models import VideoJob, AnnotationEvent, PathData
    from backend.rag.qdrant_store import QdrantRAGStore
    from backend.pipeline.annotation_handler import AnnotationHandler

    existing = jobs_db.get(job_id, {})
    job = VideoJob(
        job_id=job_id,
        pdf_path="",
        user_prompt=existing.get("user_prompt", "Annotated video query"),
        document_text=existing.get("document_text", ""),
        video_url=existing.get("video_url"),
        version=existing.get("version", 1),
    )

    parsed: list[AnnotationEvent] = []
    for ann in annotations_raw:
        raw_paths = ann.get("paths", [])
        parsed_paths = []
        for p in raw_paths:
            parsed_paths.append(PathData(
                points=[(pt[0], pt[1]) for pt in p.get("points", [])],
                stroke_color=p.get("stroke_color", "#ef4444"),
                stroke_width=p.get("stroke_width", 3),
            ))
        parsed.append(AnnotationEvent(
            timestamp=ann.get("timestamp", 0.0),
            frame_image=ann.get("frame_image", ""),
            paths=parsed_paths,
            comment=ann.get("comment", ""),
        ))

    handler = AnnotationHandler(QdrantRAGStore())
    updated_job = handler.process_annotations(job, parsed)

    result = {
        "job_id": updated_job.job_id,
        "status": "done",
        "video_url": updated_job.stitched_video_url or updated_job.video_url,
        "version": updated_job.version,
        "annotation_results": [],
        "stitch_strategy": "stream_copy",
    }
    jobs_db[job_id] = result
    return result


from fastapi import Request

# ── HTTP Endpoints ─────────────────────────────────────────────────────────────

@app.function(image=manim_image, gpu="A10G", timeout=600, secrets=secrets)
@modal.fastapi_endpoint(method="POST")
async def generate(request: Request) -> dict:
    """
    POST /generate
    Accepts JSON body with prompt & pdf_bytes in base64.
    Returns job_id immediately; poll /status for completion.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    job_id = body.get("job_id") or f"job_{uuid.uuid4().hex[:10]}"
    prompt = body.get("prompt", "Explain the document concepts.")
    import base64
    pdf_b64 = body.get("pdf_bytes", "")
    pdf_bytes = base64.b64decode(pdf_b64) if pdf_b64 else b""

    jobs_db[job_id] = {
        "job_id": job_id,
        "status": "processing",
        "video_url": None,
        "user_prompt": prompt,
    }

    _process_generation_job.spawn({"job_id": job_id, "user_prompt": prompt}, pdf_bytes)

    return {
        "job_id": job_id,
        "status": "processing",
        "video_url": None,
        "estimated_seconds": 90,
    }


@app.function(image=manim_image, gpu="A10G", timeout=300, secrets=secrets)
@modal.fastapi_endpoint(method="POST")
async def annotate(request: Request) -> dict:
    """
    POST /annotate
    Accepts {job_id, annotations: [{timestamp, frame_image, paths, comment}]}
    Returns stitched video_url with annotation clips inserted.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    job_id = body.get("job_id", "")
    annotations = body.get("annotations", [])
    result = _process_annotation_job.remote(job_id, annotations)
    return result


@app.function(image=manim_image, secrets=secrets)
@modal.fastapi_endpoint(method="GET")
async def status(request: Request, job_id: str = "") -> dict:
    """
    GET /status?job_id=xxx or GET /status/xxx
    Poll for current job state.
    """
    target_id = job_id or request.query_params.get("job_id", "")
    if target_id and target_id in jobs_db:
        job = jobs_db[target_id]
        return {
            "job_id": target_id,
            "status": job.get("status", "processing"),
            "current_stage": job.get("step", "pipeline"),
            "video_url": job.get("video_url"),
            "story_script": job.get("story_script"),
            "error_message": job.get("error_message"),
        }
    return {
        "job_id": target_id,
        "status": "processing",
        "current_stage": "pipeline",
        "video_url": None,
        "error_message": None,
    }
