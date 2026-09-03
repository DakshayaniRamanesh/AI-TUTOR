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

def clean_math_syntax(math_str: str) -> str:
    """Converts a math expression string into clean mathematical HTML typography without LaTeX syntax."""
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

    # 2. Fractions \frac{num}{den} or bare frac{num}{den} -> typeset fraction HTML
    def _frac_repl(m):
        num = clean_math_syntax(m.group(1))
        den = clean_math_syntax(m.group(2))
        return f'<span style="display:inline-block; vertical-align:middle; text-align:center; padding:0 2px;"><span style="display:block; font-size:90%; border-bottom:1px solid currentColor; padding-bottom:1px;">{num}</span><span style="display:block; font-size:90%; padding-top:1px;">{den}</span></span>'

    for _ in range(4):  # Support nested fractions
        s = re.sub(r'\\?frac\{([^{}]+)\}\{([^{}]+)\}', _frac_repl, s)

    # 3. Square roots \sqrt{expr} or \sqrt[n]{expr}
    s = re.sub(r'\\?sqrt\[([^{}]+)\]\{([^{}]+)\}', r'<sup>\1</sup>√(<span style="text-decoration:overline;">\2</span>)', s)
    s = re.sub(r'\\?sqrt\{([^{}]+)\}', r'√(<span style="text-decoration:overline;">\1</span>)', s)

    # 4. Integrals \int_{a}^{b} or \int_a^b
    s = re.sub(r'\\int_\{([^{}]+)\}\^\{([^{}]+)\}', r'∫<sub>\1</sub><sup>\2</sup> ', s)
    s = re.sub(r'\\int_([0-9a-zA-Z])\^([0-9a-zA-Z])', r'∫<sub>\1</sub><sup>\2</sup> ', s)
    s = re.sub(r'\\int', '∫ ', s)

    # 5. Sums & Limits
    s = re.sub(r'\\sum_\{([^{}]+)\}\^\{([^{}]+)\}', r'∑<sub>\1</sub><sup>\2</sup> ', s)
    s = re.sub(r'\\sum', '∑ ', s)
    s = re.sub(r'\\lim_\{([^{}]+)\}', r'lim<sub>\1</sub> ', s)

    # 6. Exponents & Subscripts
    s = re.sub(r'\^\{([^{}]+)\}', r'<sup>\1</sup>', s)
    s = re.sub(r'\^([0-9a-zA-Z\+\-\*nxy])', r'<sup>\1</sup>', s)
    s = re.sub(r'_\{([^{}]+)\}', r'<sub>\1</sub>', s)
    s = re.sub(r'_([0-9a-zA-Z])', r'<sub>\1</sub>', s)

    # 7. Greek letters & mathematical symbols
    for cmd, sym in GREEK_AND_SYMBOLS.items():
        s = s.replace(cmd, sym)

    # 8. Strip any leftover backslashes & braces
    s = re.sub(r'\\([a-zA-Z]+)', r'\1', s)
    s = s.replace('\\', '').replace('{', '').replace('}', '')

    return s


def format_math_to_html(raw_text: str) -> str:
    """
    Parses a raw LaTeX document or Markdown + Math string into a clean, PDF-level HTML view
    with clear heading hierarchy, bolding, bullet points, and typeset math notation.
    No literal '###', '**', or raw LaTeX symbols will be shown.
    """
    if not raw_text or not raw_text.strip():
        return "<p>No content provided.</p>"

    text = raw_text

    # Extract body inside \begin{document} ... \end{document} if present
    doc_body_m = re.search(r'\\begin\{document\}(.*?)\\end\{document\}', text, flags=re.DOTALL)
    if doc_body_m:
        text = doc_body_m.group(1)

    # 1. Strip preamble & LaTeX document configuration commands
    text = re.sub(r'\\documentclass\[.*?\]\{.*?\}', '', text)
    text = re.sub(r'\\documentclass\{.*?\}', '', text)
    text = re.sub(r'\\usepackage\[.*?\]\{.*?\}', '', text)
    text = re.sub(r'\\usepackage\{.*?\}', '', text)
    text = re.sub(r'\\geometry\{.*?\}', '', text)
    text = re.sub(r'\\pagestyle\{.*?\}', '', text)
    text = re.sub(r'\\thispagestyle\{.*?\}', '', text)
    text = re.sub(r'\\title\{.*?\}', '', text)
    text = re.sub(r'\\author\{.*?\}', '', text)
    text = re.sub(r'\\date\{.*?\}', '', text)
    text = re.sub(r'\\maketitle', '', text)

    # Clean center environments & spacing commands
    text = text.replace(r"\begin{center}", '<div style="text-align: center;">')
    text = text.replace(r"\end{center}", '</div>')
    text = re.sub(r'\\vspace\*?\{[^{}]*\}', '<br/>', text)
    text = re.sub(r'\\hspace\*?\{[^{}]*\}', ' ', text)
    text = re.sub(r'\\vfill|\\hfill', '', text)
    text = re.sub(r'\\(Large|large|LARGE|huge|Huge|small|footnotesize|tiny|normalsize|centering|noindent)', '', text)

    # 2. Format Display Math Environments ($$...$$, \[...\], \begin{equation}...)
    def _display_math_repl(m):
        math_content = m.group(1).strip()
        cleaned = clean_math_syntax(math_content)
        return f'<div style="margin: 8px 0; font-size: 1.1em; line-height: 1.6; text-align: left; padding: 4px 0;">{cleaned}</div>'

    text = re.sub(r'\\begin\{equation\*?\}(.*?)\\end\{equation\*?\}', _display_math_repl, text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{align\*?\}(.*?)\\end\{align\*?\}', _display_math_repl, text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{gather\*?\}(.*?)\\end\{gather\*?\}', _display_math_repl, text, flags=re.DOTALL)
    text = re.sub(r'\\\[(.*?)\\\]', _display_math_repl, text, flags=re.DOTALL)
    text = re.sub(r'\$\$(.*?)\$\$', _display_math_repl, text, flags=re.DOTALL)

    # 3. Format Inline Math ($...$, \(...\))
    def _inline_math_repl(m):
        math_content = m.group(1).strip()
        cleaned = clean_math_syntax(math_content)
        return f'<span>{cleaned}</span>'

    text = re.sub(r'\\\((.*?)\\\)', _inline_math_repl, text)
    text = re.sub(r'\$([^\$\n]+)\$', _inline_math_repl, text)

    # 4. Clean up bare LaTeX fractions and math expressions outside delimiters
    text = re.sub(r'\\?frac\{([^{}]+)\}\{([^{}]+)\}', lambda m: clean_math_syntax(m.group(0)), text)
    text = re.sub(r'\\?sqrt\{([^{}]+)\}', lambda m: clean_math_syntax(m.group(0)), text)

    # 5. Process Markdown line-by-line for headings, lists, and structural elements
    lines = text.split('\n')
    processed_lines = []

    for line in lines:
        sline = line.strip()

        # Markdown Headings
        if sline.startswith('#### '):
            heading_txt = sline[5:].strip()
            processed_lines.append(f'<div style="font-size: 14px; font-weight: 700; margin-top: 8px; margin-bottom: 3px; color: #0a0a0a;">{heading_txt}</div>')
            continue
        elif sline.startswith('### '):
            heading_txt = sline[4:].strip()
            processed_lines.append(f'<div style="font-size: 16px; font-weight: 800; margin-top: 10px; margin-bottom: 4px; color: #0a0a0a;">{heading_txt}</div>')
            continue
        elif sline.startswith('## '):
            heading_txt = sline[3:].strip()
            processed_lines.append(f'<div style="font-size: 18px; font-weight: 800; margin-top: 12px; margin-bottom: 5px; color: #0a0a0a;">{heading_txt}</div>')
            continue
        elif sline.startswith('# '):
            heading_txt = sline[2:].strip()
            processed_lines.append(f'<div style="font-size: 20px; font-weight: 800; margin-top: 14px; margin-bottom: 6px; color: #0a0a0a;">{heading_txt}</div>')
            continue

        # Bullet lists (- item or * item)
        if re.match(r'^[\*\-]\s+', sline):
            item_text = re.sub(r'^[\*\-]\s+', '', sline)
            processed_lines.append(f'<div style="margin-left: 14px; margin-top: 2px; margin-bottom: 2px; line-height: 1.5;">• &nbsp;{item_text}</div>')
            continue

        # Numbered lists (1. item)
        num_match = re.match(r'^(\d+)\.\s+(.*)$', sline)
        if num_match:
            num = num_match.group(1)
            item_text = num_match.group(2)
            processed_lines.append(f'<div style="margin-left: 14px; margin-top: 2px; margin-bottom: 2px; line-height: 1.5;"><b>{num}.</b> &nbsp;{item_text}</div>')
            continue

        # LaTeX section commands
        sec_m = re.match(r'\\section\*?\{([^{}]+)\}', sline)
        if sec_m:
            processed_lines.append(f'<div style="font-size: 18px; font-weight: 800; margin-top: 12px; margin-bottom: 5px;">{sec_m.group(1)}</div>')
            continue
        subsec_m = re.match(r'\\subsection\*?\{([^{}]+)\}', sline)
        if subsec_m:
            processed_lines.append(f'<div style="font-size: 16px; font-weight: 800; margin-top: 10px; margin-bottom: 4px;">{subsec_m.group(1)}</div>')
            continue

        if not sline:
            processed_lines.append('<br/>')
        else:
            processed_lines.append(f'<div style="line-height: 1.6; margin-bottom: 3px;">{sline}</div>')

    text = "".join(processed_lines)

    # 6. Format Markdown Inline Bolds (**bold** / __bold__) & Italics (*italic* / _italic_)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
    text = re.sub(r'(?<![a-zA-Z0-9])\*([^\*\n]+?)\*(?![a-zA-Z0-9])', r'<i>\1</i>', text)

    # Format LaTeX Inline text formatting
    text = re.sub(r'\\textbf\{([^{}]+)\}', r'<b>\1</b>', text)
    text = re.sub(r'\\textit\{([^{}]+)\}', r'<i>\1</i>', text)
    text = re.sub(r'\\underline\{([^{}]+)\}', r'<u>\1</u>', text)

    # 7. Clean up common LaTeX symbols outside math environments
    for cmd, sym in GREEK_AND_SYMBOLS.items():
        text = text.replace(cmd, sym)

    # Clean escapes & linebreaks
    text = text.replace(r"\\", "<br/>")
    text = text.replace(r"\newline", "<br/>")
    text = text.replace(r"\par", "<br/>")
    text = text.replace(r"\%", "%").replace(r"\$", "$").replace(r"\&", "&").replace(r"\_", "_")

    # Final cleanup of any stray literal LaTeX commands or braces
    text = re.sub(r'\\[a-zA-Z]+', '', text)
    text = text.replace('{', '').replace('}', '')

    return text.strip()
