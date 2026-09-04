import os
import uuid
import tempfile
import base64
import io
from typing import Dict, Any
import modal
from fastapi import Request

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
        "manim==0.20.1",
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
jobs_db = modal.Dict.from_name("manim-jobs-db", create_if_missing=True)
latex_jobs_db = modal.Dict.from_name("latex-jobs-db", create_if_missing=True)
artifact_volume = modal.Volume.from_name("manim-artifacts-vol", create_if_missing=True)
secrets = [modal.Secret.from_dotenv()]


@app.function(image=manim_image, gpu="A10G", timeout=600, secrets=secrets, volumes={"/root/backend/workspace/artifacts": artifact_volume})
def _process_generation_job(job_dict: Dict[str, Any], pdf_bytes: bytes) -> Dict[str, Any]:
    from backend.video_generation.models import VideoJob, BoardSelection
    from backend.video_generation.graph import VideoGenerationPipeline
    from backend.workspace.qdrant_store import QdrantRAGStore

    temp_pdf_path = ""
    if pdf_bytes:
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        temp_pdf.write(pdf_bytes)
        temp_pdf.close()
        temp_pdf_path = temp_pdf.name

    board_selection = BoardSelection.from_dict(job_dict.get("board_selection"))
    job = VideoJob(
        job_id=job_dict["job_id"],
        pdf_path=temp_pdf_path,
        user_prompt=job_dict["user_prompt"],
        document_text="",
        page_range=job_dict.get("page_range") or None,
        emphasis_note=job_dict.get("emphasis_note") or None,
        output_type=job_dict.get("output_type") or "video",
        subject_id=job_dict.get("subject_id") or None,
        board_selection=board_selection,
    )

    pipeline = VideoGenerationPipeline()
    final_job = pipeline.run_pipeline(job)

    if temp_pdf_path and os.path.exists(temp_pdf_path):
        os.remove(temp_pdf_path)

    result = {
        "job_id": final_job.job_id,
        "status": final_job.status.value if hasattr(final_job.status, "value") else str(final_job.status),
        "video_url": final_job.video_url,
        "story_script": final_job.story_script,
        "error_message": final_job.error_message,
        "version": final_job.version,
        "step": final_job.step,
        "user_prompt": final_job.user_prompt,
        "document_text": final_job.document_text,
        "board_topic": getattr(final_job.board_ir, "probable_topic", "") if final_job.board_ir else "",
    }
    jobs_db[final_job.job_id] = result

    # Full-video semantic cache is intentionally disabled for board selections.
    # The selected whiteboard state must participate in any future scene cache key.
    if (
        not board_selection
        and final_job.video_url
        and getattr(final_job.status, "value", final_job.status) == "done"
    ):
        try:
            rag = QdrantRAGStore()
            cache_prompt = _cache_prompt(job_dict)
            content_hash = rag.compute_content_hash(final_job.document_text or "", cache_prompt)
            rag.cache_video_result(
                content_hash=content_hash,
                video_url=final_job.video_url,
                manim_code=final_job.manim_code or "",
                story_script=final_job.story_script or "",
                user_prompt=cache_prompt,
            )
        except Exception as e:
            print(f"[modal_app] Cache store failed (non-critical): {e}")

    return result


@app.function(image=manim_image, gpu="A10G", timeout=300, secrets=secrets, volumes={"/root/backend/workspace/artifacts": artifact_volume})
def _process_annotation_job(job_id: str, annotations_raw: list) -> Dict[str, Any]:
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

    parsed = [
        AnnotationEvent(
            timestamp=ann.get("timestamp", 0.0),
            frame_image=ann.get("frame_image", ""),
            paths=[
                PathData(
                    points=[(pt[0], pt[1]) for pt in p.get("points", [])],
                    stroke_color=p.get("stroke_color", "#ef4444"),
                    stroke_width=p.get("stroke_width", 3),
                )
                for p in ann.get("paths", [])
            ],
            comment=ann.get("comment", ""),
        )
        for ann in annotations_raw
    ]

    updated_job = AnnotationHandler(QdrantRAGStore()).process_annotations(job, parsed)
    result = {
        "job_id": updated_job.job_id,
        "status": "done",
        "video_url": updated_job.stitched_video_url or updated_job.video_url,
        "version": updated_job.version,
        "annotation_results": updated_job.annotation_context.get("results", []),
        "stitch_strategy": "stream_copy",
        "user_prompt": updated_job.user_prompt,
        "document_text": updated_job.document_text,
    }
    jobs_db[job_id] = result
    return result


@app.function(image=manim_image, timeout=600, secrets=secrets, volumes={"/root/backend/workspace/artifacts": artifact_volume})
def _process_latex_job(job_dict: Dict[str, Any]) -> Dict[str, Any]:
    from backend.video_generation.models import LatexJob
    from backend.math_engine.latex_graph import LatexGenerationPipeline

    job = LatexJob(
        job_id=job_dict["job_id"],
        image_b64=job_dict["image_b64"],
        template_type=job_dict["template_type"],
        mode=job_dict.get("mode", "study"),
        classroom_action=job_dict.get("classroom_action", "Solve Question"),
    )
    final_job = LatexGenerationPipeline().run_pipeline(job)
    pdf_b64 = None
    if final_job.pdf_path and os.path.exists(final_job.pdf_path):
        with open(final_job.pdf_path, "rb") as f:
            pdf_b64 = base64.b64encode(f.read()).decode("utf-8")
    result = {
        "job_id": final_job.job_id,
        "status": final_job.status.value if hasattr(final_job.status, "value") else str(final_job.status),
        "pdf_b64": pdf_b64,
        "error_message": final_job.error_message,
        "step": final_job.step,
        "progress_percentage": final_job.progress_percentage,
    }
    latex_jobs_db[final_job.job_id] = result
    return result


def _cache_prompt(body: Dict[str, Any]) -> str:
    return (
        f"{body.get('prompt', '')}"
        f"||pages={body.get('page_range', '')}"
        f"||emphasis={body.get('emphasis_note', '')}"
        f"||output={body.get('output_type', 'video')}"
    )


def _pdf_text_for_cache(pdf_bytes: bytes, page_range: str = "") -> str:
    if not pdf_bytes:
        return ""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = list(range(min(len(reader.pages), 8)))
        # Cache lookup only needs a stable document fingerprint; do not run the
        # full ingestion parser here.
        parts = [(reader.pages[i].extract_text() or "") for i in pages]
        return "\n".join(parts)[:4000]
    except Exception as exc:
        print(f"[modal_app] PDF cache fingerprint extraction skipped: {exc}")
        return ""


@app.function(image=manim_image, gpu="A10G", timeout=600, secrets=secrets, volumes={"/root/backend/workspace/artifacts": artifact_volume})
@modal.fastapi_endpoint(method="POST")
async def generate(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        body = {}

    job_id = body.get("job_id") or f"job_{uuid.uuid4().hex[:10]}"
    prompt = body.get("user_prompt", "Explain the document concepts.")
    pdf_b64 = body.get("document_text", "")
    try:
        pdf_bytes = base64.b64decode(pdf_b64) if pdf_b64 else b""
    except Exception:
        pdf_bytes = b""
    board_selection = body.get("board_selection") or {}

    # Never use prompt-only full-video semantic cache when board state matters.
    if not board_selection:
        try:
            from backend.workspace.qdrant_store import QdrantRAGStore
            rag = QdrantRAGStore()
            cache_prompt = _cache_prompt(body)
            pdf_text = _pdf_text_for_cache(pdf_bytes, body.get("page_range", ""))
            content_hash = rag.compute_content_hash(pdf_text, cache_prompt)
            cached = rag.get_cached_video(content_hash, cache_prompt)
            if cached and cached.get("video_url"):
                cached_result = {
                    "job_id": job_id,
                    "status": "done",
                    "video_url": cached["video_url"],
                    "estimated_seconds": 0,
                    "cache_hit": True,
                    "cache_type": cached.get("cache_type", "exact"),
                    "user_prompt": prompt,
                }
                jobs_db[job_id] = cached_result
                return cached_result
        except Exception as e:
            print(f"[generate] Cache check failed (non-critical): {e}")

    job_dict = {
        "job_id": job_id,
        "user_prompt": prompt,
        "page_range": body.get("page_range", ""),
        "emphasis_note": body.get("emphasis_note", ""),
        "output_type": body.get("output_type", "video"),
        "subject_id": body.get("subject_id", ""),
        "board_selection": board_selection,
    }
    jobs_db[job_id] = {
        "job_id": job_id,
        "status": "processing",
        "video_url": None,
        "user_prompt": prompt,
        "document_text": "",
        "cache_hit": False,
    }
    _process_generation_job.spawn(job_dict, pdf_bytes)
    return {
        "job_id": job_id,
        "status": "processing",
        "video_url": None,
        "estimated_seconds": 90,
        "cache_hit": False,
        "whiteboard_selection": bool(board_selection),
    }


@app.function(image=manim_image, gpu="A10G", timeout=300, secrets=secrets, volumes={"/root/backend/workspace/artifacts": artifact_volume})
@modal.fastapi_endpoint(method="POST")
async def annotate(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        body = {}
    return _process_annotation_job.remote(body.get("job_id", ""), body.get("annotations", []))


@app.function(image=manim_image, secrets=secrets, volumes={"/root/backend/workspace/artifacts": artifact_volume})
@modal.fastapi_endpoint(method="GET")
async def status(request: Request, job_id: str = "") -> dict:
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
            "board_topic": job.get("board_topic", ""),
        }
    return {
        "job_id": target_id,
        "status": "processing",
        "current_stage": "pipeline",
        "video_url": None,
        "error_message": None,
        "cache_hit": False,
    }


@app.function(image=manim_image, secrets=secrets, volumes={"/root/backend/workspace/artifacts": artifact_volume})
@modal.fastapi_endpoint(method="POST")
async def generate_latex(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        body = {}
    job_id = body.get("job_id") or f"latex_{uuid.uuid4().hex[:10]}"
    latex_jobs_db[job_id] = {
        "job_id": job_id,
        "status": "processing",
        "step": "init",
        "progress_percentage": 0,
    }
    _process_latex_job.spawn({
        "job_id": job_id,
        "image_b64": body.get("image_b64", ""),
        "template_type": body.get("template_type", "Homework"),
        "mode": body.get("mode", "study"),
        "classroom_action": body.get("classroom_action", "Solve Question"),
    })
    return {"job_id": job_id, "status": "processing", "message": "LaTeX generation pipeline started."}


@app.function(image=manim_image, secrets=secrets, volumes={"/root/backend/workspace/artifacts": artifact_volume})
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
    return {"job_id": target_id, "status": "error", "error_message": "Job not found"}


@app.function(image=manim_image, secrets=secrets, volumes={"/root/backend/workspace/artifacts": artifact_volume})
@modal.fastapi_endpoint(method="GET")
async def stream_status(request: Request, job_id: str = "") -> Any:
    import asyncio
    import json as json_lib
    from fastapi.responses import StreamingResponse

    target_id = job_id or request.query_params.get("job_id", "")

    async def event_generator():
        for _ in range(120):
            if target_id in jobs_db:
                job = jobs_db[target_id]
                payload = {
                    "job_id": target_id,
                    "status": job.get("status", "processing"),
                    "current_stage": job.get("step", "pipeline"),
                    "video_url": job.get("video_url"),
                    "error_message": job.get("error_message"),
                    "cache_hit": job.get("cache_hit", False),
                    "board_topic": job.get("board_topic", ""),
                }
                yield f"data: {json_lib.dumps(payload)}\n\n"
                if job.get("status") in ("done", "error"):
                    break
            else:
                yield f"data: {{\"status\": \"processing\", \"job_id\": \"{target_id}\"}}\n\n"
            await asyncio.sleep(2.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.function(image=manim_image, secrets=secrets, volumes={"/root/backend/workspace/artifacts": artifact_volume})
@modal.fastapi_endpoint(method="GET")
async def get_artifact(request: Request, filename: str) -> Any:
    from fastapi.responses import FileResponse, JSONResponse
    import mimetypes
    path = os.path.join("/root/backend/workspace/artifacts", filename)
    if os.path.exists(path) and os.path.isfile(path):
        mt, _ = mimetypes.guess_type(path)
        return FileResponse(path, media_type=mt or "application/octet-stream")
    return JSONResponse({"error": "Artifact not found"}, status_code=404)
