import os
import json
from backend.pipeline.models import VideoJob
from backend.pipeline.scene_templates import SceneTemplateLibrary


class CodeGenAgent:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self._sdk = None
        self._template_lib = SceneTemplateLibrary()
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                self._sdk = "new"
            except ImportError:
                import google.generativeai as genai_legacy  # type: ignore
                genai_legacy.configure(api_key=self.api_key)
                self._legacy = genai_legacy
                self._sdk = "legacy"

    def _generate(self, prompt: str) -> str:
        if self._sdk == "new":
            # Try gemini-2.0-flash first; fall back to gemini-2.0-flash-lite / gemini-1.5-pro if rate-limited
            for model_name in ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro"]:
                try:
                    response = self._client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                    )
                    if response.text:
                        return response.text
                except Exception as e:
                    print(f"[CodeGenAgent] Model {model_name} error: {e}")
        elif self._sdk == "legacy":
            try:
                model = self._legacy.GenerativeModel("gemini-2.0-flash")
                return model.generate_content(prompt).text
            except Exception as e:
                print(f"[CodeGenAgent] Legacy LLM error: {e}")
        return ""

    def _fill_template_via_llm(self, job: VideoJob, template_name: str) -> str:
        """
        Asks the LLM to fill in the variable slots of a chosen template.
        Pre-fills $topic with job.user_prompt so the LLM can never override the title
        with generic content like 'Manim AI Visual Explanation'.
        """
        import re

        # Known template variable names — used to detect genuinely unfilled placeholders
        KNOWN_VARS = {
            "topic", "concept_label", "step1", "step2", "step3", "step4",
            "summary", "latex_formula", "transform_formula", "label_a", "label_b",
            "detail_a", "detail_b", "conclusion", "item1", "item2", "item3",
            "title", "subtitle", "description"
        }

        # Step 1: Pre-fill $topic with the actual user prompt BEFORE sending to LLM.
        # This is the most important fix — the LLM chose generic text here before.
        topic_safe = job.user_prompt.strip().replace('"', "'")[:50]
        raw_template = self._template_lib.get_template(template_name)
        # Replace $topic (and ${topic}) with the real title before LLM sees it
        raw_template = re.sub(r'\$\{?topic\}?', topic_safe, raw_template)

        print(f"[CodeGenAgent] Template strategy: '{template_name}' | topic='{topic_safe}'")

        prompt = f"""You are filling in a Manim animation template for a lesson about: "{job.user_prompt}"

Lesson context (from the student's uploaded document):
{(job.story_script or 'No script available — use your knowledge of the topic.')[:2000]}

Below is a partially filled Manim Python template. The title ($topic) is already set.
Your job is to fill in the REMAINING $variable placeholders with content specific to "{job.user_prompt}".

STRICT RULES:
- Text variables (concept_label, step1, step2, step3, summary etc.) → plain English, NO LaTeX, max 45 chars
- LaTeX variables (latex_formula, transform_formula) → valid LaTeX math ONLY, e.g. r"A\\mathbf{{v}} = \\lambda\\mathbf{{v}}"
- Make content SPECIFIC to "{job.user_prompt}" — not generic placeholder text
- Do NOT change any Python code structure — only replace $variable placeholders
- Return ONLY the complete Python code block, no explanation

TEMPLATE (fill remaining $variables):
```python
{raw_template}
```

Return only executable Python code."""

        raw_response = self._generate(prompt)
        if not raw_response:
            print(f"[CodeGenAgent] Template strategy: LLM returned empty response")
            return ""

        # Extract code block
        if "```python" in raw_response:
            code = raw_response.split("```python")[1].split("```")[0].strip()
        elif "```" in raw_response:
            code = raw_response.split("```")[1].split("```")[0].strip()
        else:
            code = raw_response.strip()

        # Only flag genuinely unfilled placeholders — check against known var names.
        # Avoids false positives from $ signs in LaTeX strings or Python comments.
        unfilled = [
            m for m in re.findall(r'\$\{?(\w+)\}?', code)
            if m in KNOWN_VARS
        ]
        if unfilled:
            print(f"[CodeGenAgent] Template fill incomplete — unfilled vars: {unfilled}")
            return ""

        print(f"[CodeGenAgent] Template strategy succeeded — {len(code)} chars generated")
        return code

    def run(self, job: VideoJob) -> VideoJob:
        job.step = "codegen_agent"
        job.progress_percentage = 60

        print(f"[CodeGenAgent] START | job={job.job_id} | prompt='{job.user_prompt[:60]}'")
        print(f"[CodeGenAgent] story_script length: {len(job.story_script or '')} chars")
        print(f"[CodeGenAgent] api_key present: {bool(self.api_key)} | sdk: {self._sdk}")

        error_context = ""
        build_err = getattr(job, "build_error_trace", None) or getattr(job, "ci_error_log", None)
        if build_err:
            error_context = f"\nPREVIOUS BUILD ERROR (Fix this in your code):\n{build_err}\n"
            print(f"[CodeGenAgent] Retry mode — build error: {build_err[:100]}")

        # ── Strategy 1: Template-based generation (low error rate) ────────────
        if self.api_key and not build_err:
            try:
                chosen_template = self._template_lib.select_template_for_topic(
                    job.user_prompt, job.story_script or ""
                )
                print(f"[CodeGenAgent] Selected template: '{chosen_template}'")
                template_code = self._fill_template_via_llm(job, chosen_template)
                if template_code and "class MainScene" in template_code:
                    print(f"[CodeGenAgent] ✅ Strategy 1 (template) succeeded")
                    job.manim_code = template_code
                    return job
                else:
                    print(f"[CodeGenAgent] Strategy 1 (template) produced no valid code, falling back")
            except Exception as e:
                print(f"[CodeGenAgent] Strategy 1 (template) exception: {e}. Falling back to free-gen.")

        # ── Strategy 2: Free-generation (fallback / retry path) ────────────
        print(f"[CodeGenAgent] Running Strategy 2 (Free-generation)")
        prompt = f"""You are an expert Manim CE (v0.20.1) Python code developer.
User Topic: "{job.user_prompt}"
Lesson Script:
{job.story_script}
{error_context}

CRITICAL INSTRUCTIONS:
Create a rich, 3Blue1Brown-style 2D animated lesson explaining "{job.user_prompt}".
DO NOT just print plain text strings. Create visual 2D diagrams!
- Use geometric shapes: Square, Circle, Rectangle, Arrow, VGroup, NumberPlane, Matrix.
- IMPORTANT TEXT RULE: Use Text() for ALL prose, labels, and descriptions.
  Only use MathTex() when displaying an actual mathematical formula or equation.
  Example: Text("The mitochondria is the powerhouse") NOT MathTex("The mitochondria...")
  Example: MathTex(r"E = mc^2") for actual equations ONLY.
  This prevents unnecessary LaTeX compilation which slows rendering significantly.
- Use dynamic animations: Create, Write, FadeIn, Transform, ReplacementTransform, Indicate, SurroundingRectangle.
- Ensure all objects fit within standard camera bounds (14x8 frame).

FORMATTING RULES:
1. Output ONLY executable Python code inside ```python ``` blocks.
2. Define a single class `MainScene(Scene):` with a `construct(self)` method.
3. Do NOT import external packages beyond manim, math, numpy.
4. Use valid Manim color constants (BLUE, TEAL, GREEN, YELLOW, RED, PURPLE, ORANGE, WHITE, GRAY) or hex strings (e.g. '#00ffff'). Do NOT use CYAN.
5. The code must be fully self-contained and run without error."""

        if self.api_key:
            try:
                code_text = self._generate(prompt)
                if "```python" in code_text:
                    code_text = code_text.split("```python")[1].split("```")[0].strip()
                elif "```" in code_text:
                    code_text = code_text.split("```")[1].split("```")[0].strip()
                if code_text and "class MainScene" in code_text:
                    job.manim_code = code_text
                    return job
            except Exception as e:
                print(f"[CodeGenAgent] LLM error: {e}. Using educational fallback Manim template.")

        # Educational fallback Manim code — renders real 2D matrix/grid diagrams & arrows
        title_clean = (job.user_prompt or "Neural Network Concept").strip().replace("\n", " ")[:35]
        sub_clean = (job.document_text or "Feature maps & matrix transformations").strip().replace("\n", " ")[:45]

        title_json = json.dumps(title_clean)
        sub_json = json.dumps(sub_clean)

        job.manim_code = f'''from manim import *

class MainScene(Scene):
    def construct(self):
        self.camera.background_color = "#090d16"

        # ── Stage 1: Lesson Title Banner ──
        title = Text({title_json}, font_size=36, color=BLUE).to_edge(UP, buff=0.5)
        subtitle = Text("Step-by-Step Visual Explanation", font_size=20, color=GRAY).next_to(title, DOWN, buff=0.2)
        
        self.play(Write(title), run_time=1.2)
        self.play(FadeIn(subtitle), run_time=0.8)
        self.wait(1)

        # ── Stage 2: Visual 2D Grid / Matrix Representation ──
        grid_group = VGroup()
        for row in range(3):
            for col in range(3):
                sq = Square(side_length=0.75, color=TEAL, fill_opacity=0.15)
                sq.move_to(np.array([col * 0.85 - 0.85, row * 0.85 - 0.85, 0]))
                grid_group.add(sq)

        grid_label = Text("Input Matrix (X)", font_size=18, color=TEAL).next_to(grid_group, DOWN, buff=0.3)
        input_section = VGroup(grid_group, grid_label).shift(LEFT * 3.5 + DOWN * 0.5)

        self.play(Create(grid_group), FadeIn(grid_label), run_time=1.5)
        self.wait(1)

        # ── Stage 3: Transformation Arrow & Formula ──
        arrow = Arrow(LEFT * 1.5, RIGHT * 0.5, color=YELLOW, buff=0.1).shift(DOWN * 0.5)
        formula = MathTex(r"Y = f(W \\cdot X + b)", font_size=32, color=YELLOW).next_to(arrow, UP, buff=0.2)

        self.play(GrowArrow(arrow), Write(formula), run_time=1.2)
        self.wait(1)

        # ── Stage 4: Feature Map Output Grid ──
        out_grid = VGroup()
        for row in range(2):
            for col in range(2):
                sq = Square(side_length=0.9, color=GREEN, fill_opacity=0.25)
                sq.move_to(np.array([col * 1.0 + 2.0, row * 1.0 - 0.5, 0]))
                out_grid.add(sq)

        out_label = Text("Feature Map Output", font_size=18, color=GREEN).next_to(out_grid, DOWN, buff=0.3)
        output_section = VGroup(out_grid, out_label)

        self.play(Create(out_grid), FadeIn(out_label), run_time=1.5)
        self.wait(1)

        # Highlight feature extraction pulse
        pulse = SurroundingRectangle(output_section, color=YELLOW, buff=0.2)
        self.play(Create(pulse), run_time=1.0)
        self.play(Uncreate(pulse), run_time=0.8)

        # ── Stage 5: Summary Card ──
        summary_card = RoundedRectangle(corner_radius=0.2, height=1.5, width=9.0, color=BLUE, fill_color="#131b2e", fill_opacity=0.9).to_edge(DOWN, buff=0.4)
        summary_text = Text({sub_json}, font_size=18, color=WHITE).move_to(summary_card.get_center())
        
        self.play(FadeIn(summary_card), Write(summary_text), run_time=1.5)
        self.wait(2)'''.strip()
        return job
