import os
from backend.pipeline.models import VideoJob, JobStatus


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
            response = self._client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            return response.text
        elif self._sdk == "legacy":
            model = self._legacy.GenerativeModel("gemini-2.0-flash")
            return model.generate_content(prompt).text
        return ""

    def run(self, job: VideoJob) -> VideoJob:
        job.step = "codegen_agent"
        job.progress_percentage = 60

        error_context = (
            f"\nPrevious compilation error to fix:\n{job.build_error_trace}\n"
            if job.build_error_trace
            else ""
        )

        prompt = f"""You are an expert Python Manim developer.
Generate executable Python code using Manim (Community Edition v0.20.1) to render the following script into a scene named `MainScene`:

Script:
{job.story_script}
{error_context}

CRITICAL RULES:
1. Output ONLY executable Python code inside ```python ``` blocks.
2. Define a single class `MainScene(Scene):` with a `construct(self)` method.
3. Use smooth animations: Write, Create, FadeIn, Transform, ReplacementTransform.
4. Ensure all Mobjects stay within screen boundaries (config.frame_width x config.frame_height).
5. Use a dark theme with vibrant accent colors.
6. Do NOT import external packages beyond manim, math, numpy.
7. The code must be fully self-contained and run without any modification."""

        if self.api_key:
            try:
                code_text = self._generate(prompt)
                if "```python" in code_text:
                    code_text = code_text.split("```python")[1].split("```")[0].strip()
                elif "```" in code_text:
                    code_text = code_text.split("```")[1].split("```")[0].strip()
                job.manim_code = code_text
                return job
            except Exception as e:
                print(f"[CodeGenAgent] LLM error: {e}. Using fallback Manim template.")

        # Fallback Manim code
        title_safe = (job.user_prompt or "Topic")[:30].replace('"', "'")
        job.manim_code = f'''from manim import *

class MainScene(Scene):
    def construct(self):
        self.camera.background_color = "#0f0f23"

        title = Text("{title_safe}", font_size=42, color=BLUE)
        subtitle = Text("Generated with Manim AI", font_size=24, color=WHITE).next_to(title, DOWN)

        self.play(Write(title), run_time=1.5)
        self.play(FadeIn(subtitle), run_time=1.0)
        self.wait(1)

        formula = MathTex(r"E = mc^2", font_size=60, color=YELLOW)
        group = VGroup(title, subtitle)

        self.play(ReplacementTransform(group, formula))
        self.wait(2)

        box = SurroundingRectangle(formula, color=GREEN, buff=MED_SMALL_BUFF)
        self.play(Create(box))
        self.wait(2)'''.strip()
        return job
