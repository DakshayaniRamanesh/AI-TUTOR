"""
Narration Planner for Educational Video Voice-Over.

Converts the AnimationTimeline (produced by AnimationPlanner) into a
NarrationPlan: one NarrationSegment per SlideScene, each containing
natural, teacher-quality narration text (not raw LaTeX).

Design principles
-----------------
* Groups narration by SlideScene (one audio file per slide).
* Pedagogically rich: explains what each equation step represents,
  extracting teacher annotations and framing mathematical transitions clearly.
* Translates LaTeX symbols into clear spoken English (e.g. derivatives,
  fractions, exponents, limits, roots).
* Rule-based, fast, and completely deterministic (no external LLM latency).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .document_model import DocumentElement, ElementType, ImportanceLevel
from .animation_planner import AnimationTimeline, SlideScene


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class NarrationSegment:
    """Narration for a single SlideScene (one audio file)."""
    scene_index: int
    text: str                           # Full narration text for this scene
    audio_path: Optional[str] = None    # Set after TTS generation
    duration_seconds: float = 0.0       # Set after TTS generation


@dataclass
class NarrationPlan:
    """Complete narration plan for an educational video."""
    segments: List[NarrationSegment] = field(default_factory=list)

    def get_segment(self, scene_index: int) -> Optional[NarrationSegment]:
        for seg in self.segments:
            if seg.scene_index == scene_index:
                return seg
        return None


# ---------------------------------------------------------------------------
# LaTeX → English translator
# ---------------------------------------------------------------------------

class _LatexToSpeech:
    """
    Lightweight, rule-based translator for mathematical LaTeX -> spoken English.
    Translates mathematical notation, derivatives, fractions, powers, and
    symbols into fluent, conversational speech suitable for educational narration.
    """

    @classmethod
    def extract_annotations(cls, latex: str) -> Tuple[str, List[str]]:
        """
        Extract text commentary like '\\text{(differentiate y^2 with respect to y)}'
        returning the cleaned math string and the list of commentary sentences.
        """
        notes: List[str] = []
        
        def _replace_text(m: re.Match) -> str:
            content = m.group(1).strip()
            # Strip outer parens from notes like (note)
            cleaned_note = re.sub(r"^\((.+)\)$", r"\1", content).strip()
            if cleaned_note and len(cleaned_note) > 3:
                # Capitalize first letter and ensure ending period
                cleaned_note = cleaned_note[0].upper() + cleaned_note[1:]
                if not cleaned_note.endswith((".", "!", "?")):
                    cleaned_note += "."
                notes.append(cleaned_note)
            return " "

        math_without_notes = re.sub(
            r"\\text\{([^{}]+)\}",
            _replace_text,
            latex
        )
        return math_without_notes, notes

    @classmethod
    def translate(cls, latex: str) -> str:
        """Convert a LaTeX math string to a speakable English description."""
        math_str, notes = cls.extract_annotations(latex)
        result = math_str.strip()

        # Specific calculus patterns first
        result = re.sub(r"\\frac\{d\}\{d([a-zA-Z])\}", r"the derivative with respect to \1 of", result)
        result = re.sub(r"\\frac\{d([a-zA-Z])\}\{d([a-zA-Z])\}", r"d \1 by d \2", result)
        result = re.sub(r"\\frac\{\\partial\}\{\\partial([a-zA-Z])\}", r"the partial derivative with respect to \1 of", result)
        result = re.sub(r"\\frac\{\\partial([a-zA-Z])\}\{\\partial([a-zA-Z])\}", r"partial \1 by partial \2", result)

        # Standard fractions
        result = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"\1 over \2", result)

        # Roots
        result = re.sub(r"\\sqrt\[([^\]]+)\]\{([^{}]+)\}", r"the \1th root of \2", result)
        result = re.sub(r"\\sqrt\{([^{}]+)\}", r"the square root of \1", result)
        result = re.sub(r"\\sqrt\s+([A-Za-z0-9])", r"the square root of \1", result)

        # Common powers
        result = re.sub(r"\^\{2\}|\^2", " squared", result)
        result = re.sub(r"\^\{3\}|\^3", " cubed", result)
        result = re.sub(r"\^\{([^{}]+)\}", r" to the power of \1", result)
        result = re.sub(r"\^([a-zA-Z0-9])", r" to the power \1", result)

        # Subscripts
        result = re.sub(r"_\{([^{}]+)\}", r" sub \1", result)
        result = re.sub(r"_([a-zA-Z0-9])", r" sub \1", result)

        # Integrals and sums
        result = re.sub(r"\\int_\{([^{}]+)\}\^\{([^{}]+)\}", r"the integral from \1 to \2 of", result)
        result = re.sub(r"\\int", "the integral of", result)
        result = re.sub(r"\\sum_\{([^{}]+)\}\^\{([^{}]+)\}", r"the sum from \1 to \2 of", result)
        result = re.sub(r"\\sum", "the sum of", result)
        result = re.sub(r"\\lim_\{([^{}]+)\}", r"the limit as \1 of", result)

        # Operators & relations
        result = re.sub(r"\\pm", "plus or minus", result)
        result = re.sub(r"\\mp", "minus or plus", result)
        result = re.sub(r"\\times", " times ", result)
        result = re.sub(r"\\cdot", " times ", result)
        result = re.sub(r"\\div", " divided by ", result)
        result = re.sub(r"\\leq", " is less than or equal to ", result)
        result = re.sub(r"\\geq", " is greater than or equal to ", result)
        result = re.sub(r"\\neq", " is not equal to ", result)
        result = re.sub(r"\\approx", " is approximately ", result)
        result = re.sub(r"\\to|\\rightarrow", " approaches ", result)
        result = re.sub(r"\\infty", "infinity", result)

        # Equal sign to spoken form
        result = re.sub(r"\s*=\s*", " equals ", result)
        result = re.sub(r"\s*\+\s*", " plus ", result)
        result = re.sub(r"\s*-\s*", " minus ", result)

        # Greek symbols
        greek = {
            r"\\alpha": "alpha", r"\\beta": "beta", r"\\gamma": "gamma",
            r"\\delta": "delta", r"\\epsilon": "epsilon", r"\\theta": "theta",
            r"\\lambda": "lambda", r"\\mu": "mu", r"\\pi": "pi",
            r"\\sigma": "sigma", r"\\omega": "omega", r"\\Delta": "delta",
        }
        for pat, spoken in greek.items():
            result = re.sub(pat, spoken, result)

        # Strip remaining markup
        result = re.sub(r"\\(left|right|big|Big|bigg|Bigg)", "", result)
        result = re.sub(r"\\boxed\{([^{}]+)\}", r"\1", result)
        result = re.sub(r"\\(mathrm|mathbf|mathit|mathbb|mathcal|operatorname)\{([^{}]+)\}", r"\2", result)
        result = re.sub(r"[&\\\\]", " ", result)
        result = re.sub(r"\$+", "", result)
        result = re.sub(r"\\[a-zA-Z]+\*?", "", result)
        result = re.sub(r"[{}]", "", result)

        # Clean spacing
        result = re.sub(r"\s{2,}", " ", result).strip()

        # If we had notes extracted, attach them as natural commentary
        if notes:
            return " ".join(notes) + f" That gives: {result}" if result else " ".join(notes)

        return result


# ---------------------------------------------------------------------------
# Narration Planner
# ---------------------------------------------------------------------------

class NarrationPlanner:
    """
    Builds an educational NarrationPlan from an AnimationTimeline.
    Generates rich, teacher-quality spoken narration for each slide scene.
    """

    _SKIP_TYPES = frozenset({
        ElementType.TABLE,
        ElementType.FIGURE,
    })

    def plan(self, timeline: AnimationTimeline) -> NarrationPlan:
        """Produce one NarrationSegment per SlideScene with pedagogical narration."""
        narration_plan = NarrationPlan()

        for scene in timeline.scenes:
            text = self._narrate_scene(scene)
            if text.strip():
                narration_plan.segments.append(
                    NarrationSegment(scene_index=scene.scene_index, text=text)
                )

        return narration_plan

    def _narrate_scene(self, scene: SlideScene) -> str:
        """Compose the full teacher narration for an entire SlideScene."""
        parts: List[str] = []
        seen: set[str] = set()

        # Step counter for derivation variety
        step_index = 0

        for elem in scene.elements:
            if elem.element_id in seen or elem.type in self._SKIP_TYPES:
                continue
            seen.add(elem.element_id)

            if elem.type == ElementType.EQUATION_STEP:
                step_index += 1

            sentence = self._narrate_element(elem, step_index=step_index, scene=scene)
            if sentence:
                parts.append(sentence)

        # Combine into cohesive monologue
        full_text = "  ".join(parts).strip()
        # Clean any awkward double punctuation
        full_text = re.sub(r"\s+([.,;:!?])", r"\1", full_text)
        full_text = re.sub(r"\.{2,}", ".", full_text)
        return full_text

    def _narrate_element(
        self,
        elem: DocumentElement,
        step_index: int = 0,
        scene: Optional[SlideScene] = None,
    ) -> str:
        """Convert a single DocumentElement to an educational spoken explanation."""
        t = elem.type

        if t == ElementType.TITLE:
            title = self._clean(elem.clean_text)
            return f"Welcome to this lesson on {title}. Today, we will explore this concept step by step."

        if t == ElementType.SECTION:
            title = self._clean(elem.clean_text)
            if not title or title.lower() in ("introduction", "overview"):
                return "Let's begin by looking at the core ideas."
            return f"In this section, we focus on {title}."

        if t == ElementType.SUBSECTION:
            title = self._clean(elem.clean_text)
            return f"Let's look at {title}." if title else ""

        if t == ElementType.SUBSUBSECTION:
            title = self._clean(elem.clean_text)
            return f"Next, consider {title}." if title else ""

        if t == ElementType.PARAGRAPH:
            text = self._clean(elem.clean_text or elem.raw_content)
            if len(text) > 6:
                if not text.endswith((".", "!", "?")):
                    text += "."
                return text
            return ""

        if t == ElementType.EQUATION_DISPLAY:
            # Check for embedded annotation commentary
            _, notes = _LatexToSpeech.extract_annotations(elem.raw_content)
            spoken = _LatexToSpeech.translate(elem.raw_content)
            if spoken:
                if not spoken.endswith((".", "!", "?")):
                    spoken += "."
                if notes:
                    return spoken
                return f"We start with the equation: {spoken}"
            return ""

        if t == ElementType.EQUATION_STEP:
            # Check for commentary notes in the step (e.g. power rule, chain rule)
            _, notes = _LatexToSpeech.extract_annotations(elem.raw_content)
            # Skip trivial low-complexity steps without teacher annotations
            if elem.complexity_score < 1.0 and not notes:
                return ""

            spoken = _LatexToSpeech.translate(elem.raw_content)
            if not spoken:
                return ""
            if not spoken.endswith((".", "!", "?")):
                spoken += "."

            if notes:
                # If the step already has explicit teacher notes, use them directly!
                return spoken

            # Connective transitions for steps
            connectors = [
                "Taking the next step, we have:",
                "Applying the rules of differentiation, we get:",
                "Next, simplifying the terms gives:",
                "Now, isolating the unknown yields:",
                "Continuing the derivation, we find:",
            ]
            connector = connectors[(step_index - 1) % len(connectors)]
            return f"{connector} {spoken}"

        if t == ElementType.BOXED_RESULT:
            spoken = _LatexToSpeech.translate(elem.raw_content)
            if spoken:
                if not spoken.endswith((".", "!", "?")):
                    spoken += "."
                return f"Bringing it all together, our final result is: {spoken}"
            return ""

        if t in (ElementType.BULLET_ITEM, ElementType.NUMBERED_ITEM):
            text = self._clean(elem.clean_text or elem.raw_content)
            if text:
                if not text.endswith((".", "!", "?")):
                    text += "."
                return f"Notice that {text}"
            return ""

        if t == ElementType.CALLOUT:
            text = self._clean(elem.clean_text or elem.raw_content)
            if text:
                if not text.endswith((".", "!", "?")):
                    text += "."
                return f"Key takeaway: {text}"
            return ""

        return ""

    @staticmethod
    def _clean(text: str) -> str:
        """Strip residual LaTeX markup and normalise whitespace for TTS."""
        if not text:
            return ""
        cleaned = re.sub(r"\\[a-zA-Z]+\*?\{[^{}]*\}", "", text)
        cleaned = re.sub(r"\\[a-zA-Z]+\*?", "", cleaned)
        cleaned = re.sub(r"[{}$]", "", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        return cleaned.strip()
