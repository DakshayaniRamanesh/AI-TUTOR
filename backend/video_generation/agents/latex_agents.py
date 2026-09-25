import os
import io
import re
import base64
import subprocess
import tempfile
from typing import Optional
from backend.video_generation.models import LatexJob, JobStatus
from backend.workspace.artifact_store import artifact_store

# Try to import groq
try:
    from groq import Groq
except ImportError:
    Groq = None

# ── Shared LaTeX formatting rules (injected into every prompt) ────────────────
_LATEX_RULES = """
UNIVERSAL LATEX RULES (ALWAYS APPLY):
1. Math Environments:
   - Use `$ ... $` for inline math within sentences.
   - Use `\\[ ... \\]` for standalone single-line display formulas.
   - Use `\\begin{align*} ... \\end{align*}` ONLY for multi-line derivations aligned at `&=`.
   - In align*, every line must be pure math. NEVER put text labels before `&`.
   - NEVER use `&` inside variable names. NEVER write `\\&` inside equations.
2. Structure:
   - Use `\\section*{...}` and `\\subsection*{...}` for headings.
   - Use `\\begin{itemize} ... \\end{itemize}` for bullet lists.
   - Use `\\begin{enumerate} ... \\end{enumerate}` for numbered lists.
3. Output constraints:
   - Do NOT output `\\documentclass`, `\\usepackage`, or `\\begin{document}`.
   - Output ONLY the raw LaTeX body.
   - Do NOT wrap output in markdown code fences.
   - NEVER use `#`, `##`, `**` — this must be pure LaTeX.
   - Use `\\textbf{...}` for bold, `\\emph{...}` for italics.
"""

# ── Dynamic pedagogical prompt templates ──────────────────────────────────────
_THEORY_PROMPT = """
You are an expert educator and LaTeX typesetter.

Create a rich, deep conceptual EXPLANATION of the following topic:
{input_text}

WRITING INSTRUCTIONS:
- This is NOT a homework problem. Do NOT invent a toy problem and solve it.
- Do NOT use sections named "Problem Statement", "Step-by-Step Solution", or "Final Answer".
- Write genuinely educational content that helps a student deeply understand this concept.
- Use TOPIC-SPECIFIC section headings that reflect the actual subject matter (e.g. \\section*{{The Principle of Momentum}}, \\section*{{Physical Intuition}}).

REQUIRED STRUCTURE (adapt section names to the topic):
1. \\section*{{<Descriptive Conceptual Title>}}: A clear, intuitive statement of what this concept IS and WHY it matters. Motivate it with a real-world scenario or analogy.
2. \\section*{{<Governing Laws / Formal Formulation>}}: State the formal mathematical definition, law, or governing equation. Explain what each symbol means.
3. \\section*{{<Mechanism / How It Works>}}: Explain the physical, mathematical, or logical mechanism. Walk through the key ideas, consequences, and limits of validity.
4. \\section*{{<Key Properties and Applications>}}: 3-5 important properties, consequences, or real-world applications as bullet points.

{rules}
"""

_PROBLEM_PROMPT = """
You are an expert STEM mathematician and LaTeX typesetter.

Solve the following problem or exercise completely:
{input_text}

WRITING INSTRUCTIONS:
- PROVIDE A COMPLETE, EXHAUSTIVE STEP-BY-STEP SOLUTION. Never skip steps.
- Always enclose the verified final answer in \\boxed{{...}}.
- Section headings should be descriptive and topic-specific (e.g. \\section*{{Setting Up the Equation}}, NOT just \\section*{{Step 1}}).

REQUIRED STRUCTURE:
1. \\section*{{Problem Setup}}: Clearly state the problem, identify what is given and what is to be found.
2. \\section*{{Strategy and Key Principles}}: Identify the mathematical method or theorem that applies and briefly explain why.
3. \\section*{{Detailed Solution}}: Complete derivation using \\begin{{align*}} ... \\end{{align*}} with every algebraic step shown.
4. \\section*{{Final Answer}}: Enclose the result in \\boxed{{...}}.
5. \\section*{{Key Insights}}: 2-3 concise bullet points on important observations, common mistakes to avoid, or generalizations.

{rules}
"""

_PROOF_PROMPT = """
You are an expert mathematician and LaTeX typesetter.

Present a rigorous, complete MATHEMATICAL PROOF for:
{input_text}

WRITING INSTRUCTIONS:
- This is a formal proof. Present it with mathematical rigor.
- Do NOT reduce this to a homework problem with a numeric answer.
- Section headings should reflect the actual theorem and proof structure.

REQUIRED STRUCTURE:
1. \\section*{{<Theorem Name>}}: State the theorem, lemma, or identity precisely in mathematical language.
2. \\section*{{Setup and Definitions}}: Define all variables, structures, and any auxiliary constructions needed.
3. \\section*{{Proof}}: Rigorous step-by-step logical deduction. Use \\begin{{align*}} for equational derivations.
4. \\section*{{Conclusion}}: State what has been proven and its mathematical significance (e.g. \\emph{{Q.E.D.}}).
5. \\section*{{Corollaries and Significance}} (optional): Direct consequences or applications of the theorem.

{rules}
"""

_ALGORITHM_PROMPT = """
You are an expert computer scientist / scientist and LaTeX typesetter.

Explain and walk through the following ALGORITHM, PROCESS, or PROCEDURE:
{input_text}

WRITING INSTRUCTIONS:
- This is NOT a math problem to solve for a numeric answer.
- Explain how the algorithm WORKS, its purpose, invariants, and trade-offs.
- Section headings should describe actual phases or properties of this algorithm.

REQUIRED STRUCTURE:
1. \\section*{{Purpose and High-Level Idea}}: Explain in plain terms what this algorithm does and the central insight behind it.
2. \\section*{{Core Mechanics and Invariants}}: Describe the key data structures, loop invariant, or logical conditions that make it work.
3. \\section*{{Step-by-Step Walkthrough}}: Walk through the algorithm on a clear, concrete small example using `\\begin{{enumerate}}` for each step.
4. \\section*{{Complexity and Trade-offs}}: State time/space complexity (use $O(...)$ notation) and when to use vs. avoid this approach.

{rules}
"""

_TRANSCRIBE_ONLY_PROMPT = """
You are an expert LaTeX typesetter.

Your task is strictly to TRANSCRIBE the following text and math into valid LaTeX.
{input_text}

CRITICAL RULES:
- DO NOT solve any equations.
- DO NOT correct any mistakes.
- DO NOT rearrange any expressions.
- DO NOT add any explanations.
- Output exactly what was given, but formatted beautifully in LaTeX.

{rules}
"""

def _detect_educational_intent(text: str) -> str:
    """
    Classify the educational intent of the input text.
    Returns one of: 'theory', 'problem', 'proof', 'algorithm'
    """
    low = (text or "").lower()

    # Algorithm / process signals (check before theory, shares some keywords)
    algo_signals = [
        "algorithm", "sort", "search", "binary search", "merge sort", "quick sort",
        "hash", "graph traversal", "bfs", "dfs", "dynamic programming", "memoization",
        "recursion", "iteration", "step by step", "procedure", "process", "cycle",
        "photosynthesis", "krebs cycle", "cellular respiration", "dna replication",
        "pcr", "fermentation", "how does", "how do"
    ]
    if sum(1 for s in algo_signals if s in low) >= 2 or any(
        s in low for s in ["algorithm", "photosynthesis", "krebs cycle", "sort algorithm", "dna replication"]
    ):
        return "algorithm"

    # Proof signals
    proof_signals = [
        "prove", "proof", "lemma", "corollary", "show that", "demonstrate that",
        "q.e.d", "qed", "by induction", "proof by contradiction", "by contradiction"
    ]
    if any(s in low for s in proof_signals):
        return "proof"

    # Problem/exercise signals (explicit solve request or numeric equation)
    problem_signals = [
        "solve", "find the", "calculate", "compute", "evaluate", "simplify", "differentiate",
        "integrate", "determine the value", "what is the value of", "=0", "= 0",
        "word problem", "if x", "given that", "for what value"
    ]
    import re as _re
    # Only treat '?' as a problem signal when it appears in a math context (e.g. find x = ?)
    # NOT for plain conversational questions like "What is X?"
    has_equation_to_solve = bool(_re.search(r'\\?=\s*0|solve|find\s+\w+\s*=', low))
    if any(s in low for s in problem_signals) or has_equation_to_solve:
        return "problem"

    # Theory / conceptual explanation (default for named concepts, laws, phenomena)
    theory_signals = [
        "explain", "what is", "describe", "concept", "theory", "law", "principle", "theorem",
        "definition", "overview", "introduction", "understanding", "meaning of",
        "newton", "einstein", "maxwell", "schrödinger", "heisenberg", "planck",
        "gravity", "electromagnetism", "thermodynamics", "quantum", "relativity",
        "entropy", "momentum", "conservation", "bayes", "fourier", "euler"
    ]
    if any(s in low for s in theory_signals):
        return "theory"

    # Default: if there is already structured LaTeX or pure math, treat as problem
    if r"\begin" in text or r"\[" in text or r"\frac" in text:
        return "problem"

    # Final default: theory (safer than inventing a problem)
    return "theory"


class LatexTranscribeAgent:
    """Uses Groq Vision (primary) or Google Gemini Vision (fallback) to extract raw LaTeX and math from handwriting."""
    
    def __init__(self):
        pass
                
    def run(self, job: LatexJob) -> LatexJob:
        job.step = "Transcribing Handwriting"
        job.progress_percentage = 10
        print(f"[{job.job_id}] Transcribing handwriting with Groq Vision (default)...")

        # Clean base64 string
        b64_str = job.image_b64 or ""
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        b64_str = b64_str.strip()

        if not b64_str:
            job.status = JobStatus.ERROR
            job.error_message = "No image data provided for LaTeX transcription."
            return job

        prompt = (
            "Transcribe all handwritten math equations, symbols, problems, diagrams, and text from this image into clean, precise LaTeX. "
            "Preserve all mathematical variables, formulas, subscripts, superscripts, and problem statements accurately. "
            "Output ONLY the transcribed LaTeX and text without markdown wrapping or chat preamble."
        )

        try:
            from shared.ai_client import ai_client
            # Pass the raw base64 string directly; ai_client handles the data URL/MIME wrapping
            response_text = ai_client.generate_content(prompt, image_b64=b64_str)
            import re as _re
            response_text = _re.sub(r'<think>.*?</think>', '', response_text, flags=_re.DOTALL).strip()
            print(f"[{job.job_id}] Vision transcription OK ({len(response_text)} chars)")
        except Exception as e:
            print(f"[{job.job_id}] AI transcription error: {e}")
            response_text = ""

        if not response_text:
            job.status = JobStatus.ERROR
            job.error_message = "Transcription failed: Unable to extract text from handwriting."
            return job

        job.raw_transcription = response_text
        return job



class LatexStructureAgent:
    """Uses Groq (default) or Gemini (fallback) text LLM to structure, format, and solve math problems into clean LaTeX."""

    def __init__(self):
        pass
                
    def run(self, job: LatexJob) -> LatexJob:
        job.step = "Structuring & Solving Math"
        job.progress_percentage = 35

        raw_text = (job.raw_transcription or "").strip()
        action = (getattr(job, "classroom_action", "") or "").strip()

        # ── Detect educational intent ─────────────────────────────────────────
        # classroom_action may override: e.g. "Explain Concept" forces theory intent
        if str(job.mode).lower() == "selection_exact":
            intent = "transcribe_only"
        elif action.lower() in ("explain concept", "explain theory", "conceptual overview", "theory"):
            intent = "theory"
        elif action.lower() in ("prove theorem", "formal proof", "proof"):
            intent = "proof"
        elif action.lower() in ("explain algorithm", "algorithm", "process", "procedure"):
            intent = "algorithm"
        elif action.lower() in ("solve question", "solve problem", "homework", "exercise"):
            intent = "problem"
        else:
            intent = _detect_educational_intent(raw_text)

        print(f"[{job.job_id}] Educational intent detected: {intent!r} (action={action!r}, mode={job.mode!r})")

        # ── Select the matching pedagogical prompt ────────────────────────────
        template_map = {
            "theory": _THEORY_PROMPT,
            "proof": _PROOF_PROMPT,
            "algorithm": _ALGORITHM_PROMPT,
            "problem": _PROBLEM_PROMPT,
            "transcribe_only": _TRANSCRIBE_ONLY_PROMPT,
        }
        selected_template = template_map.get(intent, _PROBLEM_PROMPT)
        prompt = selected_template.format(
            input_text=raw_text or "(no input provided)",
            rules=_LATEX_RULES
        )

        # If retrying after a build error, pass the error to the LLM to fix
        if job.has_build_error and job.build_error_trace:
            prompt += f"\n\nPREVIOUS COMPILATION ERROR:\nThe previous LaTeX code failed to compile with the following error:\n{job.build_error_trace}\n\nPlease fix the LaTeX syntax errors."

        content = ""

        content = ""
        try:
            from shared.ai_client import ai_client
            system_instruction = "You are an expert STEM mathematician and LaTeX typesetter. Output only clean valid LaTeX document body without preamble."
            content = ai_client.generate_content(prompt, system_instruction=system_instruction)
            print(f"[{job.job_id}] LaTeX structure generated via unified AI model")
        except Exception as e:
            print(f"[{job.job_id}] AI structuring error: {e}")

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

        # Normalize troublesome Unicode characters that crash Tectonic or terminal codecs
        unicode_replacements = {
            '\u2010': '-',   # Hyphen
            '\u2011': '-',   # Non-breaking hyphen
            '\u2012': '-',   # Figure dash
            '\u2013': '--',  # En dash
            '\u2014': '---', # Em dash
            '\u2015': '---', # Horizontal bar
            '\u2212': '-',   # Minus sign
            '\u00a0': ' ',   # Non-breaking space
            '\u2018': "'",   # Left single quote
            '\u2019': "'",   # Right single quote
            '\u201c': '"',   # Left double quote
            '\u201d': '"',   # Right double quote
            '\u2026': r'\dots{}', # Ellipsis
            '\u2264': r'\le ',    # Less than or equal
            '\u2265': r'\ge ',    # Greater than or equal
            '\u00d7': r'\times ', # Multiplication sign
            '\u00f7': r'\div ',   # Division sign
            '\u00b1': r'\pm ',    # Plus-minus sign
        }
        for u_char, rep in unicode_replacements.items():
            content = content.replace(u_char, rep)

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

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _extract_topic(job: "LatexJob") -> str:
        """
        Try to derive a meaningful topic title from the generated LaTeX.
        Priority:
          1. First \\section* or \\section heading in structured_latex
          2. First 60 chars of raw_transcription (cleaned)
          3. template_type as fallback (e.g. "Homework")
        """
        import re as _re

        if job.structured_latex:
            # Match \section*{...} or \section{...}
            m = _re.search(r'\\section\*?\{([^}]+)\}', job.structured_latex)
            if m:
                return m.group(1).strip()

        if job.raw_transcription:
            # Take the first meaningful line, stripped of LaTeX commands
            first_line = job.raw_transcription.strip().split('\n')[0]
            # Remove common LaTeX markup
            first_line = _re.sub(r'\\[a-zA-Z]+(\{[^}]*\})?', '', first_line)
            first_line = first_line.strip(" {}$\\")
            if first_line:
                return first_line[:72] if len(first_line) > 72 else first_line

        return job.template_type or "Document"

    # ── main run ─────────────────────────────────────────────────────────────
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

        topic = self._extract_topic(job)
        # Escape any LaTeX special chars that may appear in a topic title
        _special = {'&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#',
                    '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}',
                    '^': r'\textasciicircum{}'}
        safe_topic = ''.join(_special.get(c, c) for c in topic)

        try:
            if os.path.exists(template_path):
                with open(template_path, "r", encoding="utf-8") as f:
                    template_content = f.read()
                final_tex = (
                    template_content
                    .replace("{{TOPIC}}", safe_topic)
                    .replace("{{CONTENT_BODY}}", job.structured_latex or "")
                )
            else:
                # Minimal fallback document if template file is missing
                final_tex = (
                    "\\documentclass[12pt]{article}\n"
                    "\\usepackage[margin=1in]{geometry}\n"
                    "\\usepackage{amsmath, amssymb, amsthm, xcolor}\n"
                    "\\begin{document}\n\n"
                    f"{{\\Large\\textbf{{{safe_topic}}}}}\n\n"
                    f"{job.structured_latex or ''}\n\n"
                    "\\end{document}\n"
                )
            job.final_tex_code = final_tex
            job.step = "LaTeX Generated"
            job.status = JobStatus.DONE
            job.progress_percentage = 60
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
        import shutil
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
                
                # Copy the PDF to tempdir or artifact store for serving
                try:
                    final_pdf_path = artifact_store.put(job.job_id, "document.pdf", pdf_path)
                    job.pdf_path = final_pdf_path
                except Exception:
                    final_pdf_path = os.path.join(tempfile.gettempdir(), f"{job.job_id}.pdf")
                    if os.path.exists(pdf_path):
                        shutil.copy2(pdf_path, final_pdf_path)
                        job.pdf_path = final_pdf_path
                
                job.status = JobStatus.DONE
                job.progress_percentage = 100
                print(f"[{job.job_id}] PDF compiled successfully: {job.pdf_path}")
        except Exception as e:
            print(f"[{job.job_id}] Compilation process notice: {e}")
            job.status = JobStatus.DONE
            job.progress_percentage = 100
        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

        return job
