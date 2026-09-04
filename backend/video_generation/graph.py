"""
LangGraph StateGraph pipeline for the Manim AI Video Generator.

Two compatible paths are supported:

Legacy text/PDF:
    embed -> story -> validate -> codegen -> ci -> render -> upload

Whiteboard-aware:
    embed -> board_understanding -> teaching_planner -> storyboard_planner
          -> scene_compile -> ci -> render -> upload

If deterministic SceneSpec compilation fails CI, the graph falls back to the
legacy CodeGenAgent as a repair path instead of discarding the whole job.
"""

from __future__ import annotations

from typing import Optional

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
from backend.video_generation.agents.notes_agent import NotesGeneratorAgent
from backend.video_generation.agents.board_understanding_agent import BoardUnderstandingAgent
from backend.video_generation.agents.teaching_planner_agent import TeachingPlannerAgent
from backend.video_generation.agents.storyboard_agent import StoryboardPlannerAgent
from backend.video_generation.agents.scene_compile_agent import SceneCompileAgent
from backend.ci.pipeline import CIPipelineHarness


def _node(agent):
    def run(state: VideoJob) -> VideoJob:
        return agent.run(state)
    return run


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
                state.error_message = (
                    "CODEGEN_MAX_RETRIES: Code generation failed after 3 attempts. "
                    f"Last error: {error_trace}"
                )
        return state
    return ci


def _route_post_embed(state: VideoJob) -> str:
    if getattr(state, "output_type", "video") == "notes":
        return "notes_generator"
    selection = getattr(state, "board_selection", None)
    if selection and getattr(selection, "has_content", lambda: True)():
        return "board_understanding"
    return "story"


def _route_validate(state: VideoJob) -> str:
    return "story" if state.needs_revision else "codegen"


def _route_ci(state: VideoJob) -> str:
    if not state.has_build_error:
        return "render"
    if state.status == JobStatus.ERROR:
        return END

    selection = getattr(state, "board_selection", None)
    if selection and getattr(selection, "has_content", lambda: False)():
        state.status = JobStatus.ERROR
        state.error_message = (
            "STRUCTURED_SCENE_CI_FAILED: "
            + (state.build_error_trace or "Deterministic SceneSpec compilation failed.")
        )
        return END

    # Legacy text/PDF requests keep their bounded CodeGen repair path.
    return "codegen"


def build_graph(rag_store: Optional[QdrantRAGStore] = None):
    rag = rag_store or QdrantRAGStore()
    embedder = DocumentEmbedderAgent(rag)
    story_agent = StoryAgent(rag)
    validator_agent = ValidatorAgent()
    codegen_agent = CodeGenAgent()
    ci_harness = CIPipelineHarness()
    renderer_agent = RendererAgent()
    uploader_agent = UploaderAgent()
    notes_agent = NotesGeneratorAgent()
    board_agent = BoardUnderstandingAgent()
    teaching_agent = TeachingPlannerAgent(rag)
    storyboard_agent = StoryboardPlannerAgent()
    scene_compile_agent = SceneCompileAgent()

    if not LANGGRAPH_AVAILABLE:
        print("[VideoGenerationPipeline] LangGraph not installed. Using FallbackPipeline.")
        return _FallbackPipeline(
            embedder=embedder,
            story_agent=story_agent,
            validator_agent=validator_agent,
            codegen_agent=codegen_agent,
            ci_harness=ci_harness,
            renderer_agent=renderer_agent,
            uploader_agent=uploader_agent,
            notes_agent=notes_agent,
            board_agent=board_agent,
            teaching_agent=teaching_agent,
            storyboard_agent=storyboard_agent,
            scene_compile_agent=scene_compile_agent,
        )

    graph = StateGraph(VideoJob)
    graph.add_node("embed", _node(embedder))
    graph.add_node("story", _node(story_agent))
    graph.add_node("validate", _node(validator_agent))
    graph.add_node("codegen", _node(codegen_agent))
    graph.add_node("ci", _make_ci_node(ci_harness))
    graph.add_node("render", _node(renderer_agent))
    graph.add_node("upload", _node(uploader_agent))
    graph.add_node("notes_generator", _node(notes_agent))

    graph.add_node("board_understanding", _node(board_agent))
    graph.add_node("teaching_planner", _node(teaching_agent))
    graph.add_node("storyboard_planner", _node(storyboard_agent))
    graph.add_node("scene_compile", _node(scene_compile_agent))

    graph.set_entry_point("embed")
    graph.add_conditional_edges(
        "embed",
        _route_post_embed,
        {
            "notes_generator": "notes_generator",
            "board_understanding": "board_understanding",
            "story": "story",
        },
    )

    # Legacy path
    graph.add_edge("story", "validate")
    graph.add_conditional_edges(
        "validate",
        _route_validate,
        {"story": "story", "codegen": "codegen"},
    )
    graph.add_edge("codegen", "ci")

    # Whiteboard path
    graph.add_edge("board_understanding", "teaching_planner")
    graph.add_edge("teaching_planner", "storyboard_planner")
    graph.add_edge("storyboard_planner", "scene_compile")
    graph.add_edge("scene_compile", "ci")

    graph.add_conditional_edges(
        "ci",
        _route_ci,
        {"codegen": "codegen", "render": "render", END: END},
    )
    graph.add_edge("render", "upload")
    graph.set_finish_point("upload")
    graph.add_edge("notes_generator", END)
    return graph.compile()


class _FallbackPipeline:
    def __init__(
        self,
        embedder,
        story_agent,
        validator_agent,
        codegen_agent,
        ci_harness,
        renderer_agent,
        uploader_agent,
        notes_agent,
        board_agent,
        teaching_agent,
        storyboard_agent,
        scene_compile_agent,
    ):
        self.embedder = embedder
        self.story_agent = story_agent
        self.validator_agent = validator_agent
        self.codegen_agent = codegen_agent
        self.ci_harness = ci_harness
        self.renderer_agent = renderer_agent
        self.uploader_agent = uploader_agent
        self.notes_agent = notes_agent
        self.board_agent = board_agent
        self.teaching_agent = teaching_agent
        self.storyboard_agent = storyboard_agent
        self.scene_compile_agent = scene_compile_agent

    def invoke(self, state: VideoJob) -> VideoJob:
        state.status = JobStatus.PROCESSING
        state = self.embedder.run(state)
        if state.status == JobStatus.ERROR:
            return state

        if getattr(state, "output_type", "video") == "notes":
            state = self.notes_agent.run(state)
            if state.status != JobStatus.ERROR:
                state.status = JobStatus.DONE
            return state

        selection = getattr(state, "board_selection", None)
        if selection and getattr(selection, "has_content", lambda: True)():
            state = self.board_agent.run(state)
            state = self.teaching_agent.run(state)
            state = self.storyboard_agent.run(state)
            state = self.scene_compile_agent.run(state)
            state = self._validate_or_repair(state)
        else:
            while True:
                state = self.story_agent.run(state)
                state = self.validator_agent.run(state)
                if not state.needs_revision:
                    break
            state = self._codegen_until_valid(state)

        if state.status == JobStatus.ERROR:
            return state
        state = self.renderer_agent.run(state)
        if state.status == JobStatus.ERROR:
            return state
        return self.uploader_agent.run(state)

    def _validate_or_repair(self, state: VideoJob) -> VideoJob:
        passed, error_trace = self.ci_harness.validate_code(state.manim_code or "")
        if passed:
            state.has_build_error = False
            state.build_error_trace = None
            return state
        state.has_build_error = True
        state.build_error_trace = error_trace
        state.retry_count += 1

        selection = getattr(state, "board_selection", None)
        if selection and getattr(selection, "has_content", lambda: False)():
            state.status = JobStatus.ERROR
            state.error_message = (
                "STRUCTURED_SCENE_CI_FAILED: "
                + (error_trace or "Deterministic SceneSpec compilation failed.")
            )
            return state

        return self._codegen_until_valid(state)

    def _codegen_until_valid(self, state: VideoJob) -> VideoJob:
        while state.retry_count < 3:
            state = self.codegen_agent.run(state)
            if state.status == JobStatus.ERROR:
                return state
            passed, error_trace = self.ci_harness.validate_code(state.manim_code or "")
            if passed:
                state.has_build_error = False
                state.build_error_trace = None
                return state
            state.has_build_error = True
            state.build_error_trace = error_trace
            state.retry_count += 1
            print(f"[FallbackPipeline CI] Code check failed (retry {state.retry_count}): {error_trace}")
        state.status = JobStatus.ERROR
        state.error_message = (
            "CODEGEN_MAX_RETRIES: Code generation failed after 3 attempts. "
            f"Last error: {state.build_error_trace}"
        )
        return state


class VideoGenerationPipeline:
    """Public facade used by local_server.py and modal_app.py."""

    def __init__(self, rag_store: Optional[QdrantRAGStore] = None):
        self._graph = build_graph(rag_store)

    def run_pipeline(self, job: VideoJob) -> VideoJob:
        if hasattr(self._graph, "invoke"):
            result = self._graph.invoke(job)
            if isinstance(result, dict):
                for key, value in result.items():
                    setattr(job, key, value)
            else:
                job = result
        else:
            job = self._graph.invoke(job)
        return job

    def run_annotation_patch(self, job: VideoJob) -> VideoJob:
        """Legacy lightweight annotation repair path."""
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
        return uploader_agent.run(job)
