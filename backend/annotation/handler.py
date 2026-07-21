import os
import requests
from typing import List
from backend.pipeline.models import VideoJob, AnnotationEvent
from backend.rag.qdrant_store import QdrantRAGStore
from backend.pipeline.agents.codegen_agent import CodeGenAgent
from backend.pipeline.agents.renderer_agent import RendererAgent
from backend.annotation.stitcher import VideoStitcher

class ResearchAgent:
    """Tavily web search tool fallback for out-of-document queries."""
    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY")

    def search(self, query: str) -> str:
        if not self.api_key:
            return f"General knowledge search summary for: {query}"
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
        return f"Fallback web context for question: {query}"

class AnnotationHandler:
    def __init__(self, rag_store: QdrantRAGStore):
        self.rag_store = rag_store
        self.research_agent = ResearchAgent()
        self.codegen_agent = CodeGenAgent()
        self.renderer_agent = RendererAgent()
        self.stitcher = VideoStitcher()

    def process_annotations(self, job: VideoJob, annotations: List[AnnotationEvent]) -> VideoJob:
        if not annotations:
            return job

        new_clip_paths = []
        for index, ann in enumerate(annotations):
            query = ann.comment or "Explain this highlight in detail."
            # Vector search in Qdrant
            results = self.rag_store.search(query, job.job_id, top_k=2)
            
            if results and results[0]["score"] > 0.5:
                context = "\n".join([r["text"] for r in results])
            else:
                context = self.research_agent.search(query)

            # Generate clip manim code
            clip_prompt_job = VideoJob(
                job_id=f"{job.job_id}_ann_{index}",
                pdf_path=job.pdf_path,
                user_prompt=f"Create a short 5-10 second Manim clip explaining: {query}.\nContext: {context}",
                story_script=f"Short visual response to user highlight: {query}"
            )
            clip_prompt_job = self.codegen_agent.run(clip_prompt_job)
            clip_prompt_job = self.renderer_agent.run(clip_prompt_job)
            
            if clip_prompt_job.video_path and os.path.exists(clip_prompt_job.video_path):
                new_clip_paths.append((ann.timestamp, clip_prompt_job.video_path))

        if new_clip_paths and job.video_path:
            job.version += 1
            stitched_path = self.stitcher.stitch_clips(job.video_path, new_clip_paths, job.job_id, job.version)
            job.video_path = stitched_path
            job.stitched_video_url = f"/api/video/{job.job_id}_v{job.version}.mp4"
            job.video_url = job.stitched_video_url

        return job
