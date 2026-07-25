r"""
LaTeX & Markdown Math Formatter to HTML
Converts raw LaTeX math expressions ($$...$$, $...$, \frac, \int, \cdot, \left\right) and Markdown
into beautiful, clean HTML mathematical notation formatted onto notebook ruled paper lines.
"""

import re

def format_math_to_html(raw_text: str) -> str:
    if not raw_text:
        return ""

    text = raw_text

    # 1. Clean common LaTeX escape sequences
    text = text.replace(r"\ ", " ")
    text = text.replace(r"\cdot", " · ")
    text = text.replace(r"\left(", "(").replace(r"\right)", ")")
    text = text.replace(r"\left[", "[").replace(r"\right]", "]")

    # 2. Convert LaTeX Integrals \int
    text = re.sub(r'\\int', '∫ ', text)

    # 3. Convert LaTeX Fractions \frac{num}{den} -> <sup>num</sup>/<sub>den</sub> or (num / den)
    def _replace_frac(match):
        num = match.group(1).strip()
        den = match.group(2).strip()
        return f'<span style="font-size: 1.1em; font-weight: bold; color: #007aff;">(<sup>{num}</sup>&frasl;<sub>{den}</sub>)</span>'

    # Support nested/simple fractions
    text = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', _replace_frac, text)
    text = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', _replace_frac, text) # second pass for nested

    # 4. Convert Exponents x^{n} or x^2
    text = re.sub(r'\^\{([^{}]+)\}', r'<sup>\1</sup>', text)
    text = re.sub(r'\^([0-9a-zA-Z])', r'<sup>\1</sup>', text)

    # 5. Convert Block Formulas $$...$$
    def _replace_block_formula(match):
        formula = match.group(1).strip()
        return f'<div style="font-size: 24px; font-weight: bold; color: #007aff; margin: 8px 0; line-height: 28px; background: rgba(0, 122, 255, 0.05); padding: 4px 10px; border-left: 3px solid #007aff; border-radius: 4px;">{formula}</div>'

    text = re.sub(r'\$\$(.*?)\$\$', _replace_block_formula, text, flags=re.DOTALL)

    # 6. Convert Inline Formulas $...$
    def _replace_inline_formula(match):
        formula = match.group(1).strip()
        return f'<span style="font-size: 20px; font-weight: bold; color: #0b2545;">{formula}</span>'

    text = re.sub(r'\$([^\$]+)\$', _replace_inline_formula, text)

    # 7. Convert Markdown Headings (###, ##, #)
    text = re.sub(r'###\s*(.*)', r'<h3 style="font-size: 22px; font-weight: bold; color: #007aff; margin-top: 14px; margin-bottom: 4px; line-height: 28px;">\1</h3>', text)
    text = re.sub(r'##\s*(.*)', r'<h2 style="font-size: 24px; font-weight: bold; color: #007aff; margin-top: 16px; margin-bottom: 6px; line-height: 28px;">\1</h2>', text)
    text = re.sub(r'#\s*(.*)', r'<h1 style="font-size: 26px; font-weight: bold; color: #007aff; margin-top: 18px; margin-bottom: 8px; line-height: 28px;">\1</h1>', text)

    # 8. Convert Markdown Bold **Text** & Italics *Text*
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)

    # 9. Convert Horizontal Dividers ---
    text = re.sub(r'---', r'<hr style="border: none; border-top: 1px solid #d1d1d6; margin: 10px 0;"/>', text)

    # 10. Wrap in Container with Ruled Line Height (28px)
    html_res = f"""
    <div style="font-family: 'Caveat', 'Comic Sans MS', cursive; font-size: 22px; line-height: 28px; color: #0b2545;">
        {text.replace(chr(10), '<br/>')}
    </div>
    """
    return html_res
