import pytest
from backend.video_generation.agents.latex_agents import (
    balance_latex_environments,
    repair_latex_document,
)


def test_balance_unclosed_itemize():
    bad_code = r"""\begin{document}
\section*{Key Insights}
\begin{itemize}
\item For a monic quadratic, look for two numbers.
\item Another insight.

\end{document}"""
    fixed = balance_latex_environments(bad_code)
    assert r"\end{itemize}" in fixed
    assert fixed.index(r"\end{itemize}") < fixed.index(r"\end{document}")


def test_balance_nested_environments():
    bad_code = r"""\begin{document}
\begin{enumerate}
\item Step 1
\begin{align*}
x = 1
\end{document}"""
    fixed = balance_latex_environments(bad_code)
    assert r"\end{align*}" in fixed
    assert r"\end{enumerate}" in fixed
    assert fixed.index(r"\end{align*}") < fixed.index(r"\end{enumerate}")
    assert fixed.index(r"\end{enumerate}") < fixed.index(r"\end{document}")


def test_already_balanced_remains_unchanged():
    good_code = r"""\documentclass{article}
\begin{document}
\begin{itemize}
\item Done
\end{itemize}
\end{document}"""
    fixed = balance_latex_environments(good_code)
    assert fixed == good_code


def test_markdown_bold_and_italics_repair():
    code = r"Solve the equation by **factoring** or using __formula__."
    repaired = repair_latex_document(code)
    assert r"\textbf{factoring}" in repaired
    assert r"\textbf{formula}" in repaired
    assert "**" not in repaired


def test_fragment_wrapped_with_preamble():
    fragment = r"\[ x^2 + 5x + 6 = 0 \]"
    repaired = repair_latex_document(fragment)
    assert r"\documentclass" in repaired
    assert r"\begin{document}" in repaired
    assert r"\end{document}" in repaired


def test_repair_ignores_line_break_spacing():
    code = r"""\begin{document}
\begin{align*}
x^2 - 2x + 1 &= 0 \\[4pt]
(x - 1)^2 &= 0 \\[4pt]
x &= 1
\end{align*}
\end{document}"""
    repaired = repair_latex_document(code)
    # Ensure no extra \] was appended before \end{document}
    assert r"\]" not in repaired

