from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from backend.video_generation.models import JobStatus, LatexJob
from backend.workspace.artifact_store import artifact_store

try:
    from groq import Groq
except ImportError:
    Groq = None


STRUCTURE_PROMPT_TEMPLATE = """You are an expert document structurer.
Convert the supplied transcription into JSON DocumentIR.

Return ONLY valid JSON:
{{
  "title": "Document title",
  "blocks": [
    {{
      "type": "heading|paragraph|equation|list|slide_title",
      "content": "text or LaTeX math",
      "level": 1,
      "items": ["item"]
    }}
  ]
}}

Rules:
- heading level 1 = main section, level 2 = subsection.
- equation contains only equation content, without $$ or \\[ \\] wrappers.
- list items go in items.
- no Markdown fences.
- do not invent source content in transcription mode.

Template: {template_type}
Raw transcription:
{raw_text}
"""


def _strip_data_url(value: str) -> str:
    value = (value or "").strip()
    if value.startswith("data:") and "," in value:
        return value.split(",", 1)[1]
    return value


def _extract_json_object(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    first = text.find("{")
    last = text.rfind("}")
    if first < 0 or last <= first:
        raise ValueError("Model did not return a JSON object.")
    data = json.loads(text[first : last + 1])
    if not isinstance(data, dict) or not isinstance(data.get("blocks", []), list):
        raise ValueError("DocumentIR JSON has an invalid shape.")
    return data


def _mode_instruction(job: LatexJob) -> str:
    mode = (getattr(job, "mode", "study") or "study").lower()
    action = getattr(job, "classroom_action", "Solve Question") or "Solve Question"

    if mode == "study":
        return (
            "\nMODE: STUDY. Build clear study notes grounded in the transcription. "
            "You may explain detected concepts, but do not invent unrelated sections."
        )
    if action == "Solve Question":
        return (
            "\nMODE: SOLVE. Solve the detected question with concise, correct steps "
            "and a direct final answer."
        )
    return (
        "\nMODE: TRANSCRIBE. Preserve the source faithfully. Do not solve questions "
        "or add explanations that were not present."
    )


class LatexTranscribeAgent:
    """Vision OCR/transcription only. It does not perform study expansion."""

    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.model_name = os.getenv("GEMINI_VISION_MODEL", "gemini-3.5-flash-lite")

    def run(self, job: LatexJob) -> LatexJob:
        job.step = "Transcribing Handwriting"
        job.progress_percentage = 10

        if not self.api_key:
            job.status = JobStatus.ERROR
            job.error_message = "GOOGLE_API_KEY missing from environment."
            return job
        if not job.image_b64:
            job.status = JobStatus.ERROR
            job.error_message = "No image data was supplied for LaTeX transcription."
            return job

        try:
            import google.generativeai as genai

            image_bytes = base64.b64decode(_strip_data_url(job.image_b64), validate=False)
            if not image_bytes:
                raise ValueError("Decoded image is empty.")

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model_name)
            prompt = (
                "Faithfully transcribe the handwritten math and text. Preserve ordering "
                "and mathematical notation. Return plain transcription/LaTeX fragments only; "
                "do not solve or expand the content."
            )
            response = model.generate_content(
                [prompt, {"mime_type": "image/png", "data": image_bytes}]
            )
            text = (getattr(response, "text", "") or "").strip()
            if not text:
                raise ValueError("Vision model returned an empty transcription.")
            job.raw_transcription = text
            return job
        except Exception as exc:
            job.status = JobStatus.ERROR
            job.error_message = f"Transcription failed: {exc}"
            return job


class LatexStructureAgent:
    """Turn transcription into DocumentIR. Groq is primary; Gemini is a real fallback."""

    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.groq_model = os.getenv("GROQ_TEXT_MODEL", "qwen/qwen3.8-27b")
        self.gemini_model = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.5-flash-lite")

    def _call_groq(self, prompt: str) -> str:
        if not self.groq_api_key or Groq is None:
            return ""
        client = Groq(api_key=self.groq_api_key)
        response = client.chat.completions.create(
            model=self.groq_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            timeout=45.0,
        )
        return response.choices[0].message.content or ""

    def _call_gemini(self, prompt: str) -> str:
        if not self.google_api_key:
            return ""
        import google.generativeai as genai

        genai.configure(api_key=self.google_api_key)
        response = genai.GenerativeModel(self.gemini_model).generate_content(prompt)
        return getattr(response, "text", "") or ""

    def run(self, job: LatexJob) -> LatexJob:
        job.step = "Structuring Document"
        job.progress_percentage = 30

        if not job.raw_transcription:
            job.status = JobStatus.ERROR
            job.error_message = "No transcription is available to structure."
            return job

        prompt = STRUCTURE_PROMPT_TEMPLATE.format(
            template_type=job.template_type,
            raw_text=job.raw_transcription,
        )
        prompt += _mode_instruction(job)

        if job.has_build_error and job.build_error_trace:
            prompt += (
                "\nThe previous deterministic LaTeX render failed. Correct the structured "
                "content that caused this compiler diagnostic:\n"
                + job.build_error_trace[-3000:]
            )

        errors: list[str] = []
        content = ""

        try:
            content = self._call_groq(prompt)
        except Exception as exc:
            errors.append(f"Groq: {exc}")

        if not content:
            try:
                content = self._call_gemini(prompt)
            except Exception as exc:
                errors.append(f"Gemini: {exc}")

        if not content:
            job.status = JobStatus.ERROR
            job.error_message = (
                "Document structuring failed: no text model was available. "
                + " | ".join(errors)
            )
            return job

        try:
            ir = _extract_json_object(content)
            job.structured_latex = json.dumps(ir, ensure_ascii=False)
            return job
        except Exception as exc:
            job.status = JobStatus.ERROR
            job.error_message = f"Document structuring returned invalid JSON: {exc}"
            return job


def _normalize_equation(value: str) -> str:
    value = (value or "").strip()
    if value.startswith("$$") and value.endswith("$$"):
        value = value[2:-2].strip()
    if value.startswith(r"\[") and value.endswith(r"\]"):
        value = value[2:-2].strip()
    return value


class TemplateApplyAgent:
    """Deterministically render DocumentIR into one of the known templates."""

    TEMPLATE_MAP = {
        "Assignment": "assignment.tex",
        "Research Paper": "research_paper.tex",
        "Homework": "homework.tex",
        "Lecture Slides": "lecture_slides.tex",
    }

    def run(self, job: LatexJob) -> LatexJob:
        job.step = "Applying Template"
        job.progress_percentage = 50

        filename = self.TEMPLATE_MAP.get(job.template_type)
        if not filename:
            job.status = JobStatus.ERROR
            job.error_message = f"Unknown LaTeX template: {job.template_type!r}"
            return job

        template_path = (
            Path(__file__).resolve().parent.parent / "templates" / filename
        )

        try:
            ir = json.loads(job.structured_latex or "{}")
            blocks = ir.get("blocks", [])
            if not isinstance(blocks, list):
                raise ValueError("DocumentIR.blocks must be a list.")

            latex_parts: list[str] = []
            is_slides = job.template_type == "Lecture Slides"
            in_frame = False

            for block in blocks:
                if not isinstance(block, dict):
                    continue
                block_type = str(block.get("type", "paragraph"))
                content = str(block.get("content", "") or "").strip()
                level = int(block.get("level", 1) or 1)
                items = block.get("items", [])
                if not isinstance(items, list):
                    items = []

                if block_type == "slide_title":
                    if in_frame:
                        latex_parts.append(r"\end{frame}")
                    latex_parts.append(rf"\begin{{frame}}{{{content}}}")
                    in_frame = True
                elif block_type == "heading":
                    if is_slides:
                        if in_frame:
                            latex_parts.append(r"\end{frame}")
                        latex_parts.append(rf"\begin{{frame}}{{{content}}}")
                        in_frame = True
                    elif level <= 1:
                        latex_parts.append(rf"\section*{{{content}}}")
                    else:
                        latex_parts.append(rf"\subsection*{{{content}}}")
                elif block_type == "equation":
                    eq = _normalize_equation(content)
                    if eq:
                        latex_parts.append(
                            "\\begin{equation}\n" + eq + "\n\\end{equation}"
                        )
                elif block_type == "list":
                    latex_parts.append(r"\begin{itemize}")
                    for item in items:
                        latex_parts.append(r"    \item " + str(item))
                    latex_parts.append(r"\end{itemize}")
                elif content:
                    latex_parts.append(content)

            if is_slides and in_frame:
                latex_parts.append(r"\end{frame}")

            body_tex = "\n\n".join(latex_parts)
            template_content = template_path.read_text(encoding="utf-8")
            if "{{CONTENT_BODY}}" not in template_content:
                raise ValueError(f"Template {filename} is missing {{CONTENT_BODY}}.")
            job.final_tex_code = template_content.replace("{{CONTENT_BODY}}", body_tex)
            job.step = "LaTeX Generated"
            job.progress_percentage = 60
            return job
        except Exception as exc:
            job.status = JobStatus.ERROR
            job.error_message = f"Template apply failed: {exc}"
            return job


def _find_tectonic() -> str | None:
    explicit = os.getenv("TECTONIC_BIN", "").strip()
    if explicit and os.path.isfile(explicit):
        return explicit

    project_root = Path(__file__).resolve().parents[3]
    legacy = project_root / "tectonic.exe"
    if legacy.is_file():
        return str(legacy)

    return shutil.which("tectonic") or shutil.which("tectonic.exe")


class TectonicCompileAgent:
    MAX_RETRIES = 2

    def run(self, job: LatexJob) -> LatexJob:
        job.step = "Compiling PDF"
        job.progress_percentage = 70

        if not job.final_tex_code:
            job.status = JobStatus.ERROR
            job.error_message = "No LaTeX code to compile."
            return job

        tectonic_cmd = _find_tectonic()
        if not tectonic_cmd:
            job.status = JobStatus.ERROR
            job.error_message = (
                "Tectonic compiler is not installed. Install Tectonic and put it on PATH, "
                "or set TECTONIC_BIN to the executable path."
            )
            return job

        try:
            with tempfile.TemporaryDirectory(prefix=f"latex_{job.job_id}_") as temp_dir:
                tex_path = os.path.join(temp_dir, "document.tex")
                pdf_path = os.path.join(temp_dir, "document.pdf")
                with open(tex_path, "w", encoding="utf-8") as f:
                    f.write(job.final_tex_code)

                result = subprocess.run(
                    [tectonic_cmd, tex_path],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )

                if result.returncode != 0 or not os.path.isfile(pdf_path):
                    job.has_build_error = True
                    job.build_error_trace = (
                        result.stderr or result.stdout or "Tectonic produced no PDF."
                    )[-6000:]
                    job.retry_count += 1
                    if job.retry_count >= self.MAX_RETRIES:
                        job.status = JobStatus.ERROR
                        job.error_message = (
                            "Compilation failed after 2 attempts. Last compiler error:\n"
                            + job.build_error_trace[-2500:]
                        )
                    return job

                job.has_build_error = False
                job.build_error_trace = None
                job.pdf_path = artifact_store.put(
                    job.job_id, "document.pdf", pdf_path
                )
                job.status = JobStatus.DONE
                job.progress_percentage = 100
                return job
        except subprocess.TimeoutExpired:
            job.status = JobStatus.ERROR
            job.error_message = "Tectonic compilation timed out after 180 seconds."
            return job
        except Exception as exc:
            job.status = JobStatus.ERROR
            job.error_message = f"Compilation process failed: {exc}"
            return job
