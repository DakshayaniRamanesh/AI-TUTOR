"""
CodeGenAgent — Reliable Manim code generator with two-strategy approach.

Improvements over v1:
  - Strategy 1 (template-based) is RE-ENABLED as the primary path
  - Template selection uses topic_subject hint from StoryAgent for subject-aware routing
  - Enhanced free-generation prompt with explicit layout constraints and banned API list
  - Post-generation preprocessing: MathTex/Tex → Text() rewrite, code extraction
  - Retry path includes specific directive to use a different approach (not repeat mistake)
  - Records model_used on the job for traceability
  - Migrated to suppress FutureWarning
"""

import os
import re
import json
import warnings
from backend.video_generation.models import VideoJob, JobStatus
from backend.video_generation.scene_templates import SceneTemplateLibrary


# Known template variable names — used to detect genuinely unfilled placeholders
_KNOWN_VARS = {
    "topic", "concept_label", "step1", "step2", "step3", "step4",
    "summary", "latex_formula", "transform_formula", "label_a", "label_b",
    "detail_a", "detail_b", "conclusion", "item1", "item2", "item3",
    "title", "subtitle", "description", "x_range", "y_range", "x_label",
    "y_label", "func_expr", "func_label", "key_x", "key_y", "key_annotation",
    "object_label", "force1_label", "force2_label", "principle",
    "element_a", "element_b", "product", "reaction_equation", "explanation",
    "result", "stage1", "stage2", "stage3", "stage4",
    "left_label", "right_label", "left_p1", "left_p2", "left_p3",
    "right_p1", "right_p2", "right_p3",
    "input_label", "output_label", "grid_rows", "grid_cols", "out_rows", "out_cols",
    "var1_sym", "var1_desc", "var2_sym", "var2_desc", "var3_sym", "var3_desc", "key_insight",
}

_MANIM_SAFE_COLORS = (
    "BLUE TEAL GREEN YELLOW RED PURPLE ORANGE WHITE GRAY GREY "
    "DARK_BLUE DARK_GREEN DARK_BROWN DARK_GRAY LIGHT_GRAY "
    "BLUE_A BLUE_B BLUE_C BLUE_D BLUE_E "
    "GREEN_A GREEN_B GREEN_C GREEN_D GREEN_E "
    "TEAL_A TEAL_B TEAL_C TEAL_D TEAL_E "
    "GOLD GOLD_A GOLD_B GOLD_C GOLD_D "
    "RED_A RED_B RED_C RED_D RED_E MAROON "
    "PINK LIGHT_PINK PURE_RED PURE_GREEN PURE_BLUE BLACK"
)

_BANNED_PATTERNS = [
    ("MathTex(", "Replace MathTex(...) with Text(...)"),
    ("Tex(", "Replace Tex(...) with Text(...)"),
    ("time.sleep(", "Remove time.sleep() — it blocks the renderer"),
    ("while True", "Remove infinite loops"),
    ("input(", "Remove input() calls"),
    ("import requests", "No network calls"),
    ("import urllib", "No network calls"),
    ("open(", "No file I/O — use only manim/numpy/math"),
]

# Free-generation prompt — used on retry and when no matching template exists
_FREE_GEN_PROMPT = """You are an expert Manim CE (v0.20.1) Python code developer.

TOPIC: "{topic}"
SUBJECT AREA: {subject}
LESSON SCRIPT:
{script}
{error_context}
TASK: Create a complete, self-contained Manim animation for the topic above.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULES (FAILURE TO FOLLOW = UNUSABLE CODE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. CLASS:   Define exactly ONE class `MainScene(Scene)` with `construct(self)`.
2. IMPORTS: Only `from manim import *`, `import numpy as np`, `import math`. Nothing else.
3. NO LaTeX: DO NOT use MathTex() or Tex() — LaTeX is NOT installed.
            Use Text() or MarkupText() for ALL text, labels, and math.
            Math example: Text("f(x) = x^2")  NOT MathTex("f(x) = x^2")
4. COLORS:  Only use safe constants: BLUE, TEAL, GREEN, YELLOW, RED, PURPLE,
            ORANGE, WHITE, GRAY, DARK_BLUE, GOLD, PINK, BLACK.
            NEVER use CYAN (crashes on some systems).
5. LAYOUT:
   - Safe zone: x in [-6, 6], y in [-3.5, 3.5]. Keep all objects inside this zone.
   - Use .arrange(DOWN, buff=0.5) on VGroup instead of manual .shift() for multiple items.
   - To edge: use .to_edge(UP, buff=0.4) or .to_edge(DOWN, buff=0.4).
   - Never stack multiple text items at the same position.
6. TEXT:
   - Max 45 characters per line. Break long text with \\n.
   - font_size: 20 to 40 for body, 36 to 48 for titles. NEVER below 18.
   - Break equations into parts: Text("E = mc") + Text("c^2") if needed.
7. TIMING:
   - Add self.wait(1.5) to self.wait(3) between major scenes.
   - Minimum scene duration: 4 seconds total content.
   - Never animate faster than run_time=0.5.
8. CLEANUP: Use self.play(*[FadeOut(m) for m in self.mobjects]) when transitioning 
            to a completely new concept.
9. BANNED:  NO while loops, NO time.sleep(), NO input(), NO network calls.
10. VISUAL: Do NOT just show text. Create at least ONE geometric visual 
            (shapes, arrows, axes, grids, charts) appropriate for {subject}.

SUBJECT-SPECIFIC GUIDANCE for {subject}:
{visual_hint}

EXAMPLE OF GOOD STRUCTURE:
```python
from manim import *

class MainScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        
        # Scene 1: Title
        title = Text("Topic Title", font_size=40, color=BLUE, weight=BOLD)
        title.to_edge(UP, buff=0.4)
        self.play(Write(title), run_time=1.0)
        self.wait(1)
        
        # Scene 2: Visual
        ax = Axes(x_range=[-3, 3, 1], y_range=[-1, 5, 1], tips=False)
        curve = ax.plot(lambda x: x**2, color=TEAL)
        self.play(Create(ax), Create(curve), run_time=1.5)
        self.wait(2)
        
        label = Text("y = x squared", font_size=24, color=TEAL)
        label.to_edge(DOWN, buff=0.5)
        self.play(FadeIn(label))
        self.wait(2)
```

Output ONLY executable Python code inside ```python ``` blocks. No explanation."""

# Subject-specific visual hints for the free-gen prompt
_SUBJECT_VISUAL_HINTS = {
    "math": "Use Axes/NumberPlane for graphs. Plot curves with ax.plot(lambda x: ...). "
            "Show derivation steps with Text() objects that appear one at a time with FadeIn().",
    "physics": "Use Arrow() for force/velocity vectors with labels. "
               "Use Rectangle() for objects. Show before/after states.",
    "cs": "Use RoundedRectangle+Arrow for flowcharts. Use VGroup of boxes for algorithms. "
          "Show data transformation step by step.",
    "chemistry": "Use Circle+Text for elements. Use Line for bonds. Use Arrow for reactions. "
                 "Show reactants → product with reaction_arrow.",
    "biology": "Use RoundedRectangle boxes with Arrow connections for process flows. "
               "Show cyclical processes with curved arrows.",
    "statistics": "Use Axes with ax.plot() for distributions. Use BarChart for bar charts. "
                  "Annotate key values with Dot and Text labels.",
    "general": "Use RoundedRectangle boxes for concepts. Use Arrow for relationships. "
               "Use progressive FadeIn for text reveals. Keep it clean and uncluttered.",
}


class CodeGenAgent:
    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.api_key = self.google_api_key or self.groq_api_key
        self._template_lib = SceneTemplateLibrary()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            try:
                import google.generativeai as genai
                if self.google_api_key:
                    genai.configure(api_key=self.google_api_key)
                    for model_name in ["gemini-3.5-flash", "gemini-1.5-flash"]:
                        try:
                            self.gemini_model = genai.GenerativeModel(model_name)
                            self._gemini_model_name = model_name
                            break
                        except Exception:
                            self.gemini_model = None
                            self._gemini_model_name = ""
                else:
                    self.gemini_model = None
                    self._gemini_model_name = ""
            except ImportError:
                self.gemini_model = None
                self._gemini_model_name = ""

        self._groq_client = None
        if self.groq_api_key:
            try:
                from groq import Groq
                self._groq_client = Groq(api_key=self.groq_api_key)
            except ImportError:
                pass

    def _generate(self, prompt: str) -> tuple[str, str]:
        """Returns (generated_text, model_name_used)."""
        if self.gemini_model:
            try:
                response = self.gemini_model.generate_content(prompt)
                if response and response.text:
                    return response.text, self._gemini_model_name
            except Exception as e:
                print(f"[CodeGenAgent] Gemini error: {e}. Falling back to Groq...")

        if self._groq_client:
            try:
                response = self._groq_client.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=4096,
                )
                if response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content, "groq/openai/gpt-oss-120b"
            except Exception as e:
                print(f"[CodeGenAgent] Groq error: {e}")
        return "", ""

    # ── Post-generation code cleanup ─────────────────────────────────────────

    def _extract_code_block(self, raw: str) -> str:
        """Extract Python code from markdown fences."""
        if "```python" in raw:
            code = raw.split("```python")[1].split("```")[0].strip()
        elif "```" in raw:
            code = raw.split("```")[1].split("```")[0].strip()
        else:
            code = raw.strip()
        return code

    def _rewrite_mathtex(self, code: str) -> str:
        """Replace MathTex(...) and Tex(...) with Text(...) in generated code.
        
        This is an explicit rewrite (not a monkeypatch) so the CI can catch it
        early and the visual output uses proper Text rendering.
        """
        # Match MathTex("...", ...) or MathTex('...', ...) — replace class name only
        code = re.sub(r'\bMathTex\s*\(', 'Text(', code)
        code = re.sub(r'\bTex\s*\(', 'Text(', code)
        return code

    def _ensure_imports(self, code: str) -> str:
        """Make sure from manim import * is present."""
        if "from manim import" not in code and "import manim" not in code:
            code = "from manim import *\n" + code
        return code

    def _post_process(self, code: str) -> str:
        """Apply all post-generation cleanup passes."""
        code = self._extract_code_block(code) if "```" in code else code.strip()
        code = self._rewrite_mathtex(code)
        code = self._ensure_imports(code)
        return code

    # ── Strategy 1: Template-based generation ────────────────────────────────

    def _fill_template_via_llm(self, job: VideoJob, template_name: str) -> str:
        """Ask the LLM to fill template $variable slots with topic-specific content."""
        topic_safe = job.user_prompt.strip().replace('"', "'")[:50]
        raw_template = self._template_lib.get_template(template_name)
        # Pre-fill $topic before the LLM sees it
        raw_template = re.sub(r'\$\{?topic\}?', topic_safe, raw_template)

        print(f"[CodeGenAgent] Template strategy: '{template_name}' | topic='{topic_safe}'")

        prompt = f"""Fill in ALL $variable placeholders in this Manim template for: "{job.user_prompt}"

Subject area: {job.topic_subject or 'general'}

Lesson script context:
{(job.story_script or 'Use your knowledge of the topic.')[:2000]}

RULES:
- Text variables (labels, steps, summary etc.) → plain English, max 40 chars, no LaTeX
- Math variables (formulas, equations) → plain ASCII math e.g. "f(x) = x^2", NO LaTeX syntax
- Numeric variables (ranges, positions, values) → valid Python numbers/lists e.g. [-3, 3, 1]
- Lambda expressions (func_expr) → valid Python lambda body e.g. x**2
- Content MUST be SPECIFIC to "{job.user_prompt}" — not generic
- Do NOT change Python code structure — only fill $variable placeholders
- Return ONLY the complete Python code block

TEMPLATE:
```python
{raw_template}
```

Return only executable Python code."""

        raw_response, model_name = self._generate(prompt)
        if not raw_response:
            return ""

        code = self._post_process(raw_response)

        # Check for genuinely unfilled placeholders
        unfilled = [m for m in re.findall(r'\$\{?(\w+)\}?', code) if m in _KNOWN_VARS]
        if unfilled:
            print(f"[CodeGenAgent] Template fill incomplete — unfilled vars: {unfilled}")
            return ""

        if "class MainScene" not in code:
            print(f"[CodeGenAgent] Template fill: MainScene class not found in output")
            return ""

        if model_name and not job.model_used:
            job.model_used = model_name

        print(f"[CodeGenAgent] Strategy 1 (template '{template_name}') succeeded — {len(code)} chars")
        return code

    # ── Strategy 2: Free generation ──────────────────────────────────────────

    def _free_generate(self, job: VideoJob, error_context: str = "") -> str:
        """Generate Manim code from scratch using the enhanced prompt."""
        subject = job.topic_subject or "general"
        visual_hint = _SUBJECT_VISUAL_HINTS.get(subject, _SUBJECT_VISUAL_HINTS["general"])

        # On retry: add strong directive to use a DIFFERENT approach
        retry_directive = ""
        if error_context:
            retry_directive = (
                "\n⚠️  IMPORTANT: Your previous attempt failed with the error shown above. "
                "Do NOT repeat the same approach. Use a simpler, different strategy:\n"
                "- If you used complex animations, simplify them\n"
                "- If you used Axes/graph, try simple shapes instead\n"
                "- If you used many objects, reduce to 3-4 total\n"
                "- Ensure every object fits within x:[-6,6] y:[-3.5,3.5]\n"
            )

        prompt = _FREE_GEN_PROMPT.format(
            topic=job.user_prompt[:80],
            subject=subject,
            script=(job.story_script or "No script — generate from your knowledge.")[:2000],
            error_context=f"\nPREVIOUS ERROR (fix this — DO NOT REPEAT):\n{error_context}\n{retry_directive}" if error_context else "",
            visual_hint=visual_hint,
        )

        raw_response, model_name = self._generate(prompt)
        if not raw_response:
            return ""

        code = self._post_process(raw_response)
        if model_name and not job.model_used:
            job.model_used = model_name

        print(f"[CodeGenAgent] Strategy 2 (free-gen) produced {len(code)} chars")
        return code

    # ── Main run ──────────────────────────────────────────────────────────────

    def run(self, job: VideoJob) -> VideoJob:
        job.step = "codegen_agent"
        job.friendly_step = "Generating animation..."
        job.progress_percentage = 60

        print(f"[CodeGenAgent] START | job={job.job_id} | prompt='{job.user_prompt[:60]}'")
        print(f"[CodeGenAgent] story_script length: {len(job.story_script or '')} chars | subject: {job.topic_subject}")
        print(f"[CodeGenAgent] API: Gemini={bool(self.google_api_key)} | Groq={bool(self.groq_api_key)} | retry={job.retry_count}")

        error_context = ""
        build_err = getattr(job, "build_error_trace", None) or getattr(job, "ci_error_log", None)
        if build_err:
            error_context = build_err
            print(f"[CodeGenAgent] Retry mode — CI error: {build_err[:120]}")

        generated_code = ""

        # ── Strategy 1: Template (primary path, no retry) ─────────────────────
        if self.api_key and not error_context:
            try:
                chosen_template = self._template_lib.select_template_for_topic(
                    job.user_prompt, job.story_script or "", job.topic_subject or ""
                )
                print(f"[CodeGenAgent] Selected template: '{chosen_template}'")
                generated_code = self._fill_template_via_llm(job, chosen_template)
                if generated_code:
                    print(f"[CodeGenAgent] Strategy 1 succeeded")
                else:
                    print(f"[CodeGenAgent] Strategy 1 failed — falling to Strategy 2")
            except Exception as e:
                print(f"[CodeGenAgent] Strategy 1 exception: {e}. Falling to Strategy 2.")

        # ── Strategy 2: Free generation (retry path or template failure) ───────
        if not generated_code:
            print(f"[CodeGenAgent] Running Strategy 2 (free-generation)")
            if self.api_key:
                try:
                    generated_code = self._free_generate(job, error_context)
                except Exception as e:
                    print(f"[CodeGenAgent] Strategy 2 exception: {e}. Using hardcoded fallback.")

        # ── Hardcoded fallback (no API key or all LLMs failed) ────────────────
        if not generated_code:
            generated_code = self._hardcoded_fallback(job)
            job.model_used = "hardcoded_fallback"
            print(f"[CodeGenAgent] Using hardcoded fallback")

        job.manim_code = generated_code
        return job

    def _hardcoded_fallback(self, job: VideoJob) -> str:
        """A reliable, visually decent fallback that always renders successfully."""
        title_clean = (job.user_prompt or "Educational Concept").strip().replace("\n", " ")[:40]
        title_json = json.dumps(title_clean)
        subject = job.topic_subject or "general"

        return f'''from manim import *

class MainScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"

        # ── Title ──
        title = Text({title_json}, font_size=38, color=BLUE, weight=BOLD)
        title.to_edge(UP, buff=0.4)
        subtitle = Text("Visual Explanation", font_size=20, color=GRAY)
        subtitle.next_to(title, DOWN, buff=0.25)
        self.play(Write(title), run_time=1.0)
        self.play(FadeIn(subtitle), run_time=0.6)
        self.wait(1)
        self.play(FadeOut(subtitle))

        # ── Concept Box ──
        box = RoundedRectangle(corner_radius=0.3, height=2.2, width=8.5,
                               color=TEAL, fill_color="#0d2b35", fill_opacity=0.8)
        box.shift(UP * 0.5)
        label = Text("Core concept", font_size=24, color=TEAL)
        label.move_to(box.get_center())
        self.play(Create(box), Write(label), run_time=1.2)
        self.wait(1)

        # ── Key Points ──
        points = VGroup()
        point_texts = ["Understand the fundamentals", "Apply the core principle", "Verify the result"]
        for i, pt in enumerate(point_texts):
            dot = Dot(color=YELLOW)
            txt = Text(pt, font_size=20, color=WHITE)
            txt.next_to(dot, RIGHT, buff=0.25)
            row = VGroup(dot, txt)
            points.add(row)
        points.arrange(DOWN, buff=0.45, aligned_edge=LEFT)
        points.shift(DOWN * 1.2)
        for row in points:
            self.play(FadeIn(row), run_time=0.5)
        self.wait(1.5)

        # ── Summary ──
        self.play(*[FadeOut(m) for m in self.mobjects])
        card = RoundedRectangle(corner_radius=0.2, height=2.0, width=10.0,
                                color=BLUE, fill_color="#131b2e", fill_opacity=0.9)
        summary = Text("Subject: " + {title_json!r}, font_size=20, color=WHITE)
        summary.move_to(card.get_center())
        self.play(FadeIn(card), Write(summary), run_time=1.2)
        self.wait(2)
'''.replace("{title_json!r}", title_json)
