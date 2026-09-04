import os
import json
from backend.video_generation.models import VideoJob
from backend.video_generation.scene_templates import SceneTemplateLibrary


class CodeGenAgent:
    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.api_key = self.google_api_key or self.groq_api_key
        self._template_lib = SceneTemplateLibrary()

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            try:
                import google.generativeai as genai
                if self.google_api_key:
                    genai.configure(api_key=self.google_api_key)
                    self.gemini_model = genai.GenerativeModel('gemini-3.5-flash-lite')
                else:
                    self.gemini_model = None
            except ImportError:
                self.gemini_model = None

        if self.groq_api_key:
            try:
                from groq import Groq
                self._groq_client = Groq(api_key=self.groq_api_key)
            except ImportError:
                self._groq_client = None
        else:
            self._groq_client = None

    def _generate(self, prompt: str) -> str:
        if getattr(self, "gemini_model", None):
            try:
                response = self.gemini_model.generate_content(prompt)
                if response and response.text:
                    return response.text
            except Exception as e:
                print(f"[CodeGenAgent] Gemini LLM error: {e}. Falling back to Groq...")

        if getattr(self, "_groq_client", None):
            try:
                response = self._groq_client.chat.completions.create(
                    model="openai/gpt-oss-120b",  # Largest Groq model — best for code gen
                    messages=[{"role": "user", "content": prompt}],
                    timeout=60.0,
                )
                if response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content
            except Exception as e:
                print(f"[CodeGenAgent] Groq LLM error: {e}")
        return ""

    def _fill_template_via_llm(self, job: VideoJob, template_name: str) -> str:
        """
        Asks the LLM to fill in the variable slots of a chosen template.
        Pre-fills $topic with job.user_prompt so the LLM can never override the title
        with generic content like 'Manim AI Visual Explanation'.
        """
        import re

        # Known template variable names ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â used to detect genuinely unfilled placeholders
        KNOWN_VARS = {
            "topic", "concept_label", "step1", "step2", "step3", "step4",
            "summary", "latex_formula", "transform_formula", "label_a", "label_b",
            "detail_a", "detail_b", "conclusion", "item1", "item2", "item3",
            "title", "subtitle", "description"
        }

        # Step 1: Pre-fill $topic with the actual user prompt BEFORE sending to LLM.
        # This is the most important fix ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â the LLM chose generic text here before.
        topic_safe = job.user_prompt.strip().replace('"', "'")[:50]
        raw_template = self._template_lib.get_template(template_name)
        # Replace $topic (and ${topic}) with the real title before LLM sees it
        raw_template = re.sub(r'\$\{?topic\}?', topic_safe, raw_template)

        print(f"[CodeGenAgent] Template strategy: '{template_name}' | topic='{topic_safe}'")

        prompt = f"""You are filling in a Manim animation template for a lesson about: "{job.user_prompt}"

Lesson context (from the student's uploaded document):
{(job.story_script or 'No script available ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â use your knowledge of the topic.')[:2000]}

Below is a partially filled Manim Python template. The title ($topic) is already set.
Your job is to fill in the REMAINING $variable placeholders with content specific to "{job.user_prompt}".

STRICT RULES:
- Text variables (concept_label, step1, step2, step3, summary etc.) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ plain English, max 45 chars
- LaTeX variables (latex_formula, transform_formula) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ plain string math ONLY using Text(), e.g. "Av = \\lambda v". Do NOT use MathTex.
- Make content SPECIFIC to "{job.user_prompt}" ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â not generic placeholder text
- Do NOT change any Python code structure ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â only replace $variable placeholders
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

        # Only flag genuinely unfilled placeholders ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â check against known var names.
        # Avoids false positives from $ signs in LaTeX strings or Python comments.
        unfilled = [
            m for m in re.findall(r'\$\{?(\w+)\}?', code)
            if m in KNOWN_VARS
        ]
        if unfilled:
            print(f"[CodeGenAgent] Template fill incomplete ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â unfilled vars: {unfilled}")
            return ""

        print(f"[CodeGenAgent] Template strategy succeeded ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â {len(code)} chars generated")
        return code

    def run(self, job: VideoJob) -> VideoJob:
        job.step = "codegen_agent"
        job.progress_percentage = 60

        print(f"[CodeGenAgent] START | job={job.job_id} | prompt='{job.user_prompt[:60]}'")
        print(f"[CodeGenAgent] story_script length: {len(job.story_script or '')} chars")
        print(f"[CodeGenAgent] api_key present: {bool(self.api_key)} | Gemini: {bool(self.google_api_key)} | Groq: {bool(self.groq_api_key)}")

        error_context = ""
        build_err = getattr(job, "build_error_trace", None) or getattr(job, "ci_error_log", None)
        if build_err:
            error_context = f"\nPREVIOUS BUILD ERROR (Fix this in your code):\n{build_err}\n"
            print(f"[CodeGenAgent] Retry mode ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â build error: {build_err[:100]}")

        # ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ Strategy 1: Template-based generation (low error rate) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬
        # DISABLED: Templates are too short for detailed user prompts. We now rely on
        # the full LLM generation (Strategy 2) for all requests to ensure detailed videos.
        if False: # self.api_key and not build_err:
            try:
                chosen_template = self._template_lib.select_template_for_topic(
                    job.user_prompt, job.story_script or ""
                )
                print(f"[CodeGenAgent] Selected template: '{chosen_template}'")
                template_code = self._fill_template_via_llm(job, chosen_template)
                if template_code and "class MainScene" in template_code:
                    print(f"[CodeGenAgent] Strategy 1 (template) succeeded")
                    # Inject LaTeX monkeypatch
                    patch = "\nclass MathTex(Text):\n    def __init__(self, *args, **kwargs):\n        super().__init__(' '.join(args), **{k:v for k,v in kwargs.items() if k in ['color', 'font_size']})\nclass Tex(MathTex): pass\n"
                    template_code = template_code.replace("class MainScene", f"{patch}\nclass MainScene")
                    job.manim_code = template_code
                    return job
                else:
                    print(f"[CodeGenAgent] Strategy 1 (template) produced no valid code, falling back")
            except Exception as e:
                print(f"[CodeGenAgent] Strategy 1 (template) exception: {e}. Falling back to free-gen.")

        # ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ Strategy 2: Free-generation (fallback / retry path) ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬
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
- DO NOT USE MathTex() or Tex() AT ALL. LaTeX is NOT installed on this system.
- Use Text() or MarkupText() for ALL prose, labels, descriptions, and math formulas!
  Example: Text("E = mc^2") NOT MathTex("E = mc^2")
- Layout: DO NOT try to manually position many text objects with .shift(). Instead, group them in a VGroup and use .arrange(DOWN, buff=0.5) so they do not overlap.
- Text Size: Keep font_size around 24 to 36 so it fits on screen. Break long sentences into multiple lines using \\n.
- Pacing: Add self.wait(2) or self.wait(3) between major animations so the viewer has time to read.
- Clean Transitions: When moving to a completely new concept, use self.play(*[FadeOut(m) for m in self.mobjects]) to clear the screen!

FORMATTING RULES:
1. Output ONLY executable Python code inside ```python ``` blocks.
2. Define a single class `MainScene(Scene):` with a `construct(self)` method.
3. Do NOT import external packages beyond manim, math, numpy.
4. Use valid Manim color constants (BLUE, TEAL, GREEN, YELLOW, RED, PURPLE, ORANGE, WHITE, GRAY).
5. The code must be fully self-contained and run without error.
6. CRITICAL: DO NOT use `while` loops, infinite loops, `time.sleep()`, or any network calls.
7. CRITICAL: Use only standard Manim animations. Do not try to open UI windows."""

        if self.api_key:
            try:
                code_text = self._generate(prompt)
                if "```python" in code_text:
                    code_text = code_text.split("```python")[1].split("```")[0].strip()
                elif "```" in code_text:
                    code_text = code_text.split("```")[1].split("```")[0].strip()
                if code_text:
                    # Robustly inject LaTeX monkeypatch after imports
                    patch = "\nclass MathTex(Text):\n    def __init__(self, *args, **kwargs):\n        super().__init__(' '.join(args), **{k:v for k,v in kwargs.items() if k in ['color', 'font_size']})\nclass Tex(MathTex): pass\n"
                    import re
                    # Find the last import statement
                    imports = list(re.finditer(r"^(?:from\s+\S+\s+import\s+.*|import\s+.*)$", code_text, re.MULTILINE))
                    if imports:
                        last_import = imports[-1]
                        insert_idx = last_import.end()
                        code_text = code_text[:insert_idx] + "\n" + patch + code_text[insert_idx:]
                    else:
                        code_text = patch + code_text
                    
                    job.manim_code = code_text
                    return job
            except Exception as e:
                print(f"[CodeGenAgent] LLM error: {e}. Using educational fallback Manim template.")

        # Educational fallback Manim code ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â renders real 2D matrix/grid diagrams & arrows
        title_clean = (job.user_prompt or "Neural Network Concept").strip().replace("\n", " ")[:35]
        sub_clean = (job.document_text or "Feature maps & matrix transformations").strip().replace("\n", " ")[:45]

        title_json = json.dumps(title_clean)
        sub_json = json.dumps(sub_clean)

        job.manim_code = f'''from manim import *

class MainScene(Scene):
    def construct(self):
        self.camera.background_color = "#090d16"

        # ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ Stage 1: Lesson Title Banner ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬
        title = Text({title_json}, font_size=36, color=BLUE).to_edge(UP, buff=0.5)
        subtitle = Text("Step-by-Step Visual Explanation", font_size=20, color=GRAY).next_to(title, DOWN, buff=0.2)
        
        self.play(Write(title), run_time=1.2)
        self.play(FadeIn(subtitle), run_time=0.8)
        self.wait(1)

        # ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ Stage 2: Visual 2D Grid / Matrix Representation ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬
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

        # ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ Stage 3: Transformation Arrow & Formula ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬
        arrow = Arrow(LEFT * 1.5, RIGHT * 0.5, color=YELLOW, buff=0.1).shift(DOWN * 0.5)
        formula = Text("Y = f(W * X + b)", font_size=32, color=YELLOW).next_to(arrow, UP, buff=0.2)

        self.play(GrowArrow(arrow), Write(formula), run_time=1.2)
        self.wait(1)

        # ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ Stage 4: Feature Map Output Grid ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬
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

        # ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ Stage 5: Summary Card ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬
        summary_card = RoundedRectangle(corner_radius=0.2, height=1.5, width=9.0, color=BLUE, fill_color="#131b2e", fill_opacity=0.9).to_edge(DOWN, buff=0.4)
        summary_text = Text({sub_json}, font_size=18, color=WHITE).move_to(summary_card.get_center())
        
        self.play(FadeIn(summary_card), Write(summary_text), run_time=1.5)
        self.wait(2)'''.strip()
        return job
