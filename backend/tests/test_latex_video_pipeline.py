"""
End-to-end integration tests for the LaTeX Video Pipeline.
Verifies complete workflow:
Structured LaTeX -> Parser -> Planner -> Tectonic Frame Renderer -> FFmpeg Video Assembler -> Playable MP4.
"""

import os
import pytest
from backend.video_generation.models import VideoJob, JobStatus
from backend.latex_video.pipeline import LatexVideoPipeline
from backend.video_generation.graph import VideoGenerationPipeline
import backend.config as config


@pytest.fixture
def latex_pipeline():
    return LatexVideoPipeline()


def test_end_to_end_small_lesson_mp4(latex_pipeline, tmp_path):
    """Verifies that a LaTeX lesson produces a valid, playable MP4 video."""
    sample_latex = r"""
\section*{Derivative of $x^2$}

\subsection*{The Basic Idea}
The derivative measures the instantaneous rate of change:
\[
f'(x) = 2x
\]

\subsection*{Conclusion}
\[
\boxed{\frac{d}{dx} x^2 = 2x}
\]
"""
    job = VideoJob(
        job_id="test_e2e_001",
        user_prompt=sample_latex,
        document_text=""
    )

    final_job = latex_pipeline.run_pipeline(job)

    assert final_job.status == JobStatus.DONE
    assert final_job.video_path is not None
    assert os.path.exists(final_job.video_path)
    assert os.path.getsize(final_job.video_path) > 1000
    assert final_job.progress_percentage == 100
    assert final_job.friendly_step == "Video Complete!"


def test_educational_topic_resolution(latex_pipeline):
    """Verifies that natural language prompts resolve into educational LaTeX and compile."""
    job = VideoJob(
        job_id="test_e2e_newton",
        user_prompt="Explain Newton's second law",
        document_text=""
    )

    final_job = latex_pipeline.run_pipeline(job)

    assert final_job.status == JobStatus.DONE
    assert os.path.exists(final_job.video_path)
    assert final_job.video_path.endswith(".mp4")


def test_video_renderer_configuration_routing():
    """Verifies that config.VIDEO_RENDERER properly selects the active backend."""
    from backend.latex_video.voice_pipeline import VoiceEnabledPipeline

    # 1. Default (latex) — now routes through VoiceEnabledPipeline (drop-in wrapper)
    config.VIDEO_RENDERER = "latex"
    pipeline_latex = VideoGenerationPipeline()
    assert pipeline_latex.active_backend == "latex"
    assert pipeline_latex._latex_pipeline is not None
    assert isinstance(pipeline_latex._latex_pipeline, VoiceEnabledPipeline)
    assert pipeline_latex._manim_pipeline is None

    # 2. Legacy fallback (manim)
    config.VIDEO_RENDERER = "manim"
    pipeline_manim = VideoGenerationPipeline()
    assert pipeline_manim.active_backend == "manim"
    assert pipeline_manim._manim_pipeline is not None
    assert pipeline_manim._latex_pipeline is None

    # Reset to default
    config.VIDEO_RENDERER = "latex"


def test_board_selection_whiteboard_e2e(latex_pipeline):
    """Verifies that a generic whiteboard lasso selection with math items compiles cleanly to MP4."""
    board_sel_dict = {
        "board_id": "test_board_123",
        "bbox": {"x": 10.0, "y": 20.0, "width": 400.0, "height": 300.0},
        "selected_items": [
            {"type": "TextItem", "text": "Solve the quadratic equation $ax^2 + bx + c = 0$"},
            {"type": "FormulaItem", "latex": "x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}"}
        ],
        "nearby_items": [],
        "user_instruction": "Explain the selected whiteboard region using the clearest, shortest visual lesson."
    }

    job = VideoJob(
        job_id="test_e2e_board_sel",
        user_prompt="Explain the selected whiteboard region.",
        document_text="",
        board_selection=board_sel_dict
    )

    final_job = latex_pipeline.run_pipeline(job)

    assert final_job.status == JobStatus.DONE
    assert final_job.video_path is not None
    assert os.path.exists(final_job.video_path)
    assert os.path.getsize(final_job.video_path) > 1000
    assert final_job.progress_percentage == 100


def test_refusal_detection_and_sanitization():
    """Verifies that refusal detection catches apology text and title sanitization prevents LaTeX errors."""
    refusal_1 = "I apologize, but the problem statement was not provided in the transcription."
    refusal_2 = "Cannot understand the context. Please provide an equation."
    valid_latex = r"\section*{Derivatives}\[ f'(x) = 2x \]"

    assert LatexVideoPipeline._is_refusal_or_unhelpful(refusal_1) is True
    assert LatexVideoPipeline._is_refusal_or_unhelpful(refusal_2) is True
    assert LatexVideoPipeline._is_refusal_or_unhelpful(valid_latex) is False

    # Sanitization
    unsafe_title = "Lesson on 100%_pure & $pecial #terms^"
    safe = LatexVideoPipeline._sanitize_latex_title(unsafe_title)
    assert r"\%" in safe
    assert r"\_" in safe
    assert r"\&" in safe
    assert r"\$" in safe
    assert r"\#" in safe

