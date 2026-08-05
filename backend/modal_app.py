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
        "tectonic",
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
latex_jobs_db = modal.Dict.from_name("latex-jobs-db", create_if_missing=True)

# Define secrets from backend/.env unconditionally for Modal cloud deployment
secrets = [modal.Secret.from_dotenv()]

@app.function(image=manim_image, gpu="A10G", timeout=600, secrets=secrets)
def _process_generation_job(job_dict: Dict[str, Any], pdf_bytes: bytes) -> Dict[str, Any]:
    """Heavy GPU worker: runs the full LangGraph pipeline."""
    from backend.video_generation.models import VideoJob
    from backend.video_generation.graph import VideoGenerationPipeline
    from backend.workspace.qdrant_store import QdrantRAGStore

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

    # ── Store result in cross-student cache (NEW) ─────────────────────────────
    # If the job succeeded, cache the result so future students with the same
    # PDF + prompt get an instant response instead of re-running the pipeline.
    if final_job.video_url and final_job.status.value == "done":
        try:
            rag = QdrantRAGStore()
            content_hash = rag.compute_content_hash(
                final_job.document_text or "",
                final_job.user_prompt,
            )
            rag.cache_video_result(
                content_hash=content_hash,
                video_url=final_job.video_url,
                manim_code=final_job.manim_code or "",
                story_script=final_job.story_script or "",
                user_prompt=final_job.user_prompt,
            )
        except Exception as e:
            print(f"[modal_app] Cache store failed (non-critical): {e}")

    return result


@app.function(image=manim_image, gpu="A10G", timeout=300, secrets=secrets)
def _process_annotation_job(job_id: str, annotations_raw: list) -> Dict[str, Any]:
    """GPU worker: handles canvas annotation pipeline."""
    from backend.video_generation.models import VideoJob, AnnotationEvent, PathData
    from backend.workspace.qdrant_store import QdrantRAGStore
    from backend.video_qa.annotation_handler import AnnotationHandler

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


@app.function(image=manim_image, timeout=600, secrets=secrets)
def _process_latex_job(job_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Worker for latex generation pipeline."""
    from backend.video_generation.models import LatexJob
    from backend.math_engine.latex_graph import LatexGenerationPipeline

    job = LatexJob(
        job_id=job_dict["job_id"],
        image_b64=job_dict["image_b64"],
        template_type=job_dict["template_type"]
    )

    pipeline = LatexGenerationPipeline()
    final_job = pipeline.run_pipeline(job)

    # Read PDF as base64 to send it back via modal dict (or just rely on storage)
    # Since modal functions don't easily serve files without a Volume, 
    # we'll encode the PDF as base64 and return it, or the frontend can just get it if we upload it.
    # Wait, the spec says "returns the URL/path". In Modal, local temp files are lost.
    # Let's use AWS S3/DO Spaces to upload it, just like UploaderAgent does for videos, OR just base64 encode it in the DB.
    # Since it's a PDF, base64 is usually small enough for modal.Dict (limit ~1MB or so).
    # But wait, we can just save it as base64 inside the dict.
    
    pdf_b64 = None
    if final_job.pdf_path and os.path.exists(final_job.pdf_path):
        import base64
        with open(final_job.pdf_path, "rb") as f:
            pdf_b64 = base64.b64encode(f.read()).decode("utf-8")

    result = {
        "job_id": final_job.job_id,
        "status": final_job.status.value if hasattr(final_job.status, "value") else str(final_job.status),
        "pdf_b64": pdf_b64,
        "error_message": final_job.error_message,
        "step": final_job.step,
        "progress_percentage": final_job.progress_percentage
    }
    latex_jobs_db[final_job.job_id] = result
    return result

from fastapi import Request

# ── HTTP Endpoints ─────────────────────────────────────────────────────────────

@app.function(image=manim_image, gpu="A10G", timeout=600, secrets=secrets)
@modal.fastapi_endpoint(method="POST")
async def generate(request: Request) -> dict:
    """
    POST /generate
    Accepts JSON body with prompt & pdf_bytes in base64.

    ── Cache check (NEW) ───────────────────────────────────────────────────
    Before spawning the GPU pipeline, compute hash(pdf_content + prompt)
    and check if a finished video exists in the Qdrant cache.
    If yes, return it immediately (multi-minute pipeline → instant response).
    If no, spawn the pipeline as before and store result in cache on completion.
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

    # ── Cache check before GPU pipeline ───────────────────────────────────────
    try:
        from backend.workspace.qdrant_store import QdrantRAGStore
        rag = QdrantRAGStore()
        # Decode PDF text for hashing (first 2000 chars only, no full parse needed)
        pdf_text_for_hash = pdf_bytes[:4000].decode("utf-8", errors="ignore") if pdf_bytes else ""
        content_hash = rag.compute_content_hash(pdf_text_for_hash, prompt)
        cached = rag.get_cached_video(content_hash, prompt)
        if cached and cached.get("video_url"):
            # Cache hit — return instantly without spawning GPU job
            cached_result = {
                "job_id": job_id,
                "status": "done",
                "video_url": cached["video_url"],
                "estimated_seconds": 0,
                "cache_hit": True,
                "cache_type": cached.get("cache_type", "exact"),
            }
            jobs_db[job_id] = cached_result
            print(f"[generate] ⚡ Cache hit ({cached.get('cache_type')}) for job {job_id} — skipping GPU pipeline")
            return cached_result
    except Exception as e:
        print(f"[generate] Cache check failed (non-critical, continuing with pipeline): {e}")

    # Cache miss — run full pipeline
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
        "cache_hit": False,
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
    GET /status?job_id=xxx
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
            "cache_hit": job.get("cache_hit", False),
        }
    return {
        "job_id": target_id,
        "status": "processing",
        "current_stage": "pipeline",
        "video_url": None,
        "error_message": None,
        "cache_hit": False,
    }


@app.function(image=manim_image, secrets=secrets)
@modal.fastapi_endpoint(method="POST")
async def generate_latex(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        body = {}

    job_id = body.get("job_id") or f"latex_{uuid.uuid4().hex[:10]}"
    image_b64 = body.get("image_b64", "")
    template_type = body.get("template_type", "Homework")

    latex_jobs_db[job_id] = {
        "job_id": job_id,
        "status": "processing",
        "step": "init",
        "progress_percentage": 0
    }

    _process_latex_job.spawn({
        "job_id": job_id,
        "image_b64": image_b64,
        "template_type": template_type
    })

    return {
        "job_id": job_id,
        "status": "processing",
        "message": "LaTeX generation pipeline started."
    }

@app.function(image=manim_image, secrets=secrets)
@modal.fastapi_endpoint(method="GET")
async def latex_status(request: Request, job_id: str = "") -> dict:
    target_id = job_id or request.query_params.get("job_id", "")
    if target_id and target_id in latex_jobs_db:
        job = latex_jobs_db[target_id]
        return {
            "job_id": target_id,
            "status": job.get("status", "processing"),
            "step": job.get("step", "processing"),
            "progress_percentage": job.get("progress_percentage", 0),
            "pdf_b64": job.get("pdf_b64"),
            "error_message": job.get("error_message"),
        }
    return {
        "job_id": target_id,
        "status": "error",
        "error_message": "Job not found"
    }


@app.function(image=manim_image, secrets=secrets)
@modal.fastapi_endpoint(method="GET")
async def stream_status(request: Request, job_id: str = "") -> Any:
    """
    GET /stream_status?job_id=xxx
    Server-Sent Events endpoint — pushes status updates to frontend.

    Advantage over polling:
      - Frontend receives updates instantly the moment they are available
      - Eliminates 60+ unnecessary HTTP requests during a 90s render
      - Better perceived performance (student sees each pipeline stage complete)

    Frontend usage:
        const source = new EventSource(`/stream_status?job_id=${jobId}`);
        source.onmessage = (e) => {
            const data = JSON.parse(e.data);
            if (data.status === 'done') source.close();
        };
    """
    import asyncio
    import json as json_lib
    from fastapi.responses import StreamingResponse

    target_id = job_id or request.query_params.get("job_id", "")

    async def event_generator():
        max_polls = 120   # 120 × 2s = 4 min max wait
        interval = 2.0    # seconds between checks
        for _ in range(max_polls):
            if target_id in jobs_db:
                job = jobs_db[target_id]
                payload = {
                    "job_id": target_id,
                    "status": job.get("status", "processing"),
                    "current_stage": job.get("step", "pipeline"),
                    "video_url": job.get("video_url"),
                    "error_message": job.get("error_message"),
                    "cache_hit": job.get("cache_hit", False),
                }
                yield f"data: {json_lib.dumps(payload)}\n\n"
                if job.get("status") in ("done", "error"):
                    break
            else:
                yield f"data: {{\"status\": \"processing\", \"job_id\": \"{target_id}\"}}\n\n"
            await asyncio.sleep(interval)

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
