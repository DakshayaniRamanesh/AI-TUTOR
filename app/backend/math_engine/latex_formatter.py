r"""
LaTeX to PDF-Level Clean HTML Document Formatter
Parses raw LaTeX document source code into a syntax-free, PDF-styled HTML page.
Strips all LaTeX preambles, commands, escapes, and converts math/structure into clean typography.
"""

import re

GREEK_AND_SYMBOLS = {
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
    r"\epsilon": "ε", r"\varepsilon": "ε", r"\zeta": "ζ", r"\eta": "η",
    r"\theta": "θ", r"\iota": "ι", r"\kappa": "κ", r"\lambda": "λ",
    r"\mu": "μ", r"\nu": "ν", r"\xi": "ξ", r"\pi": "π",
    r"\rho": "ρ", r"\sigma": "σ", r"\tau": "τ", r"\upsilon": "υ",
    r"\phi": "φ", r"\chi": "χ", r"\psi": "ψ", r"\omega": "ω",
    r"\Gamma": "Γ", r"\Delta": "Δ", r"\Theta": "Θ", r"\Lambda": "Λ",
    r"\Xi": "Ξ", r"\Pi": "Π", r"\Sigma": "Σ", r"\Upsilon": "Υ",
    r"\Phi": "Φ", r"\Psi": "Ψ", r"\Omega": "Ω",
    r"\infty": "∞", r"\partial": "∂", r"\nabla": "∇", r"\pm": "±",
    r"\times": "×", r"\cdot": "·", r"\div": "÷", r"\leq": "≤",
    r"\geq": "≥", r"\neq": "≠", r"\approx": "≈", r"\to": "→",
    r"\Rightarrow": "⇒", r"\rightarrow": "→", r"\forall": "∀",
    r"\exists": "∃", r"\in": "∈", r"\notin": "∉", r"\subset": "⊂",
    r"\subseteq": "⊆", r"\union": "∪", r"\cup": "∪", r"\cap": "∩",
    r"\aleph": "ℵ", r"\hbar": "ℏ", r"\quad": " ", r"\qquad": "  ",
    r"\,": " ", r"\;": " ", r"\!": ""
}

def extract_balanced_group(s: str, start_idx: int):
    """Given a string and the index of an opening '{', returns (content_inside, end_index_after_closing_brace)."""
    if start_idx >= len(s) or s[start_idx] != '{':
        return "", start_idx
    depth = 0
    i = start_idx
    while i < len(s):
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                return s[start_idx + 1:i], i + 1
        i += 1
    return s[start_idx + 1:], len(s)


def parse_math_fractions_and_roots(text: str) -> str:
    """Parses nested \\frac{num}{den} and \\sqrt{expr} using balanced-group extraction into Qt-compatible math notation."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        # 1. Match \frac{num}{den} or bare frac{num}{den}
        is_frac = False
        prefix_len = 0
        if text[i:i+5] == r"\frac":
            is_frac = True
            prefix_len = 5
        elif text[i:i+4] == "frac" and (i == 0 or not text[i-1].isalnum()):
            is_frac = True
            prefix_len = 4

        if is_frac:
            j = i + prefix_len
            while j < n and text[j].isspace():
                j += 1
            if j < n and text[j] == '{':
                num, next_j = extract_balanced_group(text, j)
                while next_j < n and text[next_j].isspace():
                    next_j += 1
                if next_j < n and text[next_j] == '{':
                    den, end_j = extract_balanced_group(text, next_j)
                    num_parsed = parse_math_fractions_and_roots(num.strip())
                    den_parsed = parse_math_fractions_and_roots(den.strip())

                    # Clean Qt RichText fraction notation ensuring the division slash / is always visible
                    if num_parsed.isdigit() and den_parsed.isdigit():
                        frac_html = f"({num_parsed}/{den_parsed})"
                    elif '+' in den_parsed or '-' in den_parsed:
                        frac_html = f"({num_parsed})/({den_parsed})"
                    else:
                        frac_html = f"({num_parsed})/{den_parsed}"
                    out.append(frac_html)
                    i = end_j
                    continue

        # 2. Match \sqrt[n]{expr} or \sqrt{expr}
        if text[i:i+5] == r"\sqrt":
            j = i + 5
            while j < n and text[j].isspace():
                j += 1
            degree = ""
            if j < n and text[j] == '[':
                end_bracket = text.find(']', j)
                if end_bracket != -1:
                    degree = text[j+1:end_bracket]
                    j = end_bracket + 1
                    while j < n and text[j].isspace():
                        j += 1
            if j < n and text[j] == '{':
                radicand, end_j = extract_balanced_group(text, j)
                rad_parsed = parse_math_fractions_and_roots(radicand)
                if degree:
                    out.append(f'<sup>{degree}</sup>√(<span style="text-decoration:overline;">{rad_parsed}</span>)')
                else:
                    out.append(f'√(<span style="text-decoration:overline;">{rad_parsed}</span>)')
                i = end_j
                continue

        out.append(text[i])
        i += 1
    return "".join(out)


def replace_greek_and_symbols(s: str) -> str:
    """Replaces LaTeX symbols and Greek letters using word boundaries and longest-first matching."""
    # First handle multi-char symbols sorted by length descending
    for cmd in sorted(GREEK_AND_SYMBOLS.keys(), key=len, reverse=True):
        sym = GREEK_AND_SYMBOLS[cmd]
        if cmd.startswith('\\') and cmd[1:].isalpha():
            s = re.sub(re.escape(cmd) + r'(?![a-zA-Z])', sym, s)
        else:
            s = s.replace(cmd, sym)
    return s


def clean_math_syntax(math_str: str) -> str:
    """Converts a math expression string into clean mathematical HTML typography without LaTeX syntax, preserving all operators."""
    s = math_str.strip()

    # 1. Clean brackets and formatting commands
    s = re.sub(r'\\left\s*\(', '(', s)
    s = re.sub(r'\\right\s*\)', ')', s)
    s = re.sub(r'\\left\s*\[', '[', s)
    s = re.sub(r'\\right\s*\]', ']', s)
    s = re.sub(r'\\left\s*\{', '{', s)
    s = re.sub(r'\\right\s*\}', '}', s)
    s = re.sub(r'\\left\s*\|', '|', s)
    s = re.sub(r'\\right\s*\|', '|', s)
    s = re.sub(r'\\text\{([^{}]+)\}', r'\1', s)
    s = re.sub(r'\\mathrm\{([^{}]+)\}', r'\1', s)
    s = re.sub(r'\\mathbf\{([^{}]+)\}', r'<b>\1</b>', s)

    # 2. Parse balanced fractions and roots
    s = parse_math_fractions_and_roots(s)

    # 3. Integrals \int_{a}^{b} or \int_a^b or bare \int
    s = re.sub(r'\\int_\{([^{}]+)\}\^\{([^{}]+)\}', r'∫<sub>\1</sub><sup>\2</sup> ', s)
    s = re.sub(r'\\int_([0-9a-zA-Z])\^([0-9a-zA-Z])', r'∫<sub>\1</sub><sup>\2</sup> ', s)
    s = re.sub(r'\\int(?![a-zA-Z])', '∫ ', s)

    # 4. Sums & Limits
    s = re.sub(r'\\sum_\{([^{}]+)\}\^\{([^{}]+)\}', r'∑<sub>\1</sub><sup>\2</sup> ', s)
    s = re.sub(r'\\sum(?![a-zA-Z])', '∑ ', s)
    s = re.sub(r'\\lim_\{([^{}]+)\}', r'lim<sub>\1</sub> ', s)
    s = re.sub(r'\\lim(?![a-zA-Z])', 'lim ', s)

    # 5. Exponents & Subscripts with balanced group handling
    s = re.sub(r'\^\{([^{}]+)\}', r'<sup>\1</sup>', s)
    s = re.sub(r'\^([0-9a-zA-Z\+\-\*nxy])', r'<sup>\1</sup>', s)
    s = re.sub(r'_\{([^{}]+)\}', r'<sub>\1</sub>', s)
    s = re.sub(r'_([0-9a-zA-Z])', r'<sub>\1</sub>', s)

    # 6. Greek letters & mathematical symbols
    s = replace_greek_and_symbols(s)

    # 7. Strip leftover backslashes only from known latex commands, preserving division slashes and arithmetic operators
    s = re.sub(r'\\([a-zA-Z]+)', r'\1', s)
    s = s.replace('\\', '')
    s = s.replace('{', '').replace('}', '')

    return s


def format_math_to_html(raw_text: str) -> str:
    r"""
    Parses a raw LaTeX document or Markdown + Math string into a clean, PDF-level HTML view
    with clear heading hierarchy, bolding, bullet points, and typeset math notation.
    Completely eliminates raw LaTeX syntax (\section, \begin{center}, \textbf, \vspace, etc.)
    and renders clean, beautiful typography.
    """
    if not raw_text or not raw_text.strip():
        return "<p style='color:#888; font-style:italic;'>No content provided.</p>"

    import datetime
    today_str = datetime.date.today().strftime("%B %d, %Y")

    text = raw_text

    # Extract body inside \begin{document} ... \end{document} if present
    doc_body_m = re.search(r'\\begin\{document\}(.*?)\\end\{document\}', text, flags=re.DOTALL)
    if doc_body_m:
        text = doc_body_m.group(1)

    # 1. Clean preambles & configuration
    text = re.sub(r'\\documentclass\[.*?\]\{.*?\}|\\documentclass\{.*?\}', '', text)
    text = re.sub(r'\\usepackage\[.*?\]\{.*?\}|\\usepackage\{.*?\}', '', text)
    text = re.sub(r'\\title\{.*?\}|\\author\{.*?\}|\\date\{.*?\}|\\maketitle', '', text)

    # 2. Format \begin{center} ... \end{center} header blocks
    def _center_repl(m):
        inner = m.group(1).strip()
        return f'<div style="text-align: center; margin-bottom: 22px; padding-bottom: 8px;">{inner}</div>'
    text = re.sub(r'\\begin\{center\}(.*?)\\end\{center\}', _center_repl, text, flags=re.DOTALL)

    # 3. Clean spacing and date macros
    text = re.sub(r'\\vspace\*?\{[^{}]*\}', '<div style="height: 10px;"></div>', text)
    text = re.sub(r'\\hspace\*?\{[^{}]*\}', '&nbsp;&nbsp;', text)
    text = text.replace(r'\today', today_str)

    # 4. Handle \boxed{...} using balanced brace extraction
    i = 0
    while i < len(text):
        idx = text.find(r'\boxed', i)
        if idx == -1:
            break
        j = idx + 6
        while j < len(text) and text[j].isspace():
            j += 1
        if j < len(text) and text[j] == '{':
            inner, end_j = extract_balanced_group(text, j)
            inner_clean = clean_math_syntax(inner)
            repl = (
                f'<div style="display: inline-block; border: 1.2px solid currentColor; '
                f'background: transparent; padding: 3px 12px; margin: 6px auto; '
                f'font-weight: 600; font-size: 1.08em;">{inner_clean}</div>'
            )
            text = text[:idx] + repl + text[end_j:]
            i = idx + len(repl)
        else:
            i = idx + 6

    # 5. Handle \textbf{...}, \textit{...}, \emph{...}, \underline{...}
    for cmd, tag in [(r'\textbf', 'b'), (r'\textit', 'i'), (r'\emph', 'i'), (r'\underline', 'u')]:
        i = 0
        while i < len(text):
            idx = text.find(cmd, i)
            if idx == -1:
                break
            j = idx + len(cmd)
            while j < len(text) and text[j].isspace():
                j += 1
            if j < len(text) and text[j] == '{':
                inner, end_j = extract_balanced_group(text, j)
                inner_clean = re.sub(r'\\(Large|large|LARGE|huge|Huge|small|footnotesize|tiny|normalsize)', '', inner).strip()
                repl = f'<{tag}>{inner_clean}</{tag}>'
                text = text[:idx] + repl + text[end_j:]
                i = idx + len(repl)
            else:
                i = idx + len(cmd)

    # 6. Sections and Subsections (authentic LaTeX typography without thick web borders)
    def _sec_repl(m):
        title = m.group(1).strip()
        return (
            f'<div class="pdf-sec-head" style="font-size: 14pt; font-weight: bold; '
            f'margin-top: 18pt; margin-bottom: 5pt; font-family: serif;">{title}</div>'
        )
    text = re.sub(r'\\section\*?\{([^{}]+)\}', _sec_repl, text)

    def _subsec_repl(m):
        title = m.group(1).strip()
        return (
            f'<div class="pdf-subsec-head" style="font-size: 12pt; font-weight: bold; '
            f'margin-top: 12pt; margin-bottom: 4pt; font-family: serif;">{title}</div>'
        )
    text = re.sub(r'\\subsection\*?\{([^{}]+)\}', _subsec_repl, text)

    def _subsubsec_repl(m):
        title = m.group(1).strip()
        return f'<div style="font-size: 11pt; font-weight: bold; margin-top: 9pt; margin-bottom: 3pt;">{title}</div>'
    text = re.sub(r'\\subsubsection\*?\{([^{}]+)\}', _subsubsec_repl, text)

    # 7. Lists: itemize and enumerate
    def _itemize_repl(m):
        inner = m.group(1)
        items = re.split(r'\\item\s+', inner)
        lis = []
        for it in items:
            it = it.strip()
            if it:
                lis.append(f'<li style="margin-bottom: 3px; line-height: 1.45;">{it}</li>')
        return f'<ul style="margin: 5pt 0 8pt 20pt; padding: 0;">{"".join(lis)}</ul>'
    text = re.sub(r'\\begin\{itemize\}(.*?)\\end\{itemize\}', _itemize_repl, text, flags=re.DOTALL)

    def _enum_repl(m):
        inner = m.group(1)
        items = re.split(r'\\item\s+', inner)
        lis = []
        for it in items:
            it = it.strip()
            if it:
                lis.append(f'<li style="margin-bottom: 3px; line-height: 1.45;">{it}</li>')
        return f'<ol style="margin: 5pt 0 8pt 20pt; padding: 0;">{"".join(lis)}</ol>'
    text = re.sub(r'\\begin\{enumerate\}(.*?)\\end\{enumerate\}', _enum_repl, text, flags=re.DOTALL)

    # 8. Align / Aligned multi-line math environments
    def _align_repl(m):
        lines = m.group(1).strip().split(r'\\')
        rows = []
        for l in lines:
            l = l.strip()
            if not l:
                continue
            # Normalize escaped ampersands that might have leaked
            l = l.replace(r'\&=', '&=').replace(r'\&', '&')
            if '&=' in l:
                lhs, rhs = l.split('&=', 1)
                lhs_c = clean_math_syntax(lhs.replace('&', '').strip())
                rhs_c = clean_math_syntax(rhs.replace('&', '').strip())
                rows.append(
                    f'<tr><td style="text-align: right; padding: 2px 4px; font-size: 1.08em; font-weight: 500;">{lhs_c}</td>'
                    f'<td style="text-align: left; padding: 2px 4px; font-size: 1.08em; font-weight: 500;">= {rhs_c}</td></tr>'
                )
            elif '&' in l:
                parts = [clean_math_syntax(p.replace('&', '').strip()) for p in l.split('&')]
                tds = "".join(f'<td style="padding: 2px 6px; font-size: 1.08em;">{p}</td>' for p in parts)
                rows.append(f'<tr>{tds}</tr>')
            else:
                c = clean_math_syntax(l)
                rows.append(f'<tr><td colspan="2" style="text-align: center; padding: 2px 4px; font-size: 1.08em;">{c}</td></tr>')
        return f'<table style="margin: 8pt auto; border-collapse: collapse;">{"".join(rows)}</table>'

    text = re.sub(r'\\begin\{align\*?\}(.*?)\\end\{align\*?\}', _align_repl, text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{aligned\}(.*?)\\end\{aligned\}', _align_repl, text, flags=re.DOTALL)

    # 9. Format Display Math Environments
    def _disp_repl(m):
        c = clean_math_syntax(m.group(1))
        return f'<div class="pdf-display-math" style="text-align: center; margin: 10px 0; font-size: 1.12em; font-weight: 600; line-height: 1.6;">{c}</div>'

    text = re.sub(r'\\begin\{equation\*?\}(.*?)\\end\{equation\*?\}', _disp_repl, text, flags=re.DOTALL)
    text = re.sub(r'\\\[(.*?)\\\]', _disp_repl, text, flags=re.DOTALL)
    text = re.sub(r'\$\$(.*?)\$\$', _disp_repl, text, flags=re.DOTALL)

    # 10. Format Inline Math
    def _inline_repl(m):
        c = clean_math_syntax(m.group(1))
        return f'<span class="pdf-inline-math" style="font-weight: 600;">{c}</span>'

    text = re.sub(r'\\\((.*?)\\\)', _inline_repl, text)
    text = re.sub(r'\$([^\$\n]+)\$', _inline_repl, text)

    # 11. Parse bare LaTeX fractions and roots
    text = parse_math_fractions_and_roots(text)

    # 12. Line-by-line Markdown Structure (if Markdown mixed in)
    lines = text.split('\n')
    out = []
    for line in lines:
        sline = line.strip()
        if not sline:
            out.append('<br/>')
            continue
        if sline.startswith('#### '):
            out.append(f'<div style="font-size: 14px; font-weight: 700; margin-top: 8px; margin-bottom: 3px;">{sline[5:].strip()}</div>')
        elif sline.startswith('### '):
            out.append(f'<div style="font-size: 16px; font-weight: 800; margin-top: 10px; margin-bottom: 4px;">{sline[4:].strip()}</div>')
        elif sline.startswith('## '):
            out.append(f'<div style="font-size: 18px; font-weight: 800; margin-top: 12px; margin-bottom: 5px;">{sline[3:].strip()}</div>')
        elif sline.startswith('# '):
            out.append(f'<div style="font-size: 20px; font-weight: 800; margin-top: 14px; margin-bottom: 6px;">{sline[2:].strip()}</div>')
        elif re.match(r'^[\*\-]\s+', sline):
            item = re.sub(r'^[\*\-]\s+', '', sline)
            out.append(f'<div style="margin-left: 14px; margin-top: 2px; margin-bottom: 2px; line-height: 1.5;">• &nbsp;{item}</div>')
        elif re.match(r'^\d+\.\s+', sline):
            m = re.match(r'^(\d+)\.\s+(.*)$', sline)
            out.append(f'<div style="margin-left: 14px; margin-top: 2px; margin-bottom: 2px; line-height: 1.5;"><b>{m.group(1)}.</b> &nbsp;{m.group(2)}</div>')
        elif sline.startswith('<div') or sline.startswith('<ul') or sline.startswith('<ol') or sline.startswith('<table') or sline.startswith('<p') or sline.startswith('</'):
            out.append(sline)
        else:
            out.append(f'<div style="line-height: 1.6; margin-bottom: 3px;">{sline}</div>')

    text = "".join(out)

    # 13. Inline Bolds & Italics
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
    text = re.sub(r'(?<![a-zA-Z0-9])\*([^\*\n<]+?)\*(?![a-zA-Z0-9])', r'<i>\1</i>', text)

    # 14. Global symbols & linebreaks
    text = replace_greek_and_symbols(text)
    text = text.replace(r'\\', '<br/>').replace(r'\newline', '<br/>').replace(r'\par', '<br/>')
    text = text.replace(r'\%', '%').replace(r'\$', '$').replace(r'\&', '&').replace(r'\_', '_')
    text = re.sub(r'\\(Large|large|LARGE|huge|Huge|small|footnotesize|tiny|normalsize|centering|noindent)', '', text)

    # 15. Clean any leftover stray LaTeX commands (\foo{bar} -> bar, \foo -> "")
    # Unpack any remaining unknown \cmd{content} to just content
    text = re.sub(r'\\[a-zA-Z]+\{([^{}]+)\}', r'\1', text)
    # Strip bare unknown \cmd
    text = re.sub(r'\\[a-zA-Z]+\*?', '', text)

    return text.strip()
