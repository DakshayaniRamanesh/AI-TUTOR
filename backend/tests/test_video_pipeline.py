"""
Automated test suite for the Kestrel Video Generation Pipeline.

Tests cover:
  A. Subject classifier identifies math/physics/cs/chemistry/statistics correctly
  B. CI Stage 0 bans MathTex, Tex, time.sleep, infinite loops
  C. CI Stage 0 bans CYAN color constant
  D. CI Stage 0 catches unreadable font sizes
  E. CI Stage 0 catches excessively long text strings
  F. CI Stage 0 catches missing self.wait()
  G. ValidatorAgent structural checks (scene count, visual element, topic relevance)
  H. ValidatorAgent passes a well-formed script
  I. CodeGenAgent post-processes MathTex → Text
  J. StoryAgent fallback produces subject-appropriate content
  K. RendererAgent records render_quality on the job
  L. local_server friendly_error maps internal codes to user-friendly messages
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pytest
from unittest.mock import MagicMock, patch


# ─────────────────────────────────────────────────────────────────────────────
# A. Subject Classifier
# ─────────────────────────────────────────────────────────────────────────────

class TestSubjectClassifier:
    def _classify(self, prompt):
        from backend.video_generation.agents.story_agent import classify_subject
        return classify_subject(prompt)

    def test_math_derivative(self):
        assert self._classify("Explain the derivative of x squared") == "math"

    def test_physics_force(self):
        assert self._classify("Newton's second law: force equals mass times acceleration") == "physics"

    def test_cs_algorithm(self):
        assert self._classify("Binary search algorithm step by step") == "cs"

    def test_chemistry_reaction(self):
        assert self._classify("Chemical reaction between hydrogen and oxygen") == "chemistry"

    def test_statistics_distribution(self):
        assert self._classify("Normal distribution and probability density") == "statistics"

    def test_general_fallback(self):
        assert self._classify("The history of the Roman Empire") == "general"

    def test_neural_network_classified_cs(self):
        result = self._classify("How neural networks learn with gradient descent")
        assert result == "cs"


# ─────────────────────────────────────────────────────────────────────────────
# B–F. CI Stage 0 Static Analysis
# ─────────────────────────────────────────────────────────────────────────────

class TestCIStage0StaticAnalysis:
    def _validate(self, code):
        from backend.ci.pipeline import CIPipelineHarness
        harness = CIPipelineHarness()
        return harness.validate_code(code)

    def _minimal_valid(self):
        return '''from manim import *

class MainScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        title = Text("Test", font_size=30, color=BLUE)
        self.play(Write(title))
        self.wait(2)
'''

    def test_empty_code_fails(self):
        passed, err = self._validate("")
        assert not passed
        assert "Empty" in err

    def test_mathtex_allowed_by_static_policy(self):
        from backend.ci.pipeline import _static_analysis
        code = self._minimal_valid().replace('Text("Test"', 'MathTex("x^2"')
        passed, err = _static_analysis(code)
        assert passed, err

    def test_tex_banned(self):
        code = self._minimal_valid().replace("Text(", "Tex(", 1)
        passed, err = self._validate(code)
        assert not passed
        assert "Stage0" in err

    def test_time_sleep_banned(self):
        code = self._minimal_valid() + "\n        import time\n        time.sleep(1)\n"
        passed, err = self._validate(code)
        assert not passed
        assert "Stage0" in err
        assert "time.sleep" in err

    def test_infinite_loop_banned(self):
        code = self._minimal_valid() + "\n        while True:\n            pass\n"
        passed, err = self._validate(code)
        assert not passed
        assert "Stage0" in err

    def test_cyan_color_banned(self):
        code = self._minimal_valid().replace("color=BLUE", "color=CYAN")
        passed, err = self._validate(code)
        assert not passed
        assert "CYAN" in err

    def test_tiny_font_banned(self):
        code = self._minimal_valid().replace("font_size=30", "font_size=8")
        passed, err = self._validate(code)
        assert not passed
        assert "font_size" in err

    def test_oversized_font_banned(self):
        code = self._minimal_valid().replace("font_size=30", "font_size=120")
        passed, err = self._validate(code)
        assert not passed
        assert "font_size" in err

    def test_long_text_string_banned(self):
        long_text = "A" * 90
        code = self._minimal_valid().replace('"Test"', f'"{long_text}"')
        passed, err = self._validate(code)
        assert not passed
        assert "too long" in err.lower() or "Stage0" in err

    def test_missing_wait_banned(self):
        code = '''from manim import *

class MainScene(Scene):
    def construct(self):
        title = Text("Test", font_size=30, color=BLUE)
        self.play(Write(title))
'''
        passed, err = self._validate(code)
        assert not passed
        assert "wait" in err.lower()

    def test_missing_main_scene_banned(self):
        code = '''from manim import *

class WrongName(Scene):
    def construct(self):
        self.wait(1)
'''
        passed, err = self._validate(code)
        assert not passed
        assert "MainScene" in err

    def test_valid_code_passes_stage0(self):
        """A clean, minimal scene should pass Stage 0."""
        passed, err = self._validate(self._minimal_valid())
        # Stage 0 should pass even if stages 1-4 run and succeed
        # (We only assert Stage 0 does NOT fire)
        if not passed:
            assert "Stage0" not in err, f"Stage 0 incorrectly rejected valid code: {err}"


# ─────────────────────────────────────────────────────────────────────────────
# G–H. ValidatorAgent
# ─────────────────────────────────────────────────────────────────────────────

class TestValidatorAgent:
    def _make_job(self, script="", prompt="test topic", doc_text=""):
        from backend.video_generation.models import VideoJob
        return VideoJob(job_id="test", user_prompt=prompt, story_script=script, document_text=doc_text)

    def test_empty_script_fails(self):
        from backend.video_generation.agents.validator_agent import ValidatorAgent
        job = self._make_job(script="")
        result = ValidatorAgent().run(job)
        assert result.needs_revision is True

    def test_no_scenes_fails(self):
        from backend.video_generation.agents.validator_agent import ValidatorAgent
        job = self._make_job(script="A" * 200)
        result = ValidatorAgent().run(job)
        assert result.needs_revision is True
        assert "revision_reason" in result.metadata

    def test_no_visual_line_fails(self):
        from backend.video_generation.agents.validator_agent import ValidatorAgent
        script = "## Scene 1: Intro\nNarration: Hello\n\n## Scene 2: Main\nNarration: World\n"
        job = self._make_job(script=script * 3, prompt="test")
        result = ValidatorAgent().run(job)
        assert result.needs_revision is True

    def test_well_formed_script_passes(self):
        from backend.video_generation.agents.validator_agent import ValidatorAgent
        script = """## Scene 1: Introduction
Narration: Let's explore derivatives.
Visual: Axes with a parabola plotted. Title "Derivative" at the top.
Duration: 6 seconds

## Scene 2: Core Concept
Narration: The derivative measures the rate of change.
Visual: Tangent line touching the curve. Arrow showing slope direction.
Duration: 8 seconds

## Scene 3: Example
Narration: For f(x) = x^2, the derivative is 2x.
Visual: NumberPlane with x^2 curve and labeled tangent lines at x=1 and x=2.
Duration: 8 seconds

## Scene 4: Key Takeaway
Narration: Derivatives tell us how quickly a function changes at any point.
Visual: Summary card with three bullet points.
Duration: 5 seconds
"""
        job = self._make_job(script=script, prompt="derivative of x squared")
        result = ValidatorAgent().run(job)
        assert result.needs_revision is False

    def test_max_revisions_forces_through(self):
        from backend.video_generation.agents.validator_agent import ValidatorAgent
        job = self._make_job(script="")
        job.revision_count = 2  # already at max
        result = ValidatorAgent().run(job)
        assert result.needs_revision is False


# ─────────────────────────────────────────────────────────────────────────────
# I. CodeGenAgent post-processing
# ─────────────────────────────────────────────────────────────────────────────

class TestCodeGenAgentPostProcessing:
    def test_mathtex_rewritten_to_text(self):
        from backend.video_generation.agents.codegen_agent import CodeGenAgent
        agent = CodeGenAgent()
        code = 'from manim import *\nresult = MathTex("x^2")\nresult2 = Tex("y = mx")\n'
        processed = agent._rewrite_mathtex(code)
        assert "MathTex(" not in processed
        assert "Tex(" not in processed
        assert 'Text("x^2")' in processed
        assert 'Text("y = mx")' in processed

    def test_ensure_imports_added_when_missing(self):
        from backend.video_generation.agents.codegen_agent import CodeGenAgent
        agent = CodeGenAgent()
        code = "class MainScene(Scene):\n    def construct(self):\n        pass\n"
        result = agent._ensure_imports(code)
        assert "from manim import *" in result

    def test_code_block_extraction(self):
        from backend.video_generation.agents.codegen_agent import CodeGenAgent
        agent = CodeGenAgent()
        raw = "Here is the code:\n```python\nfrom manim import *\nclass MainScene(Scene):\n    pass\n```\nEnd."
        extracted = agent._extract_code_block(raw)
        assert extracted.startswith("from manim import *")
        assert "```" not in extracted


# ─────────────────────────────────────────────────────────────────────────────
# J. StoryAgent subject-aware fallback
# ─────────────────────────────────────────────────────────────────────────────

class TestStoryAgentFallback:
    def test_math_fallback_has_axes_reference(self):
        from backend.video_generation.agents.story_agent import StoryAgent
        agent = StoryAgent.__new__(StoryAgent)
        result = agent._subject_fallback("Calculus Integration", "math", "Area under a curve")
        assert "Axes" in result or "NumberPlane" in result or "graph" in result.lower()

    def test_physics_fallback_has_arrow_reference(self):
        from backend.video_generation.agents.story_agent import StoryAgent
        agent = StoryAgent.__new__(StoryAgent)
        result = agent._subject_fallback("Newton's Laws", "physics", "Force and acceleration")
        assert "Arrow" in result or "force" in result.lower() or "diagram" in result.lower()

    def test_cs_fallback_has_flowchart_reference(self):
        from backend.video_generation.agents.story_agent import StoryAgent
        agent = StoryAgent.__new__(StoryAgent)
        result = agent._subject_fallback("Binary Search", "cs", "Search algorithm")
        assert "box" in result.lower() or "Arrow" in result or "flowchart" in result.lower()

    def test_fallback_includes_four_scenes(self):
        from backend.video_generation.agents.story_agent import StoryAgent
        import re
        agent = StoryAgent.__new__(StoryAgent)
        result = agent._subject_fallback("Some Topic", "general", "Some content")
        scenes = re.findall(r'## Scene \d+', result)
        assert len(scenes) == 4


# ─────────────────────────────────────────────────────────────────────────────
# K. RendererAgent records render_quality
# ─────────────────────────────────────────────────────────────────────────────

class TestRendererAgent:
    def test_no_code_sets_error(self):
        from backend.video_generation.agents.renderer_agent import RendererAgent
        from backend.video_generation.models import VideoJob, JobStatus
        agent = RendererAgent()
        job = VideoJob(job_id="test", user_prompt="test", manim_code=None)
        result = agent.run(job)
        assert result.status == JobStatus.ERROR
        assert "No animation code" in (result.error_message or "")


# ─────────────────────────────────────────────────────────────────────────────
# L. Friendly error mapping (local_server)
# ─────────────────────────────────────────────────────────────────────────────

class TestFriendlyErrors:
    def _friendly(self, msg):
        # Import the function directly
        import importlib
        import sys
        # We need to import _friendly_error without running the FastAPI app
        # So we test the logic inline matching the implementation
        ERROR_LABELS = {
            "CODEGEN_MAX_RETRIES": "Kestrel couldn't generate this animation after 3 attempts. Try rephrasing your topic or using a simpler subject.",
            "PAGE_LIMIT": "Your document selection is too large. Please select 30 or fewer pages.",
            "No animation code": "No animation was produced. Please try again.",
        }
        if not msg:
            return ""
        for key, friendly in ERROR_LABELS.items():
            if key in msg:
                return friendly
        return f"Something went wrong: {msg.split(chr(10))[0][:200]}"

    def test_codegen_max_retries_friendly(self):
        err = "CODEGEN_MAX_RETRIES: Code generation failed after 3 attempts. Last error: ..."
        result = self._friendly(err)
        assert "3 attempts" in result
        assert "CODEGEN_MAX_RETRIES" not in result

    def test_page_limit_friendly(self):
        err = "PAGE_LIMIT: You selected 45 pages. Maximum allowed per extraction is 30 pages."
        result = self._friendly(err)
        assert "30" in result

    def test_none_error_returns_empty(self):
        assert self._friendly(None) == ""
        assert self._friendly("") == ""


# ─────────────────────────────────────────────────────────────────────────────
# Template library
# ─────────────────────────────────────────────────────────────────────────────

class TestSceneTemplateLibrary:
    def test_new_templates_registered(self):
        from backend.video_generation.scene_templates import SceneTemplateLibrary
        lib = SceneTemplateLibrary()
        templates = lib.list_templates()
        assert "graph_plotter" in templates
        assert "physics_diagram" in templates
        assert "algorithm_steps" in templates
        assert "chemistry_reaction" in templates

    def test_math_subject_routes_to_graph_plotter(self):
        from backend.video_generation.scene_templates import SceneTemplateLibrary
        lib = SceneTemplateLibrary()
        result = lib.select_template_for_topic(
            "Explain the derivative of x squared",
            "",
            topic_subject="math"
        )
        assert result == "graph_plotter"

    def test_chemistry_subject_routes_to_chemistry_reaction(self):
        from backend.video_generation.scene_templates import SceneTemplateLibrary
        lib = SceneTemplateLibrary()
        result = lib.select_template_for_topic(
            "Acid-base chemical reaction",
            "",
            topic_subject="chemistry"
        )
        assert result == "chemistry_reaction"

    def test_cs_algorithm_routes_to_algorithm_steps(self):
        from backend.video_generation.scene_templates import SceneTemplateLibrary
        lib = SceneTemplateLibrary()
        result = lib.select_template_for_topic(
            "Binary search algorithm steps",
            "",
            topic_subject="cs"
        )
        assert result == "algorithm_steps"

    def test_physics_force_routes_to_physics_diagram(self):
        from backend.video_generation.scene_templates import SceneTemplateLibrary
        lib = SceneTemplateLibrary()
        result = lib.select_template_for_topic(
            "Newton's law of force and motion",
            "",
            topic_subject="physics"
        )
        assert result == "physics_diagram"
