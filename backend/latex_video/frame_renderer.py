"""
LaTeX Slide Frame Renderer.

Compiles progressive document states into high-resolution (1920x1080) 16:9
presentation slides using Tectonic and rasterizes them via PyQt6.QtPdf (QPdfDocument).
Computes smooth, flicker-free inter-state transitions (alpha reveal, subtle slide,
boxed equation highlighting).
"""

from __future__ import annotations
import os
import sys
import re
import tempfile
import subprocess
from typing import List, Dict, Tuple, Optional
from PIL import Image, ImageOps

# PyQt6 is imported lazily inside methods so this module can be imported
# in environments where PyQt6 is not installed (e.g. unit-test runners).

from .document_model import (
    ElementType,
    TransitionType,
    DocumentElement,
    LessonDocument,
)
from .animation_planner import AnimationTimeline, TimelineState, SlideScene


class LatexFrameRenderer:
    """Renders progressive document states into 1080p video frames."""

    def __init__(self, width: int = 1920, height: int = 1080, fps: int = 30):
        self.width = width
        self.height = height
        self.fps = fps
        self._ensure_qapp()

    def _ensure_qapp(self):
        """Ensures a QCoreApplication / QApplication instance exists for QPdfDocument."""
        from PyQt6.QtWidgets import QApplication  # lazy import
        if QApplication.instance() is None:
            # Headless Qt application
            self._qapp = QApplication(sys.argv[:1] + ["-platform", "offscreen"])
        else:
            self._qapp = QApplication.instance()

    def render_state_images(self, timeline: AnimationTimeline) -> List[Image.Image]:
        """
        Compiles all progressive states in the timeline into a single multi-page
        presentation PDF via Tectonic, then rasterizes each page to a 1920x1080 PIL Image.
        """
        latex_source = self._generate_presentation_latex(timeline)
        pdf_path = self._compile_presentation_pdf(latex_source)
        
        if not pdf_path or not os.path.exists(pdf_path):
            raise RuntimeError("LaTeX compilation failed to produce a presentation PDF.")

        # Rasterize all pages with QPdfDocument (lazy Qt imports)
        from PyQt6.QtPdf import QPdfDocument
        from PyQt6.QtCore import QSize

        state_images: List[Image.Image] = []
        doc = QPdfDocument(None)
        doc.load(pdf_path)
        page_count = doc.pageCount()

        target_size = QSize(self.width, self.height)
        for page_idx in range(min(len(timeline.states), page_count)):
            qimg = doc.render(page_idx, target_size)
            pil_img = self._qimage_to_pil(qimg)
            state_images.append(pil_img)

        # In case page count is smaller than states count (fallback padding)
        while len(state_images) < len(timeline.states):
            state_images.append(state_images[-1] if state_images else Image.new("RGB", (self.width, self.height), (255, 255, 255)))

        return state_images

    def _generate_presentation_latex(self, timeline: AnimationTimeline) -> str:
        """
        Generates a 16:9 presentation document where each progressive state
        occupies exactly one page, separated by \\newpage.
        """
        pages_latex: List[str] = []

        for state in timeline.states:
            page_content = self._render_elements_to_latex(state.visible_elements)
            pages_latex.append(page_content)

        body = "\n\\newpage\n".join(pages_latex)
        # Pre-sanitize combined body before inserting into template
        body = self._sanitize_body_for_compile(body)

        template = r"""\documentclass[17pt]{extarticle}
\usepackage[papersize={16in,9in},margin=1.2in]{geometry}
\usepackage{amsmath,amssymb,amsthm,mathtools}
\usepackage{xcolor}
\pagestyle{empty}

% Clean monochrome color palette
\definecolor{textColor}{RGB}{28, 28, 30}
\definecolor{accentBlue}{RGB}{0, 113, 227}
\definecolor{boxBg}{RGB}{245, 245, 247}

\color{textColor}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.6em}

\begin{document}
""" + body + r"""
\end{document}
"""
        return template

    def _render_elements_to_latex(self, elements: List[DocumentElement]) -> str:
        """Converts a group of visible elements on a slide into coherent LaTeX markup."""
        output_lines: List[str] = []
        in_align = False
        align_buffer: List[str] = []
        in_itemize = False
        itemize_buffer: List[str] = []
        in_enumerate = False
        enumerate_buffer: List[str] = []

        def flush_align():
            nonlocal in_align, align_buffer
            if in_align:
                clean_rows = []
                for row in align_buffer:
                    r = re.sub(r"\\\\(?:\s*\[[^\]]*\])?\s*$", "", row.strip())
                    r = re.sub(r"^\s*\[[^\]]*\]\s*", "", r)
                    r = re.sub(r"(?<!\\)\$", "", r)
                    r = r.replace(r"\par", " ").strip()
                    if r:
                        clean_rows.append(r)
                if clean_rows:
                    joined = " \\\\\n".join(clean_rows)
                    output_lines.append(f"\\begin{{align*}}\n{joined}\n\\end{{align*}}\n")
                align_buffer = []
                in_align = False

        def flush_itemize():
            nonlocal in_itemize, itemize_buffer
            if in_itemize:
                clean_items = []
                for it in itemize_buffer:
                    if not it:
                        continue
                    # Strip any nested environment tags that would break list environment balance
                    c = re.sub(r"\\begin\{(?:itemize|enumerate)\}", "", it)
                    c = re.sub(r"\\end\{(?:itemize|enumerate)\}", "", c).strip()
                    if c:
                        clean_items.append(c)
                if clean_items:
                    joined = "\n".join(f"\\item {it}" for it in clean_items)
                    output_lines.append(f"\\begin{{itemize}}\n{joined}\n\\end{{itemize}}\n")
                itemize_buffer = []
                in_itemize = False

        def flush_enumerate():
            nonlocal in_enumerate, enumerate_buffer
            if in_enumerate:
                clean_items = []
                for it in enumerate_buffer:
                    if not it:
                        continue
                    c = re.sub(r"\\begin\{(?:itemize|enumerate)\}", "", it)
                    c = re.sub(r"\\end\{(?:itemize|enumerate)\}", "", c).strip()
                    if c:
                        clean_items.append(c)
                if clean_items:
                    joined = "\n".join(f"\\item {it}" for it in clean_items)
                    output_lines.append(f"\\begin{{enumerate}}\n{joined}\n\\end{{enumerate}}\n")
                enumerate_buffer = []
                in_enumerate = False

        for elem in elements:
            # Handle list grouping
            if elem.type == ElementType.BULLET_ITEM:
                flush_align()
                flush_enumerate()
                in_itemize = True
                itemize_buffer.append(elem.raw_content)
                continue
            elif elem.type == ElementType.NUMBERED_ITEM:
                flush_align()
                flush_itemize()
                in_enumerate = True
                enumerate_buffer.append(elem.raw_content)
                continue
            else:
                flush_itemize()
                flush_enumerate()

            # Handle align environment grouping
            if elem.align_env or elem.type == ElementType.EQUATION_STEP:
                in_align = True
                align_buffer.append(elem.raw_content)
                continue
            else:
                flush_align()

            # Standalone elements
            if elem.type == ElementType.TITLE:
                output_lines.append(
                    f"{{\\color{{accentBlue}}\\Huge \\textbf{{{elem.raw_content}}}}}\n\\par\\vspace{{1.4em}}\n"
                )
            elif elem.type == ElementType.SECTION:
                output_lines.append(
                    f"{{\\color{{accentBlue}}\\LARGE \\textbf{{{elem.raw_content}}}}}\n\\par\\vspace{{1.0em}}\n"
                )
            elif elem.type == ElementType.SUBSECTION:
                output_lines.append(f"{{\\large \\textbf{{{elem.raw_content}}}}}\n\\par\\vspace{{0.6em}}\n")
            elif elem.type == ElementType.SUBSUBSECTION:
                output_lines.append(f"{{\\normalsize \\textbf{{{elem.raw_content}}}}}\n\\par\\vspace{{0.4em}}\n")
            elif elem.type == ElementType.PARAGRAPH:
                cleaned_p = re.sub(r"\\\\(?:\s*\[[^\]]*\])?\s*$", "", elem.raw_content.strip())
                output_lines.append(f"{cleaned_p}\n\\par\\vspace{{0.8em}}\n")
            elif elem.type == ElementType.EQUATION_DISPLAY:
                content = elem.raw_content.strip()
                # Strip unescaped $ that would break display math mode
                content = re.sub(r"(?<!\\)\$", "", content)
                if not content.startswith("\\[") and not content.startswith("\\begin"):
                    output_lines.append(f"\\[\n{content}\n\\]\n")
                else:
                    output_lines.append(f"{content}\n")
            elif elem.type == ElementType.BOXED_RESULT:
                content = elem.raw_content.strip()
                content = re.sub(r"(?<!\\)\$", "", content)
                # Render boxed results with clear visual accent — safe string formatting without syntax error
                if "\\boxed" in content:
                    output_lines.append(
                        "\\par\\vspace{0.4em}\n"
                        f"{{\\color{{accentBlue}}\\[\n{content}\n\\]}}\n"
                        "\\par\\vspace{0.4em}\n"
                    )
                else:
                    output_lines.append(
                        "\\par\\vspace{0.4em}\n"
                        f"{{\\color{{accentBlue}}\\[\n\\boxed{{{content}}}\n\\]}}\n"
                        "\\par\\vspace{0.4em}\n"
                    )
            elif elem.type == ElementType.TABLE:
                output_lines.append(f"{elem.raw_content}\n")
            else:
                output_lines.append(f"{elem.raw_content}\n")

        # Flush any open environments
        flush_align()
        flush_itemize()
        flush_enumerate()

        return "\n".join(output_lines)
    def _sanitize_body_for_compile(self, body: str) -> str:
        """
        Sanitizes and repairs the multi-page slide document body before compilation.
        Ensures each page (between \\newpage) has strictly balanced environments,
        no empty itemize/enumerate, and no illegal TeX control characters.
        """
        pages = body.split(r"\newpage")
        sanitized_pages = []

        for page in pages:
            p = page.strip()
            if not p:
                continue

            # Normalize \( and \) inline math delimiters to $
            # Note: \bigl( is not the same as \( so this is safe.
            p = p.replace(r"\(", "$").replace(r"\)", "$")

            # Remove unsupported external package environments
            p = re.sub(r"\\begin\{tcolorbox\}[^\n]*\n.*?\\end\{tcolorbox\}", "", p, flags=re.DOTALL)
            p = re.sub(r"\\begin\{(tikzpicture|minted|listings)\b.*?\\end\{\1\*?\}", "", p, flags=re.DOTALL)

            # ── FIX: bare ^ and _ inside \text{...} are illegal in XeTeX text mode.
            # Wrap them as inline math: y^{2} → y$^{2}$, x_{0} → x$_{0}$
            p = self._fix_superscripts_in_text(p)

            # Clean empty itemize or enumerate blocks
            p = re.sub(r"\\begin\{itemize\}\s*\\end\{itemize\}", "", p)
            p = re.sub(r"\\begin\{enumerate\}\s*\\end\{enumerate\}", "", p)

            # Ensure all \begin{itemize} have matching \end{itemize} on this page
            open_itemizes = len(re.findall(r"\\begin\{itemize\}", p))
            close_itemizes = len(re.findall(r"\\end\{itemize\}", p))
            if open_itemizes > close_itemizes:
                p += "\n" + ("\\end{itemize}\n" * (open_itemizes - close_itemizes))
            elif close_itemizes > open_itemizes:
                excess = close_itemizes - open_itemizes
                for _ in range(excess):
                    p = re.sub(r"\\end\{itemize\}\s*$", "", p)

            # Ensure all \begin{enumerate} have matching \end{enumerate} on this page
            open_enums = len(re.findall(r"\\begin\{enumerate\}", p))
            close_enums = len(re.findall(r"\\end\{enumerate\}", p))
            if open_enums > close_enums:
                p += "\n" + ("\\end{enumerate}\n" * (open_enums - close_enums))
            elif close_enums > open_enums:
                excess = close_enums - open_enums
                for _ in range(excess):
                    p = re.sub(r"\\end\{enumerate\}\s*$", "", p)

            # Ensure all \begin{align*} have matching \end{align*} on this page
            open_aligns = len(re.findall(r"\\begin\{align\*?\}", p))
            close_aligns = len(re.findall(r"\\end\{align\*?\}", p))
            if open_aligns > close_aligns:
                p += "\n" + ("\\end{align*}\n" * (open_aligns - close_aligns))

            # Remove any lonely \item not inside a list environment
            lines = p.splitlines()
            fixed_lines = []
            in_list = False
            for line in lines:
                s = line.strip()
                if r"\begin{itemize}" in s or r"\begin{enumerate}" in s:
                    in_list = True
                elif r"\end{itemize}" in s or r"\end{enumerate}" in s:
                    in_list = False
                elif s.startswith(r"\item") and not in_list:
                    line = f"\\begin{{itemize}}\n{line}\n\\end{{itemize}}"

                # Ensure individual \item lines don't leave unclosed inline math mode
                if s.startswith(r"\item"):
                    num_dollars = len(re.findall(r"(?<!\\)\$", line))
                    if num_dollars % 2 != 0:
                        line = line + "$"

                fixed_lines.append(line)
            p = "\n".join(fixed_lines)

            # Ensure list blocks don't leave math mode unclosed before \end{itemize} or \end{enumerate}
            def _balance_list_dollars(m):
                content = m.group(0)
                dollars = len(re.findall(r"(?<!\\)\$", content))
                if dollars % 2 != 0:
                    content = re.sub(r"(\\end\{(?:itemize|enumerate)\})", r"$\1", content, count=1)
                return content

            p = re.sub(r"\\begin\{(?:itemize|enumerate)\}.*?\\end\{(?:itemize|enumerate)\}", _balance_list_dollars, p, flags=re.DOTALL)

            # Strip unescaped dollar signs ONLY inside display math \[...\] blocks.
            # Use non-greedy match but stop at the nearest \] to avoid cross-block capture.
            def _strip_dollars_in_display(m):
                inner = m.group(1)
                cleaned = re.sub(r"(?<!\\)\$", "", inner)
                return "\\[" + cleaned + "\\]"

            p = re.sub(r"\\\[(.*?)\\\]", _strip_dollars_in_display, p, flags=re.DOTALL)

            # Clean any empty itemize left over
            p = re.sub(r"\\begin\{itemize\}\s*\\end\{itemize\}", "", p)
            p = re.sub(r"\\begin\{enumerate\}\s*\\end\{enumerate\}", "", p)

            sanitized_pages.append(p)

        return "\n\n\\newpage\n\n".join(sanitized_pages)

    @staticmethod
    def _fix_superscripts_in_text(latex: str) -> str:
        """
        Fix bare ^ and _ inside \\text{...} commands which are illegal in
        XeTeX text mode.  Converts e.g. \\text{y^{2}} → \\text{y$^{2}$}.

        This handles the common LLM pattern of writing math notation inside
        \\text{} annotation comments in align* environments without wrapping
        the superscript/subscript in inline math delimiters.
        """
        def _fix_text_block(m: re.Match) -> str:
            content = m.group(1)
            # Wrap bare ^ and _ (that aren't already inside $...$) with $ $
            # Step 1: find positions already inside inline math and protect them
            protected = []
            result = []
            i = 0
            in_math = False
            while i < len(content):
                if content[i] == '$' and (i == 0 or content[i-1] != '\\'):
                    in_math = not in_math
                    result.append(content[i])
                elif not in_math and content[i] in ('^', '_'):
                    # Capture the argument: either {grouped} or single char
                    j = i + 1
                    if j < len(content) and content[j] == '{':
                        # Find closing }
                        depth = 0
                        k = j
                        while k < len(content):
                            if content[k] == '{':
                                depth += 1
                            elif content[k] == '}':
                                depth -= 1
                                if depth == 0:
                                    break
                            k += 1
                        arg = content[j:k+1]
                        result.append(f"${content[i]}{arg}$")
                        i = k + 1
                        continue
                    elif j < len(content):
                        result.append(f"${content[i]}{content[j]}$")
                        i = j + 1
                        continue
                    else:
                        result.append(content[i])
                else:
                    result.append(content[i])
                i += 1
            return r"\text{" + "".join(result) + "}"

        # Match \text{ ... } — handle nested braces up to depth 3
        return re.sub(r"\\text\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", _fix_text_block, latex)



    def _compile_presentation_pdf(self, latex_code: str) -> Optional[str]:
        """Runs local tectonic.exe to compile LaTeX presentation into PDF.
        
        Uses a 3-tier fallback strategy:
        1. Full extarticle template
        2. Standard article class at 12pt (if extarticle fails)
        3. Bare-minimum document (if all complex math/formatting fails)
        """
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        local_tectonic = os.path.join(project_root, "tectonic.exe")
        tectonic_cmd = local_tectonic if os.path.exists(local_tectonic) else "tectonic"

        temp_dir = tempfile.mkdtemp(prefix="kestrel_slide_")

        # --- Tier 1: Full extarticle template ---
        tex_path = os.path.join(temp_dir, "presentation.tex")
        pdf_path = os.path.join(temp_dir, "presentation.pdf")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_code)

        result = self._run_tectonic(tectonic_cmd, tex_path, temp_dir)
        if result and os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            print(f"[FrameRenderer] Tier-1 compilation succeeded ({os.path.getsize(pdf_path)} bytes).")
            return pdf_path

        # --- Tier 2: Standard article class fallback ---
        print(f"[FrameRenderer] Tier-1 failed. Trying Tier-2 (standard article class)...")
        fallback2_code = latex_code.replace(
            r"\documentclass[17pt]{extarticle}",
            r"\documentclass[12pt]{article}"
        )
        tex2 = os.path.join(temp_dir, "fallback2.tex")
        pdf2 = os.path.join(temp_dir, "fallback2.pdf")
        with open(tex2, "w", encoding="utf-8") as f:
            f.write(fallback2_code)
        result2 = self._run_tectonic(tectonic_cmd, tex2, temp_dir)
        if result2 and os.path.exists(pdf2) and os.path.getsize(pdf2) > 0:
            print(f"[FrameRenderer] Tier-2 compilation succeeded.")
            return pdf2

        # --- Tier 3: Bare minimal document (escape hatch) ---
        print(f"[FrameRenderer] Tier-2 failed. Falling back to Tier-3 bare minimal document.")
        bare_body = self._extract_text_only_body(latex_code)
        bare_code = (
            r"\documentclass[12pt]{article}" + "\n"
            r"\usepackage[papersize={16in,9in},margin=1.2in]{geometry}" + "\n"
            r"\usepackage{amsmath,amssymb,xcolor}" + "\n"
            r"\pagestyle{empty}" + "\n"
            r"\definecolor{accentBlue}{RGB}{0,113,227}" + "\n"
            r"\setlength{\parindent}{0pt}" + "\n"
            r"\begin{document}" + "\n"
            + bare_body + "\n"
            r"\end{document}" + "\n"
        )
        tex3 = os.path.join(temp_dir, "bare.tex")
        pdf3 = os.path.join(temp_dir, "bare.pdf")
        with open(tex3, "w", encoding="utf-8") as f:
            f.write(bare_code)
        result3 = self._run_tectonic(tectonic_cmd, tex3, temp_dir)
        if result3 and os.path.exists(pdf3) and os.path.getsize(pdf3) > 0:
            print(f"[FrameRenderer] Tier-3 bare compilation succeeded.")
            return pdf3

        print(f"[FrameRenderer] All 3 compilation tiers failed for temp_dir={temp_dir}")
        return None

    def _run_tectonic(self, tectonic_cmd: str, tex_path: str, cwd: str) -> bool:
        """Run tectonic and return True if PDF was produced successfully."""
        pdf_path = tex_path.replace(".tex", ".pdf")
        try:
            res = subprocess.run(
                [tectonic_cmd, tex_path],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=90,
                encoding='utf-8',
                errors='replace'
            )
            # If returncode is 0 and PDF exists and is non-empty, compilation SUCCEEDED.
            if res.returncode == 0 and os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                return True

            # Otherwise, compilation failed. Log detailed error info.
            combined = (res.stdout or "") + "\n" + (res.stderr or "")
            error_lines = [
                l for l in combined.splitlines()
                if l.strip() and "Fontconfig error" not in l and "Cannot load default config" not in l
            ]
            print(f"[FrameRenderer] Tectonic compile failed (exit code {res.returncode}):")
            for l in error_lines[:25]:
                print(f"  {l}")

            # Save debug tex
            debug_path = tex_path.replace(".tex", "_debug.tex")
            try:
                import shutil
                shutil.copy2(tex_path, debug_path)
            except Exception:
                pass

            return False
        except subprocess.TimeoutExpired:
            print(f"[FrameRenderer] Tectonic timed out after 90s for {tex_path}")
            return False
        except Exception as e:
            print(f"[FrameRenderer] Tectonic execution exception: {e}")
            return False

    def _extract_text_only_body(self, latex_code: str) -> str:
        """Extracts a safe, stripped-down version of body content for the bare fallback."""
        import re as _re
        # Get content between \begin{document} and \end{document}
        m = _re.search(r'\\begin\{document\}(.*?)\\end\{document\}', latex_code, flags=_re.DOTALL)
        body = m.group(1) if m else latex_code

        # Keep only safe structural elements and plain math
        # Remove tcolorbox, custom environments that need extra packages
        body = _re.sub(r'\\begin\{tcolorbox\}[^\n]*\n.*?\\end\{tcolorbox\}', '', body, flags=_re.DOTALL)
        body = _re.sub(r'\\begin\{(tikz|pgf|listings|minted|verbatim)\b.*?\\end\{\1\*?\}', '', body, flags=_re.DOTALL)

        # Strip font size commands that require extarticle
        body = body.replace(r'\Huge', r'\LARGE').replace(r'\huge', r'\Large')

        return body.strip()

    def _qimage_to_pil(self, qimg) -> Image.Image:
        """Converts QImage to PIL RGB Image without disk I/O."""
        from PyQt6.QtGui import QImage  # lazy import
        # Convert to standard 32-bit ARGB first, then composite on white to handle any transparency
        argb_img = qimg.convertToFormat(QImage.Format.Format_ARGB32)
        width = argb_img.width()
        height = argb_img.height()
        ptr = argb_img.bits()
        ptr.setsize(height * argb_img.bytesPerLine())

        # ARGB32 raw bytes → PIL RGBA (Qt uses BGRA byte order on little-endian)
        raw_bytes = bytes(ptr)
        rgba_img = Image.frombytes("RGBA", (width, height), raw_bytes, "raw", "BGRA", argb_img.bytesPerLine(), 1)

        # Composite RGBA onto a solid white background to flatten transparency correctly
        white_bg = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        composited = Image.alpha_composite(white_bg, rgba_img)
        return composited.convert("RGB")

    def generate_transition_frames(
        self,
        prev_img: Image.Image,
        curr_img: Image.Image,
        transition_type: TransitionType,
        num_frames: int
    ) -> List[Image.Image]:
        """
        Generates inter-state animation frames.
        Because existing elements have identical coordinates between prev_img and curr_img,
        linear blending keeps existing elements 100% solid and flicker-free, while
        the new element smoothly reveals.
        """
        if num_frames <= 1:
            return [curr_img]

        frames: List[Image.Image] = []
        for i in range(num_frames):
            alpha = (i + 1) / float(num_frames)
            
            # Smooth ease-in-out curve
            eased_alpha = 0.5 - 0.5 * (1.0 - alpha * 2.0 if alpha < 0.5 else alpha * 2.0 - 1.0)
            eased_alpha = max(0.0, min(1.0, alpha * alpha * (3.0 - 2.0 * alpha)))

            # Linear blend: (1 - alpha) * prev + alpha * curr
            blended = Image.blend(prev_img, curr_img, eased_alpha)
            frames.append(blended)

        return frames
