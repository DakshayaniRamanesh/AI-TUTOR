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
7. Use valid Manim color constants (BLUE, TEAL, GREEN, YELLOW, RED, PURPLE, ORANGE, WHITE, GRAY) or hex strings (e.g. '#00ffff'). Do NOT use CYAN.
8. The code must be fully self-contained and run without any modification."""

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

        # Dynamic fallback Manim code based on user prompt and document text
        import json
        title_clean = (job.user_prompt or "Document Concept").strip().replace("\n", " ")[:35]
        sub_clean = (job.document_text or "Visual Analysis").strip().replace("\n", " ")[:40]

        title_json = json.dumps(title_clean)
        sub_json = json.dumps(sub_clean)

        job.manim_code = f'''from manim import *

class MainScene(Scene):
    def construct(self):
        self.camera.background_color = "#090d16"

        title = Text({title_json}, font_size=38, color=BLUE)
        subtitle = Text("Concept Breakdown", font_size=24, color=GRAY).next_to(title, DOWN)

        self.play(Write(title), run_time=1.5)
        self.play(FadeIn(subtitle), run_time=1.0)
        self.wait(1)

        detail_box = RoundedRectangle(corner_radius=0.2, height=2.2, width=7.0, color=TEAL)
        detail_text = Text({sub_json}, font_size=20, color=WHITE).move_to(detail_box.get_center())
        group = VGroup(title, subtitle)
        box_group = VGroup(detail_box, detail_text)

        self.play(ReplacementTransform(group, box_group))
        self.wait(2)

        highlight = SurroundingRectangle(box_group, color=YELLOW, buff=MED_SMALL_BUFF)
        self.play(Create(highlight))
        self.wait(2)'''.strip()
        return job
