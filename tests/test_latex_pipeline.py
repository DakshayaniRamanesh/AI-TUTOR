import os
import sys
import base64
import pytest
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"), override=True)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.video_generation.models import LatexJob, JobStatus
from backend.video_generation.agents.latex_agents import (
    LatexStructureAgent,
    TemplateApplyAgent,
    TectonicCompileAgent
)
from backend.math_engine.latex_graph import LatexGenerationPipeline


def test_latex_structure_solve_math():
    """Verify that LatexStructureAgent structures and solves math problems with step-by-step LaTeX."""
    job = LatexJob(
        job_id="test_solve_001",
        raw_transcription=r"Solve for x: 2x^2 - 8x + 6 = 0",
        template_type="Homework",
        mode="study",
        classroom_action="Solve Question"
    )
    
    agent = LatexStructureAgent()
    updated_job = agent.run(job)
    
    assert updated_job.status != JobStatus.ERROR
    assert updated_job.structured_latex is not None
    assert len(updated_job.structured_latex) > 20
    print("\n[Structured LaTeX Output]:\n", updated_job.structured_latex)


def test_template_apply():
    """Verify that TemplateApplyAgent merges structured math into the document template."""
    job = LatexJob(
        job_id="test_template_001",
        structured_latex=r"\section*{Solution}\begin{align*} 2x^2 - 8x + 6 &= 0 \\ x^2 - 4x + 3 &= 0 \\ (x-1)(x-3) &= 0 \end{align*}\boxed{x = 1 \text{ or } x = 3}",
        template_type="Homework"
    )
    
    agent = TemplateApplyAgent()
    updated_job = agent.run(job)
    
    assert updated_job.status == JobStatus.DONE
    assert r"\documentclass" in updated_job.final_tex_code
    assert r"\begin{document}" in updated_job.final_tex_code
    assert r"\boxed" in updated_job.final_tex_code
