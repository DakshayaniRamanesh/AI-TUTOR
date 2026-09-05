"""
Unit tests for the LaTeX Semantic Parser.
Verifies identification of sections, subsections, equations, derivations (align*),
lists (itemize, enumerate), tables, and boxed highlights into the LessonDocument IR.
"""

import pytest
from backend.latex_video.latex_parser import LatexSemanticParser
from backend.latex_video.document_model import ElementType, ImportanceLevel


@pytest.fixture
def parser():
    return LatexSemanticParser()


def test_parse_sections_and_subsections(parser):
    tex = r"""
\section{Newton's Second Law}

\subsection{The Core Idea}
A net force acting on an object causes an acceleration proportional to the force.

\subsection{Mathematical Statement}
\[
\mathbf{F} = m\mathbf{a}
\]
"""
    doc = parser.parse(tex, fallback_title="Physics Lesson")
    assert len(doc.sections) >= 1
    
    types = [e.type for e in doc.all_elements]
    assert ElementType.SECTION in types
    assert ElementType.SUBSECTION in types
    assert ElementType.PARAGRAPH in types
    assert ElementType.EQUATION_DISPLAY in types


def test_parse_align_derivation_steps(parser):
    tex = r"""
\section*{Step-by-Step Calculus Derivation}
Consider the limit definition:
\begin{align*}
f'(x) &= \lim_{h \to 0} \frac{f(x+h) - f(x)}{h} \\
&= \lim_{h \to 0} \frac{(x+h)^2 - x^2}{h} \\
&= \lim_{h \to 0} (2x + h) \\
&= 2x
\end{align*}
"""
    doc = parser.parse(tex)
    step_elements = [e for e in doc.all_elements if e.type == ElementType.EQUATION_STEP]
    
    # 4 distinct derivation steps
    assert len(step_elements) == 4
    for step in step_elements:
        assert step.align_env is True
        assert "&=" in step.raw_content or "&" in step.raw_content


def test_parse_lists(parser):
    tex = r"""
\section*{Properties of Binary Search}
Key characteristics:
\begin{itemize}
\item Efficient logarithmic search time $\mathcal{O}(\log N)$.
\item Requires the array to be pre-sorted.
\item Can be implemented iteratively or recursively.
\end{itemize}

Numbered steps:
\begin{enumerate}
\item Find midpoint.
\item Compare target with mid.
\item Halve the search space.
\end{enumerate}
"""
    doc = parser.parse(tex)
    bullets = [e for e in doc.all_elements if e.type == ElementType.BULLET_ITEM]
    numbered = [e for e in doc.all_elements if e.type == ElementType.NUMBERED_ITEM]
    
    assert len(bullets) == 3
    assert len(numbered) == 3
    assert "logarithmic" in bullets[0].clean_text.lower()
    assert "midpoint" in numbered[0].clean_text.lower()


def test_parse_boxed_result(parser):
    tex = r"""
\section*{Final Answer}
The resulting derivative is:
\[
\boxed{\frac{d}{dx} x^2 = 2x}
\]
"""
    doc = parser.parse(tex)
    boxed = [e for e in doc.all_elements if e.type == ElementType.BOXED_RESULT or e.is_boxed]
    assert len(boxed) >= 1
    assert boxed[0].importance == ImportanceLevel.HIGH


def test_complexity_scoring(parser):
    simple_tex = r"Simple text statement."
    complex_tex = r"\[ \int_{-\infty}^{\infty} \frac{\sqrt{x^2 + \alpha}}{\sum_{k=1}^n \beta_k} dx \]"
    
    doc1 = parser.parse(simple_tex)
    doc2 = parser.parse(complex_tex)
    
    simple_elem = doc1.all_elements[0]
    complex_elem = doc2.all_elements[0]
    
    assert complex_elem.complexity_score > simple_elem.complexity_score
