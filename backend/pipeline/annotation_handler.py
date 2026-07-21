"""
AnnotationHandler — processes canvas annotation events.

Spec location: backend/pipeline/annotation_handler.py

For each annotation:
  1. Use gemini-embedding-2 vision to understand the frame_image (multimodal embed)
  2. Qdrant semantic search for relevant document chunks
  3. Fallback to ResearchAgent (web search) if no relevant chunks found
  4. CodeGenAgent generates a standalone AnnotationScene
  5. CI validates it (up to 2 retries)
  6. RendererAgent renders the clip
  7. ffmpeg stitch: stream-copy original + insert annotation clips at timestamps
"""

import os
import base64
import requests
from typing import List, Optional, Tuple

from backend.pipeline.models import VideoJob, AnnotationEvent, JobStatus
from backend.rag.qdrant_store import QdrantRAGStore


class ResearchAgent:
    """Web search fallback for out-of-document queries (uses Tavily)."""

    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY")

    def research(self, query: str) -> str:
        if not self.api_key:
            return f"General knowledge context for: {query}"
        try:
            url = "https://api.tavily.com/search"
            payload = {"api_key": self.api_key, "query": query, "search_depth": "basic"}
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                snippets = [r.get("content", "") for r in results[:3]]
                return "\n".join(snippets)
        except Exception as e:
            print(f"[ResearchAgent] Web search error: {e}")
        return f"Fallback context for: {query}"


class AnnotationHandler:
    """
    Handles canvas annotation events submitted via POST /annotate.

    Steps per annotation:
      - gemini-embedding-2 vision embed of frame_image + comment → semantic query vector
      - Qdrant search(top_k=3) filtered to this job's document chunks
      - If no relevant chunks (score < 0.5) → ResearchAgent web search
      - CodeGenAgent generates a standalone AnnotationScene Manim class
      - CI harness validates (2 retries)
      - RendererAgent renders the annotation clip
    After all annotations: ffmpeg stitch (stream-copy original, insert clips at timestamps)
    """

    def __init__(self, rag_store: Optional[QdrantRAGStore] = None):
        self.rag_store = rag_store or QdrantRAGStore()
        self.research_agent = ResearchAgent()

    def process_annotations(self, job: VideoJob, annotations: List[AnnotationEvent]) -> VideoJob:
        from backend.pipeline.agents.codegen_agent import CodeGenAgent
        from backend.pipeline.agents.renderer_agent import RendererAgent
        from backend.ci.pipeline import CIPipelineHarness

        if not annotations:
            return job

        # Sort by timestamp so stitching is chronological
        annotations = sorted(annotations, key=lambda a: a.timestamp)

        codegen_agent = CodeGenAgent()
        renderer_agent = RendererAgent()
        ci_harness = CIPipelineHarness()

        annotation_clips: List[Tuple[float, str]] = []  # (timestamp, clip_path)
        annotation_results = []

        for idx, ann in enumerate(annotations):
            # 1. Build query from frame_image + comment using Gemini vision
            query = ann.comment or "Explain this highlighted region."
            visual_description = self._describe_frame(ann.frame_image, ann.comment)

            # 2. Qdrant semantic search
            results = self.rag_store.search(query, job.job_id, top_k=3)
            if results and results[0]["score"] > 0.5:
                context = "\n".join([r["text"] for r in results])
                annotation_source = "rag"
            else:
                # 3. Fallback to web search
                context = self.research_agent.research(f"{query}. {visual_description}")
                annotation_source = "web_search"

            print(f"[AnnotationHandler] ann[{idx}] source={annotation_source}, query={query[:60]}")

            # 4. Generate standalone AnnotationScene Manim code
            clip_job = VideoJob(
                job_id=f"{job.job_id}_ann_{idx}",
                user_prompt=(
                    f"Create a short 5-15 second Manim annotation scene explaining: {query}.\n"
                    f"Visual context: {visual_description}\n"
                    f"Reference material: {context[:2000]}"
                ),
                document_text=context,
                story_script=f"Annotation explanation: {query}",
            )

            # CodeGen + CI loop (max 2 retries for annotation clips)
            for attempt in range(2):
                clip_job = codegen_agent.run(clip_job)
                passed, error_trace = ci_harness.validate_code(
                    clip_job.manim_code or "", scene_name="AnnotationScene"
                )
                if passed:
                    clip_job.has_build_error = False
                    break
                clip_job.has_build_error = True
                clip_job.build_error_trace = error_trace
                clip_job.retry_count += 1
                print(f"[AnnotationHandler] CI retry {attempt+1} for ann[{idx}]: {error_trace[:80]}")

            if clip_job.has_build_error:
                print(f"[AnnotationHandler] Skipping ann[{idx}] — CI failed after retries.")
                continue

            # 5. Render annotation clip
            clip_job = renderer_agent.run(clip_job)

            if clip_job.video_path and os.path.exists(clip_job.video_path):
                annotation_clips.append((ann.timestamp, clip_job.video_path))
                annotation_results.append({
                    "timestamp": ann.timestamp,
                    "annotation_source": annotation_source,
                    "context_used": context[:200],
                })

        # 6. Stitch clips into original video
        if annotation_clips and job.video_path and os.path.exists(job.video_path):
            job.version += 1
            stitched_path = self._stitch(job.video_path, annotation_clips, job.job_id, job.version)
            if stitched_path:
                job.stitched_video_url = stitched_path
                job.video_url = stitched_path

        job.annotation_context = {"results": annotation_results}
        return job

    def _describe_frame(self, frame_image_b64: str, comment: str) -> str:
        """
        Use Gemini vision to get a natural-language description of the annotated frame.
        Falls back to the comment text if vision fails or is unavailable.
        """
        if not frame_image_b64:
            return comment

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return comment

        try:
            # Inline image bytes for Gemini vision
            image_data = base64.b64decode(frame_image_b64.split(",")[-1])
            import google.generativeai as genai  # type: ignore
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            from google.generativeai.types import BlobDict
            response = model.generate_content([
                {"mime_type": "image/png", "data": image_data},
                f"Describe what is highlighted/circled in this video frame. User question: {comment}",
            ])
            return response.text or comment
        except Exception as e:
            print(f"[AnnotationHandler] Vision description failed: {e}")
            return comment

    def _stitch(
        self,
        original_path: str,
        clips: List[Tuple[float, str]],
        job_id: str,
        version: int,
    ) -> Optional[str]:
        """
        ffmpeg stream-copy stitch:
          original[0→T1] + ann_clip_1 + original[T1→T2] + ann_clip_2 + ...
        Only new annotation clips are re-encoded; original segments are stream-copied.
        """
        import subprocess
        import tempfile

        output_path = os.path.join(tempfile.gettempdir(), f"{job_id}-v{version}.mp4")

        try:
            # Build ffmpeg concat input list
            concat_list_path = os.path.join(tempfile.gettempdir(), f"{job_id}_concat.txt")
            with open(concat_list_path, "w") as f:
                prev_end = 0.0
                for timestamp, clip_path in sorted(clips, key=lambda x: x[0]):
                    # Original segment before this annotation
                    seg_path = os.path.join(
                        tempfile.gettempdir(), f"{job_id}_seg_{int(prev_end)}.mp4"
                    )
                    subprocess.run([
                        "ffmpeg", "-y", "-i", original_path,
                        "-ss", str(prev_end), "-to", str(timestamp),
                        "-c", "copy", seg_path
                    ], capture_output=True, timeout=60)
                    f.write(f"file '{seg_path}'\n")
                    f.write(f"file '{clip_path}'\n")
                    prev_end = timestamp

                # Final tail of original
                tail_path = os.path.join(tempfile.gettempdir(), f"{job_id}_tail.mp4")
                subprocess.run([
                    "ffmpeg", "-y", "-i", original_path,
                    "-ss", str(prev_end),
                    "-c", "copy", tail_path
                ], capture_output=True, timeout=60)
                f.write(f"file '{tail_path}'\n")

            result = subprocess.run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", concat_list_path, "-c", "copy", output_path
            ], capture_output=True, text=True, timeout=120)

            if result.returncode != 0:
                print(f"[AnnotationHandler] ffmpeg stitch error: {result.stderr}")
                return None

            print(f"[AnnotationHandler] Stitched video: {output_path}")
            return output_path

        except Exception as e:
            print(f"[AnnotationHandler] Stitch failed: {e}")
            return None
