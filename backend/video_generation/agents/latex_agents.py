import os
import subprocess
import tempfile
from typing import Optional
from backend.video_generation.models import LatexJob, JobStatus

# Try to use groq, which should be installed
try:
    from groq import Groq
except ImportError:
    Groq = None

STRUCTURE_PROMPT_TEMPLATE = """You are an expert LaTeX typesetter. I will provide raw transcribed math and text fragments extracted via OCR from handwritten notes, along with the requested document template type.

Your task is to organize and structure these fragments into a clean, semantically correct LaTeX document body.

CRITICAL RULES:
1. **Math Environments**: 
   - Use `$ ... $` for short, inline math embedded within text sentences.
   - Use `\\begin{{equation}} ... \\end{{equation}}` for standalone, single-line important equations.
   - Use `\\begin{{align*}} ... \\end{{align*}}` for multi-line derivations or equations aligned at the `=` sign.
2. **Ambiguity & Illegibility**: 
   - If a handwritten fragment is illegible or the OCR output is ambiguous garbage, make your best guess but wrap it in a `\\textcolor{{red}}{{??[BEST_GUESS]??}}` flag so the student can review it. Do not quietly drop content.
3. **Template-Specific Formatting**:
   - **Lecture Slides (Beamer)**: If the template type is "Lecture Slides", detect natural break points (e.g., large blank gaps, horizontal lines, headers, numbered lists) and wrap each logical section in `\\begin{{frame}}{{Slide Title}} ... \\end{{frame}}`. Infer appropriate slide titles.
   - **Standard Documents**: Use `\\section{{}}` and `\\subsection{{}}` where you detect headers or natural topic transitions. Use `\\begin{{itemize}}` for bulleted lists.
4. **Syntax Corrections**: Automatically fix obvious OCR artifacts (e.g., `l` instead of `1`, or malformed integral bounds). Ensure all braces `{{}}` match.
5. **Output Constraints**: 
   - Do NOT output `\\documentclass`, `\\usepackage`, or `\\begin{{document}}`. 
   - Output ONLY the internal body content (the raw LaTeX). 
   - This output will be directly injected into a `{{{{CONTENT_BODY}}}}` slot in a pre-existing template.
   - Do NOT wrap your output in markdown code blocks like ```latex ... ```. Output raw text.
6. **NO MARKDOWN**: NEVER use `#` or `##` for headers. NEVER use `**` for bold. This must be pure LaTeX code. Markdown characters will cause a fatal compiler crash!

Template Type: {template_type}

Raw transcription:
{raw_text}
"""


class LatexTranscribeAgent:
    """Uses Gemini 3.5 Flash Lite to extract raw LaTeX from the handwritten image (Groq Vision was decommissioned)."""
    
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")

    def run(self, job: LatexJob) -> LatexJob:
        job.step = "Transcribing Handwriting"
        job.progress_percentage = 10
        print(f"[{job.job_id}] Transcribing handwriting with Gemini...")

        if not self.api_key:
            job.status = JobStatus.ERROR
            job.error_message = "GOOGLE_API_KEY missing from environment."
            return job

        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel("gemini-3.5-flash-lite")
            
            prompt = "Transcribe this handwritten math and text into LaTeX, preserving structure. Output only the LaTeX, no explanation."
            image_part = {
                "mime_type": "image/png",
                "data": job.image_b64
            }
            
            response = model.generate_content([prompt, image_part])
            job.raw_transcription = response.text
        except Exception as e:
            job.status = JobStatus.ERROR
            job.error_message = f"Transcription failed: {str(e)}"

        return job



class LatexStructureAgent:
    """Uses Groq text LLM to structure the fragments and fix ordering."""

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")

    def run(self, job: LatexJob) -> LatexJob:
        job.step = "Structuring Document"
        job.progress_percentage = 30
        print(f"[{job.job_id}] Structuring document...")

        if not self.api_key or not Groq:
            job.status = JobStatus.ERROR
            job.error_message = "GROQ_API_KEY missing or Groq package not installed."
            return job

        try:
            client = Groq(api_key=self.api_key)
            prompt = STRUCTURE_PROMPT_TEMPLATE.format(
                template_type=job.template_type,
                raw_text=job.raw_transcription or ""
            )

            if getattr(job, "mode", "study") == "study":
                prompt += (
                    "\n\n**CRITICAL INSTRUCTION: STUDY MODE**\n"
                    "The user is in STUDY MODE. Treat this as a comprehensive study guide. "
                    "Expand heavily on the concepts mentioned, provide detailed step-by-step breakdowns, "
                    "and create a 'proper note' format for the user to learn from. Add rich, clear explanations."
                )
            else:
                action = getattr(job, "classroom_action", "Solve Question")
                if action == "Solve Question":
                    prompt += (
                        "\n\n**CRITICAL INSTRUCTION: CLASSROOM MODE - SOLVE**\n"
                        "The user wants you to solve the math problem or answer the question present in the text. "
                        "Provide a DIRECT ANSWER and show relevant steps, but keep the explanation minimal and straight-to-the-point without over-explaining."
                    )
                else:
                    prompt += (
                        "\n\n**CRITICAL INSTRUCTION: CLASSROOM MODE - TRANSCRIBE**\n"
                        "The user wants you to strictly format the text and math exactly as written to create a LaTeX document. "
                        "DO NOT answer any questions and DO NOT hallucinate explanations. Just transcribe."
                    )

            # If retrying after a build error, pass the error to the LLM to fix
            if job.has_build_error and job.build_error_trace:
                prompt += f"\n\nPREVIOUS COMPILATION ERROR:\nThe previous LaTeX code failed to compile with the following error:\n{job.build_error_trace}\n\nPlease fix the LaTeX syntax errors."

            response = client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                timeout=30.0
            )
            content = response.choices[0].message.content or ""
            
            # Post-process: strip markdown blocks
            content = content.strip()
            if content.startswith("```latex"):
                content = content[8:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            # Sanitize stray Markdown hashes that crash Tectonic
            import re
            content = re.sub(r'^###\s+(.*)$', r'\\subsubsection*{\1}', content, flags=re.MULTILINE)
            content = re.sub(r'^##\s+(.*)$', r'\\subsection*{\1}', content, flags=re.MULTILINE)
            content = re.sub(r'^#\s+(.*)$', r'\\section*{\1}', content, flags=re.MULTILINE)
            content = content.replace("#", "\\#")  # Escape any remaining hashes
            
            job.structured_latex = content.strip()
        except Exception as e:
            job.status = JobStatus.ERROR
            job.error_message = f"Structuring failed: {str(e)}"

        return job


class TemplateApplyAgent:
    """Merges structured content into the selected .tex template."""

    def run(self, job: LatexJob) -> LatexJob:
        job.step = "Applying Template"
        job.progress_percentage = 50
        print(f"[{job.job_id}] Applying template: {job.template_type}")

        # Map frontend template names to files
        template_map = {
            "Assignment": "assignment.tex",
            "Research Paper": "research_paper.tex",
            "Homework": "homework.tex",
            "Lecture Slides": "lecture_slides.tex"
        }
        
        filename = template_map.get(job.template_type, "assignment.tex")
        template_path = os.path.join(os.path.dirname(__file__), "..", "templates", filename)
        template_path = os.path.abspath(template_path)

        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template_content = f.read()

            final_tex = template_content.replace("{{CONTENT_BODY}}", job.structured_latex or "")
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
        job.progress_percentage = 70
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
            # Run tectonic
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            local_tectonic = os.path.join(project_root, "tectonic.exe")
            
            # Prefer local tectonic.exe if it exists, else assume it's in PATH
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
                        timeout=1200
                    )
            except FileNotFoundError:
                job.status = JobStatus.ERROR
                job.error_message = "Tectonic compiler not found on this system.\nPlease install tectonic (e.g., 'winget install tectonic' on Windows or 'brew install tectonic' on macOS) and ensure it is in your system PATH."
                return job

            if result.returncode != 0:
                print(f"[{job.job_id}] Tectonic compilation failed.")
                job.has_build_error = True
                
                # Read the trace from the output file
                trace_content = ""
                if os.path.exists(out_file_path):
                    with open(out_file_path, "r") as outf:
                        trace_content = outf.read()
                
                job.build_error_trace = trace_content
                job.retry_count += 1
                
                if job.retry_count >= 2:
                    job.status = JobStatus.ERROR
                    job.error_message = f"Compilation failed after max retries. Last error: {job.build_error_trace}"
            else:
                job.has_build_error = False
                job.build_error_trace = None
                
                # Copy the PDF to the root temp directory so FastAPI can serve it
                import shutil
                final_pdf_path = os.path.join(tempfile.gettempdir(), f"{job.job_id}.pdf")
                shutil.copy2(pdf_path, final_pdf_path)
                
                job.pdf_path = final_pdf_path
                job.status = JobStatus.DONE
                job.progress_percentage = 100
                print(f"[{job.job_id}] PDF compiled successfully: {final_pdf_path}")
        except Exception as e:
            job.status = JobStatus.ERROR
            job.error_message = f"Compilation process failed: {str(e)}"

        return job
