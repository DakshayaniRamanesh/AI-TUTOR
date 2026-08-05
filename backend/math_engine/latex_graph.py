"""
LangGraph pipeline for the Handwriting to Clean LaTeX feature.
"""

from __future__ import annotations
from typing import Optional

try:
    from langgraph.graph import StateGraph, END  # type: ignore
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

from backend.video_generation.models import LatexJob, JobStatus
from backend.video_generation.agents.latex_agents import (
    LatexTranscribeAgent,
    LatexStructureAgent,
    TemplateApplyAgent,
    TectonicCompileAgent,
)


def _make_transcribe_node(agent: LatexTranscribeAgent):
    def transcribe(state: LatexJob) -> LatexJob:
        return agent.run(state)
    return transcribe


def _make_structure_node(agent: LatexStructureAgent):
    def structure(state: LatexJob) -> LatexJob:
        return agent.run(state)
    return structure


def _make_template_apply_node(agent: TemplateApplyAgent):
    def template_apply(state: LatexJob) -> LatexJob:
        return agent.run(state)
    return template_apply


def _make_compile_check_node(agent: TectonicCompileAgent):
    def compile_check(state: LatexJob) -> LatexJob:
        return agent.run(state)
    return compile_check


def _route_compile_check(state: LatexJob) -> str:
    if state.status == JobStatus.ERROR:
        return END
    
    if state.has_build_error:
        print(f"[{state.job_id}] Build error detected, routing back to structure (retry {state.retry_count})")
        return "structure"
    
    return END

def _route_general(state: LatexJob, next_node: str) -> str:
    return END if state.status == JobStatus.ERROR else next_node


def build_latex_graph():
    """
    Build and compile the LangGraph StateGraph for LaTeX conversion.
    Returns a CompiledGraph (if langgraph is available) or a FallbackPipeline.
    """
    transcribe_agent = LatexTranscribeAgent()
    structure_agent = LatexStructureAgent()
    template_agent = TemplateApplyAgent()
    compile_agent = TectonicCompileAgent()

    if not LANGGRAPH_AVAILABLE:
        print("[LatexPipeline] LangGraph not installed. Using FallbackPipeline.")
        return _FallbackLatexPipeline(
            transcribe_agent, structure_agent, template_agent, compile_agent
        )

    graph = StateGraph(LatexJob)

    graph.add_node("transcribe", _make_transcribe_node(transcribe_agent))
    graph.add_node("structure", _make_structure_node(structure_agent))
    graph.add_node("template_apply", _make_template_apply_node(template_agent))
    graph.add_node("compile_check", _make_compile_check_node(compile_agent))

    graph.set_entry_point("transcribe")
    
    graph.add_conditional_edges("transcribe", lambda state: _route_general(state, "structure"), {"structure": "structure", END: END})
    graph.add_conditional_edges("structure", lambda state: _route_general(state, "template_apply"), {"template_apply": "template_apply", END: END})
    graph.add_conditional_edges("template_apply", lambda state: _route_general(state, "compile_check"), {"compile_check": "compile_check", END: END})
    
    graph.add_conditional_edges(
        "compile_check",
        _route_compile_check,
        {"structure": "structure", END: END},
    )

    return graph.compile()


class _FallbackLatexPipeline:
    """Runs the same agent sequence without LangGraph for local dev/testing."""

    def __init__(self, transcribe, structure, template, compile_node):
        self.transcribe = transcribe
        self.structure = structure
        self.template = template
        self.compile_node = compile_node

    def invoke(self, state: LatexJob) -> LatexJob:
        state.status = JobStatus.PROCESSING

        state = self.transcribe.run(state)
        if state.status == JobStatus.ERROR:
            return state

        while True:
            state = self.structure.run(state)
            if state.status == JobStatus.ERROR:
                return state

            state = self.template.run(state)
            if state.status == JobStatus.ERROR:
                return state

            state = self.compile_node.run(state)
            if state.status == JobStatus.ERROR:
                return state

            if state.has_build_error:
                if state.retry_count >= 2:
                    state.status = JobStatus.ERROR
                    state.error_message = f"Compilation failed after max retries. Last error: {state.build_error_trace}"
                    return state
                print(f"[{state.job_id}] Build error detected, routing back to structure (retry {state.retry_count})")
                continue
            
            # Success
            break

        return state


class LatexGenerationPipeline:
    """
    Public facade used by local_server.py / modal_app.py.
    Wraps the compiled LangGraph (or fallback) and provides run_pipeline().
    """

    def __init__(self):
        self._graph = build_latex_graph()

    def run_pipeline(self, job: LatexJob) -> LatexJob:
        if hasattr(self._graph, "invoke"):
            result = self._graph.invoke(job)
            if isinstance(result, dict):
                for k, v in result.items():
                    setattr(job, k, v)
            else:
                job = result
        else:
            job = self._graph.invoke(job)
        return job
