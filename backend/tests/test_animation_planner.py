"""
Unit tests for the Animation Planner.
Verifies chronological timeline progression, non-negative durations,
content-aware reading time allocation, and slide pagination.
"""

import pytest
from backend.latex_video.latex_parser import LatexSemanticParser
from backend.latex_video.animation_planner import AnimationPlanner
from backend.latex_video.document_model import ElementType


@pytest.fixture
def parser():
    return LatexSemanticParser()


@pytest.fixture
def planner():
    return AnimationPlanner(target_fps=30)


def test_timeline_chronological_ordering(parser, planner):
    tex = r"""
\section*{Derivation of $x^2$}
\subsection*{Limit Definition}
Recall that the derivative represents instantaneous change:
\begin{align*}
f'(x) &= \lim_{h \to 0} \frac{(x+h)^2 - x^2}{h} \\
&= 2x
\end{align*}
\[
\boxed{f'(x) = 2x}
\]
"""
    doc = parser.parse(tex)
    timeline = planner.plan(doc)
    
    assert len(timeline.states) >= 4
    
    prev_end = 0.0
    for state in timeline.states:
        # Start time must match or exceed previous end time
        assert state.start_time >= prev_end - 0.001
        assert state.transition_duration > 0.0
        assert state.hold_duration > 0.0
        assert state.total_state_duration > 0.0
        assert state.end_time > state.start_time
        prev_end = state.end_time

    assert timeline.total_duration >= prev_end


def test_content_aware_reading_time(parser, planner):
    short_heading_tex = r"\subsection*{Short}"
    long_explanation_tex = r"""
\subsection*{Longer Analysis}
This is a significantly more detailed explanation of why the mathematical transformation holds under continuous differentiability across the real domain, requiring the viewer to absorb several key sentences.
"""
    doc1 = parser.parse(short_heading_tex)
    doc2 = parser.parse(long_explanation_tex)
    
    tl1 = planner.plan(doc1)
    tl2 = planner.plan(doc2)
    
    # The paragraph state in tl2 must have a longer hold_duration than the short heading in tl1
    para_state = [s for s in tl2.states if s.new_element and s.new_element.type == ElementType.PARAGRAPH][0]
    heading_state = [s for s in tl1.states if s.new_element and s.new_element.type == ElementType.SUBSECTION][0]
    
    assert para_state.hold_duration > heading_state.hold_duration


def test_progressive_state_accumulation(parser, planner):
    tex = r"""
\section*{Progressive Lesson}
First paragraph.
Second paragraph.
Third paragraph.
"""
    doc = parser.parse(tex)
    timeline = planner.plan(doc)
    
    # In each state within a slide, visible_elements should monotonically increase
    scene_states = [s for s in timeline.states if s.scene_index == 0]
    for i in range(1, len(scene_states)):
        assert len(scene_states[i].visible_elements) == len(scene_states[i - 1].visible_elements) + 1


def test_slide_pagination(parser, planner):
    # Multiple sections should be partitioned into separate slides
    tex = r"""
\section*{Section One}
Content of section one.
\section*{Section Two}
Content of section two.
\section*{Section Three}
Content of section three.
"""
    doc = parser.parse(tex)
    timeline = planner.plan(doc)
    
    # At least 3 separate slide scenes
    assert len(timeline.scenes) >= 3
