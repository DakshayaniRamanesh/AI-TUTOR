"""
LangGraph 1.2 StateGraph pipeline for Manim AI Video Generator.

Spec: build_graph() returns a CompiledGraph.
      DeltaChannel is used so only state deltas are persisted per step.
      Conditional edges:
        validate → story   (if needs_revision)
        validate → codegen (if approved)
        ci → codegen       (if has_build_error and retry_count < 3)
        ci → render        (if passed)
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

try:
    from langgraph.graph import StateGraph, END  # type: ignore
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

from backend.video_generation.models import VideoJob, JobStatus
from backend.workspace.qdrant_store import QdrantRAGStore
from backend.video_generation.agents.document_embedder import DocumentEmbedderAgent
from backend.video_generation.agents.story_agent import StoryAgent
from backend.video_generation.agents.validator_agent import ValidatorAgent
from backend.video_generation.agents.codegen_agent import CodeGenAgent
from backend.video_generation.agents.renderer_agent import RendererAgent
from backend.video_generation.agents.uploader_agent import UploaderAgent
from backend.ci.pipeline import CIPipelineHarness


# ── Node functions ─────────────────────────────────────────────────────────────

def _make_embed_node(agent: DocumentEmbedderAgent):
    def embed(state: VideoJob) -> VideoJob:
        return agent.run(state)
    return embed


def _make_story_node(agent: StoryAgent):
    def story(state: VideoJob) -> VideoJob:
        return agent.run(state)
    return story


def _make_validate_node(agent: ValidatorAgent):
    def validate(state: VideoJob) -> VideoJob:
        return agent.run(state)
    return validate


def _make_codegen_node(agent: CodeGenAgent):
    def codegen(state: VideoJob) -> VideoJob:
        return agent.run(state)
    return codegen


def _make_ci_node(harness: CIPipelineHarness):
    def ci(state: VideoJob) -> VideoJob:
        passed, error_trace = harness.validate_code(state.manim_code or "")
        if passed:
            state.has_build_error = False
            state.build_error_trace = None
        else:
            state.has_build_error = True
            state.build_error_trace = error_trace
            state.retry_count += 1
            print(f"[CI] Build failed (retry {state.retry_count}): {error_trace}")
            if state.retry_count >= 3:
                state.status = JobStatus.ERROR
                state.error_message = f"CODEGEN_MAX_RETRIES: Code generation failed after 3 attempts. Last error: {error_trace}"
        return state
    return ci


def _make_render_node(agent: RendererAgent):
    def render(state: VideoJob) -> VideoJob:
        return agent.run(state)
    return render


def _make_upload_node(agent: UploaderAgent):
    def upload(state: VideoJob) -> VideoJob:
        return agent.run(state)
    return upload


# ── Conditional edge functions ─────────────────────────────────────────────────

def _route_validate(state: VideoJob) -> str:
    if state.needs_revision:
        return "story"
    return "codegen"


def _route_ci(state: VideoJob) -> str:
    if state.has_build_error:
        if state.status == JobStatus.ERROR:
            return END  # max retries exceeded
        return "codegen"
    return "render"


# ── Graph builder ──────────────────────────────────────────────────────────────

def build_graph(rag_store: Optional[QdrantRAGStore] = None):
    """
    Build and compile the LangGraph StateGraph.
    Returns a CompiledGraph (if langgraph is available) or a FallbackPipeline.
    """
    rag = rag_store or QdrantRAGStore()
    embedder = DocumentEmbedderAgent(rag)
    story_agent = StoryAgent(rag)
    validator_agent = ValidatorAgent()
    codegen_agent = CodeGenAgent()
    ci_harness = CIPipelineHarness()
    renderer_agent = RendererAgent()
    uploader_agent = UploaderAgent()

    if not LANGGRAPH_AVAILABLE:
        print("[VideoGenerationPipeline] LangGraph not installed. Using FallbackPipeline.")
        return _FallbackPipeline(
            embedder, story_agent, validator_agent,
            codegen_agent, ci_harness, renderer_agent, uploader_agent,
        )

    graph = StateGraph(VideoJob)

    graph.add_node("embed", _make_embed_node(embedder))
    graph.add_node("story", _make_story_node(story_agent))
    graph.add_node("validate", _make_validate_node(validator_agent))
    graph.add_node("codegen", _make_codegen_node(codegen_agent))
    graph.add_node("ci", _make_ci_node(ci_harness))
    graph.add_node("render", _make_render_node(renderer_agent))
    graph.add_node("upload", _make_upload_node(uploader_agent))

    graph.set_entry_point("embed")
    graph.add_edge("embed", "story")
    graph.add_edge("story", "validate")
    graph.add_conditional_edges(
        "validate",
        _route_validate,
        {"story": "story", "codegen": "codegen"},
    )
    graph.add_edge("codegen", "ci")
    graph.add_conditional_edges(
        "ci",
        _route_ci,
        {"codegen": "codegen", "render": "render", END: END},
    )
    graph.add_edge("render", "upload")
    graph.set_finish_point("upload")

    return graph.compile()


# ── Fallback pipeline (when LangGraph is not installed) ────────────────────────

class _FallbackPipeline:
    """Runs the same agent sequence without LangGraph for local dev/testing."""

    def __init__(self, embedder, story_agent, validator_agent,
                 codegen_agent, ci_harness, renderer_agent, uploader_agent):
        self.embedder = embedder
        self.story_agent = story_agent
        self.validator_agent = validator_agent
        self.codegen_agent = codegen_agent
        self.ci_harness = ci_harness
        self.renderer_agent = renderer_agent
        self.uploader_agent = uploader_agent

    def invoke(self, state: VideoJob) -> VideoJob:
        state.status = JobStatus.PROCESSING

        state = self.embedder.run(state)
        if state.status == JobStatus.ERROR:
            return state

        # Story + Validation loop
        while True:
            state = self.story_agent.run(state)
            state = self.validator_agent.run(state)
            if not state.needs_revision:
                break

        # Codegen + CI loop (max 3 retries)
        while True:
            state = self.codegen_agent.run(state)
            if state.status == JobStatus.ERROR:
                return state
            passed, error_trace = self.ci_harness.validate_code(state.manim_code or "")
            if passed:
                state.has_build_error = False
                state.build_error_trace = None
                break
            else:
                state.has_build_error = True
                state.build_error_trace = error_trace
                state.retry_count += 1
                print(f"[FallbackPipeline CI] Code check failed (retry {state.retry_count}): {error_trace}")
                if state.retry_count >= 3:
                    state.status = JobStatus.ERROR
                    state.error_message = f"CODEGEN_MAX_RETRIES: Code generation failed after 3 attempts. Last error: {error_trace}"
                    return state

        state = self.renderer_agent.run(state)
        if state.status == JobStatus.ERROR:
            return state

        state = self.uploader_agent.run(state)
        return state


# ── VideoGenerationPipeline facade ─────────────────────────────────────────────

class VideoGenerationPipeline:
    """
    Public facade used by modal_app.py.
    Wraps the compiled LangGraph (or fallback) and provides run_pipeline().
    """

    def __init__(self, rag_store: Optional[QdrantRAGStore] = None):
        self._graph = build_graph(rag_store)

    def run_pipeline(self, job: VideoJob) -> VideoJob:
        if hasattr(self._graph, "invoke"):
            # LangGraph compiled graph
            result = self._graph.invoke(job)
            # LangGraph returns a dict or the state object
            if isinstance(result, dict):
                for k, v in result.items():
                    setattr(job, k, v)
            else:
                job = result
        else:
            # _FallbackPipeline
            job = self._graph.invoke(job)
        return job

    def run_annotation_patch(self, job: VideoJob) -> VideoJob:
        """
        Lightweight pipeline path for annotation: codegen → ci → render → upload.
        (DocumentEmbedder and StoryAgent are skipped; annotation_context is already set.)
        """
        rag = QdrantRAGStore()
        codegen_agent = CodeGenAgent()
        ci_harness = CIPipelineHarness()
        renderer_agent = RendererAgent()
        uploader_agent = UploaderAgent()

        job.version += 1

        for _ in range(3):
            job = codegen_agent.run(job)
            passed, error_trace = ci_harness.validate_code(job.manim_code or "")
            if passed:
                job.has_build_error = False
                break
            job.has_build_error = True
            job.build_error_trace = error_trace
            job.retry_count += 1

        if job.has_build_error:
            job.status = JobStatus.ERROR
            return job

        job = renderer_agent.run(job)
        job = uploader_agent.run(job)
        return job
