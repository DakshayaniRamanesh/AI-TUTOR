import os
import io
import re
import base64
import subprocess
import tempfile
from typing import Optional
from backend.video_generation.models import LatexJob, JobStatus

# Try to import groq
try:
    from groq import Groq
except ImportError:
    Groq = None

STRUCTURE_PROMPT_TEMPLATE = """You are an expert STEM mathematician and LaTeX typesetter. I will provide transcribed math and text fragments extracted via OCR from handwritten notes, along with the requested document template type.

Your task is to structure this into a clean, semantically correct, high-quality LaTeX document body.

CRITICAL RULES:
1. **Math Environments & Equation Alignment**: 
   - Use `$ ... $` for short inline math embedded within text sentences.
   - Use `\\begin{{equation}} ... \\end{{equation}}` for standalone single-line formulas (centered automatically).
   - Use `\\begin{{align*}} ... \\end{{align*}}` ONLY for multi-line algebraic derivations aligned at the `=` sign using `&=`.
   - **ALIGNMENT RULES (STRICT)**:
     * NEVER put explanatory sentences or labels inside `\\begin{{align*}}` before `&` (e.g. NEVER write `\\text{{Given:}} &`). Explanatory text MUST be regular text paragraphs outside the equation block!
     * In `align*`, each line must be pure math, e.g.:
       `x^2 - 2x + 1 &= 0 \\\\`
       `(x - 1)^2 &= 0 \\\\`
       `x &= 1`
     * NEVER put `&` inside variable names (e.g. NEVER `x& = 1`).
     * NEVER write `\\&` inside math equations. The symbol `&` is strictly an alignment separator in `align*`.
2. **Mathematical Problem Solving**:
   - If the content contains a problem, equation to solve, integral, derivative, proof, or question, PROVIDE A COMPLETE STEP-BY-STEP MATHEMATICAL SOLUTION.
   - Show all necessary algebraic/calculus intermediate steps.
   - Always enclose the final answer inside `\\boxed{{...}}`.
3. **Template-Specific Formatting**:
   - **Lecture Slides (Beamer)**: Wrap logical slides in `\\begin{{frame}}{{Slide Title}} ... \\end{{frame}}`.
   - **Standard Documents**: Use `\\section*{{}}` and `\\subsection*{{}}` for clear organization. Use `\\begin{{itemize}}` or `\\begin{{enumerate}}` for lists.
4. **Output Constraints**: 
   - Do NOT output `\\documentclass`, `\\usepackage`, or `\\begin{{document}}`. 
   - Output ONLY the internal body content (the raw LaTeX). 
   - This output will be directly injected into a `{{{{CONTENT_BODY}}}}` slot in a pre-existing template.
   - Do NOT wrap your output in markdown code blocks like ```latex ... ```. Output raw text.
5. **NO MARKDOWN**: NEVER use `#` or `##` for headers. NEVER use `**` for bold (use `\\textbf{{...}}`). This must be pure LaTeX code.

Template Type: {template_type}

Raw transcription:
{raw_text}
"""


class LatexTranscribeAgent:
    """Uses Google Gemini Vision to extract raw LaTeX and math from the handwritten image."""
    
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")

    def run(self, job: LatexJob) -> LatexJob:
        job.step = "Transcribing Handwriting"
        job.progress_percentage = 10
        print(f"[{job.job_id}] Transcribing handwriting with Gemini Vision...")

        if not self.api_key:
            job.status = JobStatus.ERROR
            job.error_message = "GOOGLE_API_KEY missing from environment."
            return job

        try:
            import google.generativeai as genai
            from PIL import Image
            genai.configure(api_key=self.api_key)

            # Clean base64 string
            b64_str = job.image_b64 or ""
            if "," in b64_str:
                b64_str = b64_str.split(",", 1)[1]
            b64_str = b64_str.strip()

            if not b64_str:
                job.status = JobStatus.ERROR
                job.error_message = "No image data provided for LaTeX transcription."
                return job

            image_bytes = base64.b64decode(b64_str)
            image = Image.open(io.BytesIO(image_bytes))

            prompt = (
                "Transcribe all handwritten math equations, symbols, problems, diagrams, and text from this image into clean, precise LaTeX. "
                "Preserve all mathematical variables, formulas, subscripts, superscripts, and problem statements accurately. "
                "Output ONLY the transcribed LaTeX and text without markdown wrapping or chat preamble."
            )

            response_text = ""
            models = ["gemini-2.5-flash", "gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-2.5-pro"]
            for m in models:
                try:
                    model = genai.GenerativeModel(m)
                    resp = model.generate_content([prompt, image])
                    if resp and resp.text:
                        response_text = resp.text.strip()
                        break
                except Exception as ex:
                    print(f"[{job.job_id}] Gemini {m} transcribe notice: {ex}")
                    continue

            if not response_text:
                raise RuntimeError("All Gemini vision models failed to transcribe the image.")

            job.raw_transcription = response_text
        except Exception as e:
            job.status = JobStatus.ERROR
            job.error_message = f"Transcription failed: {str(e)}"

        return job



class LatexStructureAgent:
    """Uses Groq or Gemini text LLM to structure, format, and solve math problems into clean LaTeX."""

    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.google_api_key = os.getenv("GOOGLE_API_KEY")

    def run(self, job: LatexJob) -> LatexJob:
        job.step = "Structuring & Solving Math"
        job.progress_percentage = 35
        print(f"[{job.job_id}] Structuring document & solving math...")

        prompt = STRUCTURE_PROMPT_TEMPLATE.format(
            template_type=job.template_type,
            raw_text=job.raw_transcription or ""
        )

        mode = getattr(job, "mode", "study")
        action = getattr(job, "classroom_action", "Solve Question")

        if action == "Solve Question" or mode == "study":
            prompt += (
                "\n\n**CRITICAL INSTRUCTION: COMPLETE STEP-BY-STEP MATHEMATICAL SOLUTION**\n"
                "The user needs the fully worked and solved mathematical solution to the problem or questions present in the notes:\n"
                "1. \\section*{Problem Statement}: State the transcribed problem or equation clearly.\n"
                "2. \\section*{Key Principles and Formulas}: State the relevant mathematical formulas or methods needed.\n"
                "3. \\section*{Step-by-Step Solution}: Provide the complete, explicit mathematical solution with all intermediate algebraic and calculus steps using \\begin{align*} ... \\end{align*}.\n"
                "4. \\section*{Final Answer}: Enclose the final verified answer prominently inside \\boxed{...}.\n"
                "5. \\section*{Key Takeaways}: 2 concise bullet points explaining intuition or tips.\n"
                "Do NOT just repeat or transcribe the question; you MUST compute and solve the answer completely."
            )
        else:
            prompt += (
                "\n\n**CRITICAL INSTRUCTION: TRANSCRIBE AND TYPESET ONLY**\n"
                "The user wants clean, beautifully formatted LaTeX exactly representing the notes. "
                "Organize sections, fix OCR artifacts, and format all equations cleanly."
            )

        # If retrying after a build error, pass the error to the LLM to fix
        if job.has_build_error and job.build_error_trace:
            prompt += f"\n\nPREVIOUS COMPILATION ERROR:\nThe previous LaTeX code failed to compile with the following error:\n{job.build_error_trace}\n\nPlease fix the LaTeX syntax errors."

        content = ""

        # 1. PRIMARY: Groq (ultra-fast, using high-performance models for LaTeX & STEM math)
        if self.groq_api_key and Groq and not self.groq_api_key.startswith("your_"):
            try:
                client = Groq(api_key=self.groq_api_key)
                groq_models = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b", "qwen/qwen3.8-27b"]
                for gm in groq_models:
                    try:
                        response = client.chat.completions.create(
                            model=gm,
                            messages=[
                                {"role": "system", "content": "You are an expert STEM mathematician and LaTeX typesetter. Output only clean valid LaTeX document body without preamble."},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.2,
                            max_tokens=1500,
                            timeout=25.0
                        )
                        if response.choices and response.choices[0].message.content:
                            raw_resp = response.choices[0].message.content.strip()
                            # Strip think tags if model is reasoning-based
                            raw_resp = re.sub(r'<think>.*?</think>', '', raw_resp, flags=re.DOTALL).strip()
                            if raw_resp:
                                content = raw_resp
                                print(f"[{job.job_id}] Groq {gm} structuring OK ({len(content)} chars)")
                                break
                    except Exception as g_ex:
                        print(f"[{job.job_id}] Groq model {gm} error: {g_ex}")
                        continue
            except Exception as e:
                print(f"[{job.job_id}] Groq structuring failed: {e}")

        # 2. FALLBACK: Gemini (if Groq is unavailable or hits rate limits)
        if not content and self.google_api_key and not self.google_api_key.startswith("your_"):
            try:
                import warnings
                import google.generativeai as genai
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    genai.configure(api_key=self.google_api_key)
                gemini_models = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-pro"]
                for gm in gemini_models:
                    try:
                        g_model = genai.GenerativeModel(gm)
                        g_resp = g_model.generate_content(prompt)
                        if g_resp and g_resp.text:
                            content = g_resp.text.strip()
                            print(f"[{job.job_id}] Gemini {gm} structuring fallback OK ({len(content)} chars)")
                            break
                    except Exception as gem_ex:
                        print(f"[{job.job_id}] Gemini {gm} structuring error: {gem_ex}")
                        continue
            except Exception as e:
                print(f"[{job.job_id}] Gemini structuring error: {e}")

        if not content:
            # Fallback to raw transcription if all LLMs failed
            if job.raw_transcription:
                content = f"\\section*{{Transcribed Content}}\n\n{job.raw_transcription}"
            else:
                job.status = JobStatus.ERROR
                job.error_message = "Structuring failed: No LLM was able to process the request."
                return job

        # Post-process: strip markdown code blocks
        if content.startswith("```latex"):
            content = content[8:]
        elif content.startswith("```tex"):
            content = content[6:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # Strip <think>...</think> tokens emitted by reasoning models (Qwen, etc.)
        # Handle complete blocks first, then truncated ones (where </think> was never emitted)
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        if content.startswith('<think>'):
            # Incomplete think block — strip everything up to after the last newline before actual content
            end = content.find('</think>')
            if end != -1:
                content = content[end + 8:].strip()
            else:
                # No closing tag — find where actual LaTeX content starts (first \section or \begin)
                for marker in [r'\section', r'\begin', r'\documentclass', r'\subsection']:
                    idx = content.find(marker)
                    if idx != -1:
                        content = content[idx:].strip()
                        break
                else:
                    # Last resort: just drop the first 3000 chars of thinking
                    content = content[3000:].strip() if len(content) > 3000 else content

        # Sanitize stray Markdown hashes that crash Tectonic
        content = re.sub(r'^###\s+(.*)$', r'\\subsubsection*{\1}', content, flags=re.MULTILINE)
        content = re.sub(r'^##\s+(.*)$', r'\\subsection*{\1}', content, flags=re.MULTILINE)
        content = re.sub(r'^#\s+(.*)$', r'\\section*{\1}', content, flags=re.MULTILINE)

        # Replace unescaped hash symbols (outside math)
        content = re.sub(r'(?<!\\)#', r'\\#', content)

        # Fix any erroneous escaped ampersands before equals or math operators
        content = re.sub(r'\\&\s*=', '&=', content)
        content = re.sub(r'([a-zA-Z0-9\)])\s*\\&\s*=', r'\1 &=', content)
        content = re.sub(r'\\&(?=\s*[\+\-\*\/\=])', '&', content)

        # Replace unescaped & outside of tabular/align environments
        # CRITICAL: Use re.escape on each environment name so that 'align*' does not treat '*' as a regex quantifier!
        lines = content.split('\n')
        sanitized = []
        in_math_env = False
        math_envs = {
            'align', 'align*', 'aligned', 'tabular', 'array', 'matrix',
            'pmatrix', 'bmatrix', 'vmatrix', 'equation', 'equation*',
            'gather', 'gather*', 'multline', 'multline*'
        }
        math_begin_pattern = re.compile(r'\\begin\{(' + '|'.join(re.escape(e) for e in math_envs) + r')\}')
        math_end_pattern = re.compile(r'\\end\{(' + '|'.join(re.escape(e) for e in math_envs) + r')\}')

        for line in lines:
            stripped = line.strip()
            if math_begin_pattern.search(stripped):
                in_math_env = True

            if in_math_env:
                # Inside math environments, unescape any erroneous \& back to &
                line = line.replace(r'\&=', '&=').replace(r'\&', '&')
            elif '$' not in line:
                # Only escape bare & in pure text lines outside math
                line = re.sub(r'(?<!\\)&', r'\\&', line)

            if math_end_pattern.search(stripped):
                in_math_env = False
            sanitized.append(line)
        content = '\n'.join(sanitized)

        job.structured_latex = content.strip()
        return job


class TemplateApplyAgent:
    """Merges structured content into the selected .tex template."""

    def run(self, job: LatexJob) -> LatexJob:
        job.step = "Applying Template"
        job.progress_percentage = 60
        print(f"[{job.job_id}] Applying template: {job.template_type}")

        # Map frontend template names to files
        template_map = {
            "Assignment": "assignment.tex",
            "Research Paper": "research_paper.tex",
            "Homework": "homework.tex",
            "Lecture Slides": "lecture_slides.tex"
        }
        
        filename = template_map.get(job.template_type, "homework.tex")
        template_path = os.path.join(os.path.dirname(__file__), "..", "templates", filename)
        template_path = os.path.abspath(template_path)

        try:
            if os.path.exists(template_path):
                with open(template_path, "r", encoding="utf-8") as f:
                    template_content = f.read()
                final_tex = template_content.replace("{{CONTENT_BODY}}", job.structured_latex or "")
            else:
                # Minimal fallback document if template file is missing
                final_tex = (
                    "\\documentclass[12pt]{article}\n"
                    "\\usepackage[margin=1in]{geometry}\n"
                    "\\usepackage{amsmath, amssymb, amsthm, xcolor}\n"
                    "\\begin{document}\n\n"
                    f"{job.structured_latex or ''}\n\n"
                    "\\end{document}\n"
                )

            job.final_tex_code = final_tex
            job.status = JobStatus.DONE
            job.step = "LaTeX Generated"
            job.progress_percentage = 100
        except Exception as e:
            job.status = JobStatus.ERROR
            job.error_message = f"Template apply failed: {str(e)}"

        return job


class TectonicCompileAgent:
    """Compiles the LaTeX document via tectonic and catches any build errors."""

    def run(self, job: LatexJob) -> LatexJob:
        job.step = "Compiling PDF"
        job.progress_percentage = 80
        print(f"[{job.job_id}] Compiling PDF with tectonic...")

        if not job.final_tex_code:
            job.status = JobStatus.ERROR
            job.error_message = "No LaTeX code to compile."
            return job

        # Create a temporary directory for the build
        temp_dir = tempfile.mkdtemp()
        tex_path = os.path.join(temp_dir, "document.tex")
        pdf_path = os.path.join(temp_dir, "document.pdf")

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(job.final_tex_code)

        try:
            # Find tectonic binary
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            local_tectonic = os.path.join(project_root, "tectonic.exe")
            tectonic_cmd = local_tectonic if os.path.exists(local_tectonic) else "tectonic"
            
            out_file_path = os.path.join(temp_dir, "stdout.txt")
            try:
                with open(out_file_path, "w") as outf:
                    result = subprocess.run(
                        [tectonic_cmd, tex_path],
                        cwd=temp_dir,
                        stdout=outf,
                        stderr=subprocess.STDOUT,
                        text=True,
                        timeout=120
                    )
            except FileNotFoundError:
                print(f"[{job.job_id}] Tectonic compiler binary not found in PATH or project root. LaTeX source preserved.")
                # We still keep the LaTeX code and mark DONE so user can view/edit the LaTeX
                job.status = JobStatus.DONE
                job.progress_percentage = 100
                return job

            if result.returncode != 0:
                print(f"[{job.job_id}] Tectonic compilation returned non-zero code.")
                job.has_build_error = True
                
                trace_content = ""
                if os.path.exists(out_file_path):
                    with open(out_file_path, "r") as outf:
                        trace_content = outf.read()
                
                job.build_error_trace = trace_content
                job.retry_count += 1
                
                # Keep job marked DONE with final_tex_code available for the editor
                job.status = JobStatus.DONE
                job.progress_percentage = 100
            else:
                job.has_build_error = False
                job.build_error_trace = None
                
                # Copy the PDF to tempdir for FastAPI serving
                import shutil
                final_pdf_path = os.path.join(tempfile.gettempdir(), f"{job.job_id}.pdf")
                if os.path.exists(pdf_path):
                    shutil.copy2(pdf_path, final_pdf_path)
                    job.pdf_path = final_pdf_path
                
                job.status = JobStatus.DONE
                job.progress_percentage = 100
                print(f"[{job.job_id}] PDF compiled successfully: {job.pdf_path}")
        except Exception as e:
            print(f"[{job.job_id}] Compilation process notice: {e}")
            # Ensure LaTeX code is still delivered to user
            job.status = JobStatus.DONE
            job.progress_percentage = 100

        return job
