"""AnnotationHandler — processes canvas annotation events for generated videos."""

import os
import requests
from typing import List, Optional, Tuple

from backend.video_generation.models import VideoJob, AnnotationEvent
from backend.workspace.qdrant_store import QdrantRAGStore


class ResearchAgent:
    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY")

    def research(self, query: str) -> str:
        if not self.api_key:
            return f"General knowledge context for: {query}"
        try:
            resp = requests.post(
                "https://api.tavily.com/search",
                json={"api_key": self.api_key, "query": query, "search_depth": "basic"},
                timeout=10,
            )
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                return "\n".join(r.get("content", "") for r in results[:3])
        except Exception as e:
            print(f"[ResearchAgent] Web search error: {e}")
        return f"Fallback context for: {query}"


class AnnotationHandler:
    def __init__(self, rag_store: Optional[QdrantRAGStore] = None):
        self.rag_store = rag_store or QdrantRAGStore()
        self.research_agent = ResearchAgent()

    def process_annotations(self, job: VideoJob, annotations: List[AnnotationEvent]) -> VideoJob:
        from backend.video_generation.agents.codegen_agent import CodeGenAgent
        from backend.video_generation.agents.renderer_agent import RendererAgent
        from backend.ci.pipeline import CIPipelineHarness

        if not annotations:
            return job

        annotations = sorted(annotations, key=lambda a: a.timestamp)
        codegen_agent = CodeGenAgent()
        renderer_agent = RendererAgent()
        ci_harness = CIPipelineHarness()
        annotation_clips: List[Tuple[float, str]] = []
        annotation_results = []

        for idx, ann in enumerate(annotations):
            query = ann.comment or "Explain this highlighted region."
            visual_description = self._describe_frame(ann.frame_image, ann.comment)
            results = self.rag_store.search(query, job.material_id or job.job_id, top_k=3)
            if results and results[0]["score"] > 0.5:
                context = "\n".join(r["text"] for r in results)
                annotation_source = "rag"
            else:
                context = self.research_agent.research(f"{query}. {visual_description}")
                annotation_source = "web_search"

            clip_job = VideoJob(
                job_id=f"{job.job_id}_ann_{idx}",
                user_prompt=(
                    f"Create a short 5-15 second visual explanation for: {query}.\n"
                    f"Visual context: {visual_description}\n"
                    f"Reference material: {context[:2000]}"
                ),
                document_text=context,
                story_script=(
                    "## Scene 1: Annotation focus\n"
                    f"- Visual: Focus only on the highlighted idea: {query}\n"
                    f"- Narration: {visual_description or query}\n"
                    "## Scene 2: Clarification\n"
                    "- Visual: Show the relationship or correction with a compact diagram."
                ),
            )

            for attempt in range(2):
                clip_job = codegen_agent.run(clip_job)
                # CodeGenAgent and RendererAgent both use MainScene. The old code
                # validated AnnotationScene, causing a guaranteed class mismatch.
                passed, error_trace = ci_harness.validate_code(
                    clip_job.manim_code or "", scene_name="MainScene"
                )
                if passed:
                    clip_job.has_build_error = False
                    break
                clip_job.has_build_error = True
                clip_job.build_error_trace = error_trace
                clip_job.retry_count += 1
                print(f"[AnnotationHandler] CI retry {attempt+1} for ann[{idx}]: {error_trace[:120]}")

            if clip_job.has_build_error:
                print(f"[AnnotationHandler] Skipping ann[{idx}] — CI failed after retries.")
                continue

            clip_job = renderer_agent.run(clip_job)
            if clip_job.video_path and os.path.exists(clip_job.video_path):
                annotation_clips.append((ann.timestamp, clip_job.video_path))
                annotation_results.append({
                    "timestamp": ann.timestamp,
                    "annotation_source": annotation_source,
                    "context_used": context[:200],
                })

        if annotation_clips and job.video_path and os.path.exists(job.video_path):
            job.version += 1
            stitched_path = self._stitch(job.video_path, annotation_clips, job.job_id, job.version)
            if stitched_path:
                job.stitched_video_url = stitched_path
                job.video_url = stitched_path

        job.annotation_context = {"results": annotation_results}
        return job

    def _describe_frame(self, frame_image_b64: str, comment: str) -> str:
        if not frame_image_b64:
            return comment
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return comment
        try:
            from groq import Groq
            client = Groq(api_key=api_key)
            image_url = frame_image_b64 if frame_image_b64.startswith("data:image") else f"data:image/png;base64,{frame_image_b64}"
            response = client.chat.completions.create(
                model="llama-3.2-11b-vision-preview",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Describe only what is highlighted/circled in this video frame. User question: {comment}"},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }],
            )
            return response.choices[0].message.content or comment
        except Exception as e:
            print(f"[AnnotationHandler] Groq Vision description failed: {e}")
            return comment

    def _stitch(
        self,
        original_path: str,
        clips: List[Tuple[float, str]],
        job_id: str,
        version: int,
    ) -> Optional[str]:
        import subprocess
        import tempfile

        output_path = os.path.join(tempfile.gettempdir(), f"{job_id}-v{version}.mp4")
        try:
            concat_list_path = os.path.join(tempfile.gettempdir(), f"{job_id}_concat.txt")
            with open(concat_list_path, "w", encoding="utf-8") as f:
                prev_end = 0.0
                for ann_idx, (timestamp, clip_path) in enumerate(sorted(clips, key=lambda x: x[0])):
                    seg_path = os.path.join(tempfile.gettempdir(), f"{job_id}_seg_{ann_idx}.mp4")
                    subprocess.run([
                        "ffmpeg", "-y", "-i", original_path,
                        "-ss", str(prev_end), "-to", str(timestamp),
                        "-c", "copy", seg_path,
                    ], capture_output=True, timeout=60)
                    if os.path.exists(seg_path) and timestamp > prev_end:
                        f.write(f"file '{seg_path}'\n")
                    f.write(f"file '{clip_path}'\n")
                    prev_end = timestamp

                tail_path = os.path.join(tempfile.gettempdir(), f"{job_id}_tail.mp4")
                subprocess.run([
                    "ffmpeg", "-y", "-i", original_path,
                    "-ss", str(prev_end), "-c", "copy", tail_path,
                ], capture_output=True, timeout=60)
                if os.path.exists(tail_path):
                    f.write(f"file '{tail_path}'\n")

            result = subprocess.run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", concat_list_path, "-c", "copy", output_path,
            ], capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                print(f"[AnnotationHandler] ffmpeg stitch error: {result.stderr}")
                return None
            return output_path
        except Exception as e:
            print(f"[AnnotationHandler] Stitch failed: {e}")
            return None
