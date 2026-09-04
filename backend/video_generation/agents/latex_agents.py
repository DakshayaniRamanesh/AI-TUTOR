import os
import subprocess
import tempfile
from typing import Optional
from backend.video_generation.models import LatexJob, JobStatus
from backend.workspace.artifact_store import artifact_store

# Try to use groq, which should be installed
try:
    from groq import Groq
except ImportError:
    Groq = None

STRUCTURE_PROMPT_TEMPLATE = """You are an expert Document Structurer. I will provide raw transcribed math and text fragments extracted via OCR from handwritten notes.

Your task is to organize and structure these fragments into a JSON DocumentIR.

CRITICAL RULES:
1. Output ONLY valid JSON conforming to the following structure:
{{
  "title": "Inferred Document Title",
  "blocks": [
    {{
      "type": "heading|paragraph|equation|list|slide_title",
      "content": "Text or LaTeX math content",
      "level": 1,
      "items": ["list item 1", "list item 2"] 
    }}
  ]
}}
2. Use "heading" for sections. Set "level": 1 for main sections, 2 for subsections.
3. Use "slide_title" to delineate new slides if the template is "Lecture Slides".
4. Use "equation" for standalone math equations.
5. Use "list" for bullet points, and put the points in the "items" array.
6. Use "paragraph" for regular text. You may use inline math ($...$) within text.
7. Do NOT include Markdown formatting like **bold** or # headings.
8. NEVER wrap your JSON in ```json blocks. Output RAW JSON ONLY.

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
            
            # Post-process: strip markdown blocks and get json
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            content = content.strip()
            
            # Validate JSON
            import json
            try:
                json.loads(content)
            except json.JSONDecodeError as e:
                # Basic fallback
                content = json.dumps({
                    "title": "Transcription",
                    "blocks": [{"type": "paragraph", "content": content}]
                })
            
            job.structured_latex = content

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
            import json
            ir = json.loads(job.structured_latex or "{}")
            
            blocks = ir.get("blocks", [])
            latex_parts = []
            
            is_slides = job.template_type == "Lecture Slides"
            in_frame = False
            
            for block in blocks:
                b_type = block.get("type", "paragraph")
                content = block.get("content", "")
                level = block.get("level", 1)
                items = block.get("items", [])
                
                if b_type == "slide_title":
                    if in_frame:
                        latex_parts.append("\\end{frame}\n")
                    latex_parts.append(f"\\begin{{frame}}{{{content}}}\n")
                    in_frame = True
                elif b_type == "heading":
                    if is_slides:
                        if in_frame:
                            latex_parts.append("\\end{frame}\n")
                        latex_parts.append(f"\\begin{{frame}}{{{content}}}\n")
                        in_frame = True
                    else:
                        if level == 1:
                            latex_parts.append(f"\\section*{{{content}}}")
                        else:
                            latex_parts.append(f"\\subsection*{{{content}}}")
                elif b_type == "equation":
                    latex_parts.append(f"\\begin{{equation}}\n{content}\n\\end{{equation}}")
                elif b_type == "list":
                    latex_parts.append("\\begin{itemize}")
                    for item in items:
                        latex_parts.append(f"    \\item {item}")
                    latex_parts.append("\\end{itemize}")
                else: # paragraph
                    latex_parts.append(content)
            
            if is_slides and in_frame:
                latex_parts.append("\\end{frame}\n")
                
            body_tex = "\n\n".join(latex_parts)

            with open(template_path, "r", encoding="utf-8") as f:
                template_content = f.read()

            final_tex = template_content.replace("{{CONTENT_BODY}}", body_tex)
            job.final_tex_code = final_tex
            job.step = "LaTeX Generated"
            job.progress_percentage = 60
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
        import shutil
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
                
                # Copy the PDF to the artifact store so FastAPI can serve it
                final_pdf_path = artifact_store.put(job.job_id, "document.pdf", pdf_path)
                
                job.pdf_path = final_pdf_path
                job.status = JobStatus.DONE
                job.progress_percentage = 100
                print(f"[{job.job_id}] PDF compiled successfully: {final_pdf_path}")
        except Exception as e:
            job.status = JobStatus.ERROR
            job.error_message = f"Compilation process failed: {str(e)}"
        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

        return job
