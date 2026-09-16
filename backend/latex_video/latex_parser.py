"""
Semantic LaTeX Parser for Educational Content.

Parses LaTeX documents into a structured LessonDocument IR without relying
on fragile monolithic regular expressions. Identifies sections, subsections,
paragraphs, standalone equations, multi-step algebraic derivations (align*),
itemized/enumerated lists, tables, and boxed highlights.
"""

from __future__ import annotations
import re
from typing import List, Tuple, Optional
from .document_model import (
    ElementType,
    ImportanceLevel,
    DocumentElement,
    LessonSection,
    LessonDocument,
)


class LatexSemanticParser:
    """Parses educational LaTeX into the LessonDocument intermediate representation."""

    def __init__(self):
        self._elem_counter = 0

    def parse(self, latex_content: str, fallback_title: str = "Lesson") -> LessonDocument:
        """Parse raw LaTeX string into a structured LessonDocument."""
        self._elem_counter = 0
        raw_title = self._extract_title(latex_content)
        cleaned = self._clean_source(latex_content)
        title = raw_title or self._extract_title(cleaned)
        if not title or title.lower() in ("introduction", "overview", "lesson", "notes"):
            if fallback_title and fallback_title.lower() != "lesson":
                title = fallback_title
            elif not title:
                title = "Lesson"

        doc = LessonDocument(title=title, raw_source=latex_content)
        
        # Split into conceptual sections by \section markers
        section_chunks = self._split_into_sections(cleaned)
        
        if not section_chunks:
            # Document has no explicit \section, treat as one default section
            default_sec = LessonSection(section_id="sec_0", title=title)
            default_sec.elements = self._parse_section_content(cleaned)
            if default_sec.elements:
                doc.sections.append(default_sec)
        else:
            for idx, (sec_title, sec_body) in enumerate(section_chunks):
                sec_id = f"sec_{idx}"
                section = LessonSection(section_id=sec_id, title=sec_title)
                
                # First element is the section heading itself
                sec_elem = self._create_element(
                    elem_type=ElementType.SECTION,
                    raw_content=sec_title,
                    clean_text=sec_title,
                    importance=ImportanceLevel.HIGH
                )
                section.elements.append(sec_elem)
                
                # Parse child elements within the section
                child_elements = self._parse_section_content(sec_body)
                section.elements.extend(child_elements)
                doc.sections.append(section)

        # If document has a title element and first section starts with a section heading,
        # ensure doc title is represented
        if doc.sections and title != "Lesson":
            first_sec = doc.sections[0]
            if not any(e.type == ElementType.TITLE for e in first_sec.elements):
                title_elem = self._create_element(
                    elem_type=ElementType.TITLE,
                    raw_content=title,
                    clean_text=title,
                    importance=ImportanceLevel.HIGH
                )
                first_sec.elements.insert(0, title_elem)

        return doc

    def _next_id(self, prefix: str = "el") -> str:
        self._elem_counter += 1
        return f"{prefix}_{self._elem_counter:03d}"

    def _clean_source(self, text: str) -> str:
        """Strip preamble, document environment tags, comments, and markdown fences."""
        # Strip markdown fences
        text = re.sub(r"^```(?:latex|tex)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
        
        # Strip <think>...</think> if model output reasoning tokens
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        
        # Strip Beamer frame tags and convert frametitle to subsection
        text = re.sub(r"\\frametitle\{([^}]+)\}", r"\\subsection*{\1}", text)
        text = re.sub(r"\\begin\{frame\}(?:\[[^\]]*\])?(?:\{[^}]*\})?", "", text)
        text = re.sub(r"\\end\{frame\}", "", text)

        # Normalize $$...$$ display math to \[...\]
        text = re.sub(r"\$\$(.*?)\$\$", r"\[\1\]", text, flags=re.DOTALL)

        # Normalize inline math \(...\) to $...$
        text = text.replace(r"\(", "$").replace(r"\)", "$")

        # Extract content between \begin{document} and \end{document} if present
        doc_match = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", text, flags=re.DOTALL)
        if doc_match:
            text = doc_match.group(1)
        else:
            # Strip \documentclass and \usepackage lines
            text = re.sub(r"\\documentclass(?:\[[^\]]*\])?\{[^}]*\}", "", text)
            text = re.sub(r"\\usepackage(?:\[[^\]]*\])?\{[^}]*\}", "", text)

        # Remove single-line LaTeX comments (but preserve escaped \%)
        cleaned_lines = []
        for line in text.splitlines():
            # Check for % not preceded by backslash
            m = re.search(r"(?<!\\)%.*", line)
            if m:
                line = line[:m.start()]
            cleaned_lines.append(line)
        
        raw_cleaned = "\n".join(cleaned_lines).strip()

        # Flatten nested itemize/enumerate lists so sub-items become flat bullet points
        # This prevents environment mismatch and nesting limit crashes in progressive slides
        for env in ("itemize", "enumerate"):
            nest_pattern = re.compile(
                r"(\\begin\{" + env + r"\}[^\\].*?)"
                r"\\begin\{" + env + r"\}(.*?)"
                r"\\end\{" + env + r"\}(.*?\\end\{" + env + r"\})",
                re.DOTALL
            )
            for _ in range(4):
                if not nest_pattern.search(raw_cleaned):
                    break
                raw_cleaned = nest_pattern.sub(r"\1\2\3", raw_cleaned)

        return self._sanitize_latex(raw_cleaned)

    def _sanitize_latex(self, content: str) -> str:
        """Sanitizes unicode, stray markdown, unescaped underscores and ampersands."""
        unicode_replacements = {
            '\u2010': '-', '\u2011': '-', '\u2012': '-', '\u2013': '--',
            '\u2014': '---', '\u2015': '---', '\u2212': '-', '\u00a0': ' ',
            '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"',
            '\u2026': r'\dots{}', '\u2264': r'\le ', '\u2265': r'\ge ',
            '\u00d7': r'\times ', '\u00f7': r'\div ', '\u00b1': r'\pm ',
            '→': r'\rightarrow ', '←': r'\leftarrow ', '⇒': r'\Rightarrow ',
            '°': r'^\circ ',
        }
        for u_char, rep in unicode_replacements.items():
            content = content.replace(u_char, rep)

        # Normalize $$...$$ display math to \[...\]
        content = re.sub(r"\$\$(.*?)\$\$", r"\[\1\]", content, flags=re.DOTALL)

        # Normalize inline math \(...\) to $...$
        content = content.replace(r"\(", "$").replace(r"\)", "$")

        # Clean empty inline math ($$ or $ $)
        content = re.sub(r"\$\s*\$", "", content)

        # Sanitize stray markdown headings
        content = re.sub(r'^###\s+(.*)$', r'\\subsubsection*{\1}', content, flags=re.MULTILINE)
        content = re.sub(r'^##\s+(.*)$', r'\\subsection*{\1}', content, flags=re.MULTILINE)
        content = re.sub(r'^#\s+(.*)$', r'\\section*{\1}', content, flags=re.MULTILINE)

        # Replace unescaped hash symbols outside math
        content = re.sub(r'(?<!\\)#', r'\\#', content)

        # Fix erroneous escaped ampersands
        content = re.sub(r'\\&\s*=', '&=', content)
        content = re.sub(r'([a-zA-Z0-9\)])\s*\\&\s*=', r'\1 &=', content)

        # In lines outside math, escape bare underscores, ampersands, and wrap stray math symbols
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

        math_cmd_regex = re.compile(
            r'\\(rightarrow|leftarrow|Rightarrow|Leftarrow|leftrightarrow|times|div|pm|le|ge|neq|approx|cdot|sim|forall|exists|in|notin|subset|subseteq|cup|cap)(?![a-zA-Z])'
        )

        for line in lines:
            stripped = line.strip()
            if math_begin_pattern.search(stripped) or r"\[" in stripped or "$$" in stripped:
                in_math_env = True

            if in_math_env:
                line = line.replace(r'\&=', '&=').replace(r'\&', '&')
            else:
                parts = line.split('$')
                for i in range(0, len(parts), 2):
                    chunk = parts[i]
                    # Wrap standalone math symbol commands in math mode
                    chunk = math_cmd_regex.sub(lambda m: f"${m.group(0)}$", chunk)
                    # Escape bare ampersands
                    chunk = re.sub(r'(?<!\\)&', r'\\&', chunk)
                    # Escape bare underscores outside math
                    chunk = re.sub(r'(?<!\\)_', r'\_', chunk)
                    parts[i] = chunk
                line = '$'.join(parts)

            if math_end_pattern.search(stripped) or r"\]" in stripped or "$$" in stripped:
                in_math_env = False
            sanitized.append(line)

        return '\n'.join(sanitized).strip()

    def _extract_title(self, text: str) -> Optional[str]:
        m = re.search(r"\\title\{([^}]+)\}", text)
        if m:
            return m.group(1).strip()
        # Alternatively check for \section*{...} as first heading
        first_sec = re.search(r"\\section\*?\{([^}]+)\}", text)
        if first_sec:
            return first_sec.group(1).strip()
        return None

    def _split_into_sections(self, text: str) -> List[Tuple[str, str]]:
        """Splits document body into tuples of (section_title, section_body)."""
        pattern = re.compile(r"\\section\*?\{([^}]+)\}")
        matches = list(pattern.finditer(text))
        if not matches:
            return []

        sections: List[Tuple[str, str]] = []
        
        # Content before first section
        prefix = text[:matches[0].start()].strip()
        if prefix:
            sections.append(("Introduction", prefix))

        for i, match in enumerate(matches):
            title = match.group(1).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            sections.append((title, body))

        return sections

    def _parse_section_content(self, text: str) -> List[DocumentElement]:
        """Parses elements inside a section body."""
        elements: List[DocumentElement] = []
        
        # Tokenize into blocks: subsections, subsubsections, environments, display math, and paragraphs
        tokens = self._tokenize_blocks(text)
        
        for token_type, content in tokens:
            content = content.strip()
            if not content:
                continue

            if token_type == "subsection":
                elements.append(self._create_element(
                    elem_type=ElementType.SUBSECTION,
                    raw_content=content,
                    clean_text=content,
                    importance=ImportanceLevel.MEDIUM
                ))
            elif token_type == "subsubsection":
                elements.append(self._create_element(
                    elem_type=ElementType.SUBSUBSECTION,
                    raw_content=content,
                    clean_text=content,
                    importance=ImportanceLevel.NORMAL
                ))
            elif token_type == "align_env":
                # Multi-line derivation: break into individual algebraic steps!
                step_elements = self._parse_align_steps(content)
                elements.extend(step_elements)
            elif token_type == "equation":
                # Standalone display equation
                is_boxed = "\\boxed" in content
                elem = self._create_element(
                    elem_type=ElementType.BOXED_RESULT if is_boxed else ElementType.EQUATION_DISPLAY,
                    raw_content=content,
                    clean_text=self._clean_latex_math(content),
                    importance=ImportanceLevel.HIGH if is_boxed else ImportanceLevel.MEDIUM,
                    is_boxed=is_boxed
                )
                elements.append(elem)
            elif token_type == "itemize":
                items = self._parse_list_items(content)
                for item in items:
                    elements.append(self._create_element(
                        elem_type=ElementType.BULLET_ITEM,
                        raw_content=item,
                        clean_text=self._strip_latex_formatting(item),
                        importance=ImportanceLevel.NORMAL
                    ))
            elif token_type == "enumerate":
                items = self._parse_list_items(content)
                for item in items:
                    elements.append(self._create_element(
                        elem_type=ElementType.NUMBERED_ITEM,
                        raw_content=item,
                        clean_text=self._strip_latex_formatting(item),
                        importance=ImportanceLevel.NORMAL
                    ))
            elif token_type == "tabular":
                elements.append(self._create_element(
                    elem_type=ElementType.TABLE,
                    raw_content=content,
                    clean_text="Table",
                    importance=ImportanceLevel.NORMAL
                ))
            elif token_type == "paragraph":
                # Check if paragraph is actually a boxed result or formula
                if "\\boxed" in content and ("=" in content or "\\" in content):
                    elements.append(self._create_element(
                        elem_type=ElementType.BOXED_RESULT,
                        raw_content=content,
                        clean_text=self._clean_latex_math(content),
                        importance=ImportanceLevel.HIGH,
                        is_boxed=True
                    ))
                else:
                    elements.append(self._create_element(
                        elem_type=ElementType.PARAGRAPH,
                        raw_content=content,
                        clean_text=self._strip_latex_formatting(content),
                        importance=ImportanceLevel.NORMAL
                    ))

        return elements

    def _tokenize_blocks(self, text: str) -> List[Tuple[str, str]]:
        """Scans text and returns classified chunks in sequential appearance order."""
        tokens: List[Tuple[str, str]] = []
        
        # Regex patterns for high-level block structures
        env_pattern = re.compile(
            r"(\\subsection\*?\{[^}]+\})|"
            r"(\\subsubsection\*?\{[^}]+\})|"
            r"(\\begin\{(align\*?|aligned|gather\*?|multline\*?)\}.*?\\end\{\4\})|"
            r"(\\begin\{equation\*?\}.*?\\end\{equation\*?\})|"
            r"(\\\[.*?\\\])|"
            r"(\$\$.*?\$\$)|"
            r"(\\begin\{itemize\}.*?\\end\{itemize\})|"
            r"(\\begin\{enumerate\}.*?\\end\{enumerate\})|"
            r"(\\begin\{tabular\}.*?\\end\{tabular\})",
            re.DOTALL
        )

        pos = 0
        for m in env_pattern.finditer(text):
            start, end = m.span()
            # Everything before this block is plain paragraphs
            if start > pos:
                para_block = text[pos:start].strip()
                for p in self._split_paragraphs(para_block):
                    tokens.append(("paragraph", p))

            matched_str = m.group(0)
            if m.group(1):
                # Subsection
                title = re.search(r"\\subsection\*?\{([^}]+)\}", matched_str).group(1)
                tokens.append(("subsection", title))
            elif m.group(2):
                # Subsubsection
                title = re.search(r"\\subsubsection\*?\{([^}]+)\}", matched_str).group(1)
                tokens.append(("subsubsection", title))
            elif m.group(3):
                # Align / multi-line math environment
                inner = re.sub(r"^\\begin\{[a-zA-Z0-9\*]+\}\s*", "", matched_str)
                inner = re.sub(r"\\end\{[a-zA-Z0-9\*]+\}\s*$", "", inner)
                tokens.append(("align_env", inner.strip()))
            elif m.group(5):
                # Single equation
                inner = re.sub(r"^\\begin\{equation\*?\}\s*", "", matched_str)
                inner = re.sub(r"\\end\{equation\*?\}\s*$", "", inner)
                tokens.append(("equation", inner.strip()))
            elif m.group(6):
                # \[ ... \]
                inner = matched_str[2:-2].strip()
                tokens.append(("equation", inner))
            elif m.group(7):
                # $$ ... $$
                inner = matched_str[2:-2].strip()
                tokens.append(("equation", inner))
            elif m.group(8):
                # Itemize
                inner = re.sub(r"^\\begin\{itemize\}\s*", "", matched_str)
                inner = re.sub(r"\\end\{itemize\}\s*$", "", inner)
                tokens.append(("itemize", inner.strip()))
            elif m.group(9):
                # Enumerate
                inner = re.sub(r"^\\begin\{enumerate\}\s*", "", matched_str)
                inner = re.sub(r"\\end\{enumerate\}\s*$", "", inner)
                tokens.append(("enumerate", inner.strip()))
            elif m.group(10):
                # Tabular
                tokens.append(("tabular", matched_str))

            pos = end

        # Trailing paragraphs after last environment
        if pos < len(text):
            trailing = text[pos:].strip()
            for p in self._split_paragraphs(trailing):
                tokens.append(("paragraph", p))

        return tokens

    def _split_paragraphs(self, text: str) -> List[str]:
        """Splits raw text block into discrete paragraphs by blank lines."""
        chunks = []
        for c in re.split(r"\n\s*\n", text):
            c = c.strip()
            # Remove stray environment opening or closing tags that may have leaked
            c = re.sub(r"^\\end\{(?:itemize|enumerate|align\*?|equation\*?)\}\s*", "", c)
            c = re.sub(r"\\end\{(?:itemize|enumerate|align\*?|equation\*?)\}\s*$", "", c)
            c = re.sub(r"^\\begin\{(?:itemize|enumerate)\}\s*", "", c)
            c = c.strip()
            if c:
                chunks.append(c)
        return chunks

    def _parse_align_steps(self, align_content: str) -> List[DocumentElement]:
        """Splits multi-line align equations by \\ into sequential derivation steps."""
        raw_lines = re.split(r"\\\\(?:\s*\[[^\]]*\])?", align_content)
        lines = []
        for l in raw_lines:
            # Strip any leading bracketed spacing like [4pt] or [0.5em]
            l = re.sub(r"^\s*\[[^\]]*\]\s*", "", l).strip()
            if l:
                lines.append(l)

        group_id = self._next_id("grp_align")
        step_elements: List[DocumentElement] = []

        for idx, line in enumerate(lines):
            is_boxed = "\\boxed" in line or "\\fbox" in line
            is_last = (idx == len(lines) - 1)
            importance = ImportanceLevel.HIGH if (is_boxed or is_last) else ImportanceLevel.NORMAL

            elem = self._create_element(
                elem_type=ElementType.BOXED_RESULT if is_boxed else ElementType.EQUATION_STEP,
                raw_content=line,
                clean_text=self._clean_latex_math(line),
                importance=importance,
                is_boxed=is_boxed
            )
            elem.group_id = group_id
            elem.align_env = True
            step_elements.append(elem)

        return step_elements

    def _parse_list_items(self, list_content: str) -> List[str]:
        """Extracts individual items from an itemize or enumerate block."""
        parts = re.split(r"\\item\s+", list_content)
        items = []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            # Strip any internal or nested list environment markers
            p = re.sub(r"\\begin\{(?:itemize|enumerate)\}", "", p)
            p = re.sub(r"\\end\{(?:itemize|enumerate)\}", "", p)
            p = p.strip()
            if p:
                items.append(p)
        return items

    def _create_element(
        self,
        elem_type: ElementType,
        raw_content: str,
        clean_text: str,
        importance: ImportanceLevel = ImportanceLevel.NORMAL,
        is_boxed: bool = False
    ) -> DocumentElement:
        complexity = self._calculate_complexity(elem_type, raw_content, clean_text)
        return DocumentElement(
            element_id=self._next_id("elem"),
            type=elem_type,
            raw_content=raw_content,
            clean_text=clean_text,
            importance=importance,
            complexity_score=complexity,
            is_boxed=is_boxed
        )

    def _calculate_complexity(self, elem_type: ElementType, raw: str, clean: str) -> float:
        """Calculates cognitive reading complexity to scale animation timing."""
        if elem_type in (ElementType.TITLE, ElementType.SECTION, ElementType.SUBSECTION):
            return 1.0
        
        if elem_type in (ElementType.EQUATION_DISPLAY, ElementType.EQUATION_STEP, ElementType.BOXED_RESULT):
            # Math complexity: count symbols like fractions, integrals, powers, subscripts
            math_indicators = [
                r"\\frac", r"\\int", r"\\sum", r"\\prod", r"\\lim", r"\\sqrt",
                r"\^", r"_", r"\\partial", r"\\nabla", r"\\alpha", r"\\beta",
                r"\\gamma", r"\\theta", r"\\lambda", r"\\sigma", r"\\omega"
            ]
            score = 1.5
            for ind in math_indicators:
                score += 0.3 * len(re.findall(ind, raw))
            return min(score, 5.0)

        # Paragraph or list item: based on word count
        words = len(clean.split())
        return max(1.0, words / 15.0)

    def _strip_latex_formatting(self, text: str) -> str:
        """Removes LaTeX formatting commands to produce readable clean text."""
        # Replace \textbf{...}, \textit{...}, \emph{...} with inner text
        text = re.sub(r"\\[a-zA-Z]+\{([^}]+)\}", r"\1", text)
        # Remove standalone commands
        text = re.sub(r"\\[a-zA-Z]+", "", text)
        # Clean inline math delimiters
        text = text.replace("$", "")
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _clean_latex_math(self, text: str) -> str:
        """Clean display math for text readability."""
        clean = text.replace("&=", "=").replace("&", "")
        clean = re.sub(r"\\boxed\{([^}]+)\}", r"\1", clean)
        clean = re.sub(r"\\(mathbf|text|mathrm)\{([^}]+)\}", r"\2", clean)
        return clean.strip()
