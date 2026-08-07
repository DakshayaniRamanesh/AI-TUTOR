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
    """Converts a math expression string into clean mathematical typography without LaTeX syntax."""
    s = math_str.strip()

    # 1. Clean left/right brackets and formatting commands
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

    # 2. Fractions \frac{num}{den} -> (num / den) with fractions
    def _frac_repl(m):
        num = clean_math_syntax(m.group(1))
        den = clean_math_syntax(m.group(2))
        return f'<span class="math-frac"><sup class="math-num">{num}</sup>&frasl;<sub class="math-den">{den}</sub></span>'

    for _ in range(3): # Support nested fractions up to 3 levels
        s = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', _frac_repl, s)

    # 3. Square roots \sqrt{expr} or \sqrt[n]{expr}
    s = re.sub(r'\\sqrt\[([^{}]+)\]\{([^{}]+)\}', r'<sup>\1</sup>√(\2)', s)
    s = re.sub(r'\\sqrt\{([^{}]+)\}', r'√(\1)', s)

    # 4. Integrals \int_{a}^{b} or \int_a^b
    s = re.sub(r'\\int_\{([^{}]+)\}\^\{([^{}]+)\}', r'∫<sub>\1</sub><sup>\2</sup>', s)
    s = re.sub(r'\\int_([0-9a-zA-Z])\^([0-9a-zA-Z])', r'∫<sub>\1</sub><sup>\2</sup>', s)
    s = re.sub(r'\\int', '∫ ', s)

    # 5. Sums & Limits
    s = re.sub(r'\\sum_\{([^{}]+)\}\^\{([^{}]+)\}', r'∑<sub>\1</sub><sup>\2</sup>', s)
    s = re.sub(r'\\sum', '∑ ', s)
    s = re.sub(r'\\lim_\{([^{}]+)\}', r'lim<sub>\1</sub>', s)

    # 6. Exponents & Subscripts
    s = re.sub(r'\^\{([^{}]+)\}', r'<sup>\1</sup>', s)
    s = re.sub(r'\^([0-9a-zA-Z\+\-])', r'<sup>\1</sup>', s)
    s = re.sub(r'_\{([^{}]+)\}', r'<sub>\1</sub>', s)
    s = re.sub(r'_([0-9a-zA-Z])', r'<sub>\1</sub>', s)

    # 7. Greek letters & symbols
    for cmd, sym in GREEK_AND_SYMBOLS.items():
        s = s.replace(cmd, sym)

    # 8. Strip any leftover backslashes & braces
    s = re.sub(r'\\([a-zA-Z]+)', r'\1', s)
    s = s.replace('\\', '').replace('{', '').replace('}', '')

    return s


def format_math_to_html(raw_text: str) -> str:
    """
    Parses a raw LaTeX document or string into a clean, PDF-level HTML preview without LaTeX commands.
    """
    if not raw_text or not raw_text.strip():
        return "<p>No content provided.</p>"

    text = raw_text

    # Extract body inside \begin{document} ... \end{document} if present
    doc_body_m = re.search(r'\\begin\{document\}(.*?)\\end\{document\}', text, flags=re.DOTALL)
    if doc_body_m:
        text = doc_body_m.group(1)

    # Clean center environments & spacing commands before math parsing
    text = text.replace(r"\begin{center}", '<div style="text-align: center;">')
    text = text.replace(r"\end{center}", '</div>')
    text = re.sub(r'\\vspace\*?\{[^{}]*\}', '<br/>', text)
    text = re.sub(r'\\hspace\*?\{[^{}]*\}', ' ', text)
    text = re.sub(r'\\vfill|\\hfill', '', text)
    text = re.sub(r'\\(Large|large|LARGE|huge|Huge|small|footnotesize|tiny|normalsize|centering|noindent)', '', text)

    # 1. Format Display Math Environments BEFORE stripping general environments
    def _display_math_repl(m):
        math_content = m.group(1).strip()
        cleaned = clean_math_syntax(math_content)
        return f'<div class="pdf-display-math">{cleaned}</div>'

    text = re.sub(r'\\begin\{equation\*?\}(.*?)\\end\{equation\*?\}', _display_math_repl, text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{align\*?\}(.*?)\\end\{align\*?\}', _display_math_repl, text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{gather\*?\}(.*?)\\end\{gather\*?\}', _display_math_repl, text, flags=re.DOTALL)
    text = re.sub(r'\\\[(.*?)\\\]', _display_math_repl, text, flags=re.DOTALL)
    text = re.sub(r'\$\$(.*?)\$\$', _display_math_repl, text, flags=re.DOTALL)

    # 2. Format Inline Math Environments
    def _inline_math_repl(m):
        math_content = m.group(1).strip()
        cleaned = clean_math_syntax(math_content)
        return f'<span class="pdf-inline-math">{cleaned}</span>'

    text = re.sub(r'\\\((.*?)\\\)', _inline_math_repl, text)
    text = re.sub(r'\$([^\$]+)\$', _inline_math_repl, text)

    # 3. Format Beamer frames / slides
    def _frame_repl(m):
        stitle = m.group(1).strip()
        sbody = m.group(2).strip()
        return f'<div class="pdf-slide-box"><h3 class="slide-heading">Slide: {stitle}</h3><div class="slide-content">{sbody}</div></div>'

    text = re.sub(r'\\begin\{frame\}\{([^{}]+)\}(.*?)\\end\{frame\}', _frame_repl, text, flags=re.DOTALL)

    # 4. Format Sections & Structure
    text = re.sub(r'\\section\*?\{([^{}]+)\}', r'<h2 class="pdf-sec-head">\1</h2>', text)
    text = re.sub(r'\\subsection\*?\{([^{}]+)\}', r'<h3 class="pdf-subsec-head">\1</h3>', text)
    text = re.sub(r'\\subsubsection\*?\{([^{}]+)\}', r'<h4 class="pdf-subsubsec-head">\1</h4>', text)

    # 5. Format Lists
    text = text.replace(r"\begin{itemize}", "<ul>").replace(r"\end{itemize}", "</ul>")
    text = text.replace(r"\begin{enumerate}", "<ol>").replace(r"\end{enumerate}", "</ol>")
    text = re.sub(r'\\item\s*', '<li>', text)

    # 6. Format Inline Text Commands
    text = re.sub(r'\\textbf\{([^{}]+)\}', r'<b>\1</b>', text)
    text = re.sub(r'\\textit\{([^{}]+)\}', r'<i>\1</i>', text)
    text = re.sub(r'\\underline\{([^{}]+)\}', r'<u>\1</u>', text)
    text = re.sub(r'\\textcolor\{([^{}]+)\}\{([^{}]+)\}', r'<span style="color:\1">\2</span>', text)

    # 7. Strip preamble & document configuration commands
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

    # 8. Clean escapes & linebreaks
    text = text.replace(r"\\", "<br/>")
    text = text.replace(r"\newline", "<br/>")
    text = text.replace(r"\par", "<br/><br/>")
    text = text.replace(r"\%", "%").replace(r"\$", "$").replace(r"\&", "&").replace(r"\_", "_")

    # 9. Clean any remaining stray LaTeX commands
    text = re.sub(r'\\[a-zA-Z]+(\*)*', '', text)
    text = text.replace('{', '').replace('}', '')

    # Wrap in clean PDF Document structure
    html_out = f"""
    <div class="pdf-content">
        {text}
    </div>
    """
    return html_out
