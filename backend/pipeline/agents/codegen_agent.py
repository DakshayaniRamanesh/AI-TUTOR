import os
import json
from backend.pipeline.models import VideoJob


class CodeGenAgent:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self._sdk = None
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
            # Try gemini-2.0-flash first; fall back to gemini-1.5-flash if 429 rate-limited
            for model_name in ["gemini-2.0-flash", "gemini-1.5-flash"]:
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
            model = self._legacy.GenerativeModel("gemini-1.5-flash")
            return model.generate_content(prompt).text
        return ""

    def run(self, job: VideoJob) -> VideoJob:
        job.step = "codegen_agent"
        job.progress_percentage = 60

        error_context = ""
        if job.ci_error_log:
            error_context = f"\nPREVIOUS BUILD ERROR (Fix this in your code):\n{job.ci_error_log}\n"

        prompt = f"""You are an expert Manim CE (v0.20.1) Python code developer.
User Topic: "{job.user_prompt}"
Lesson Script:
{job.story_script}
{error_context}

CRITICAL INSTRUCTIONS:
Create a rich, 3Blue1Brown-style 2D animated lesson explaining "{job.user_prompt}".
DO NOT just print plain text strings. Create visual 2D diagrams!
- Use geometric shapes: Square, Circle, Rectangle, Arrow, VGroup, NumberPlane, Matrix.
- Use MathTex for mathematical formulas (e.g. MathTex(r"Y = f(W \\cdot X + b)")).
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
