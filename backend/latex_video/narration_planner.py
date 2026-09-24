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

import json
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

import backend.config as config
from .document_model import DocumentElement, ElementType, ImportanceLevel
from .animation_planner import AnimationTimeline, SlideScene, TimelineState


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class NarrationSegment:
    """Narration for a single SlideScene or TimelineState frame."""
    scene_index: int
    text: str                           # Full narration text for this segment
    audio_path: Optional[str] = None    # Set after TTS generation
    duration_seconds: float = 0.0       # Set after TTS generation
    frame_index: int = 0                # 1-indexed progressive frame number (0 if scene-level)


@dataclass
class NarrationPlan:
    """Complete narration plan for an educational video."""
    segments: List[NarrationSegment] = field(default_factory=list)

    def get_segment(self, scene_index: int) -> Optional[NarrationSegment]:
        for seg in self.segments:
            if seg.scene_index == scene_index:
                return seg
        return None

    def get_segment_by_frame(self, frame_index: int) -> Optional[NarrationSegment]:
        for seg in self.segments:
            if seg.frame_index == frame_index:
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
        result = re.sub(r"\\forall", "for all", result)
        result = re.sub(r"\\exists", "there exists", result)
        result = re.sub(r"\\in", " in ", result)
        result = re.sub(r"\\notin", " not in ", result)
        result = re.sub(r"\\subset", " is a subset of ", result)
        result = re.sub(r"\\cup", " union ", result)
        result = re.sub(r"\\cap", " intersection ", result)
        result = re.sub(r"\\sin", " sine ", result)
        result = re.sub(r"\\cos", " cosine ", result)
        result = re.sub(r"\\tan", " tangent ", result)

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
# Frame Descriptors Extractor
# ---------------------------------------------------------------------------

def extract_frame_descriptors(timeline: AnimationTimeline) -> List[Dict[str, Any]]:
    """
    Extracts structured pedagogical metadata for every progressive frame (TimelineState).
    Returns a list of dicts:
      [
        {
          "frame": 1,
          "scene_index": 0,
          "scene_title": "Newton's Second Law",
          "element_type": "title",
          "content": "Newton's Second Law of Motion",
          "context": "Slide: Newton's Second Law",
        },
        ...
      ]
    """
    descriptors: List[Dict[str, Any]] = []
    scenes_by_index = {sc.scene_index: sc for sc in timeline.scenes}

    for idx, state in enumerate(timeline.states):
        frame_num = idx + 1
        scene = scenes_by_index.get(state.scene_index)
        scene_title = scene.title if scene else f"Slide {state.scene_index + 1}"

        elem = state.new_element
        if elem:
            elem_type = elem.type.value if hasattr(elem.type, "value") else str(elem.type)
            raw = (elem.raw_content or "").strip()
            clean = (elem.clean_text or "").strip()

            if elem.type in (ElementType.EQUATION_DISPLAY, ElementType.EQUATION_STEP, ElementType.BOXED_RESULT):
                math_spoken = _LatexToSpeech.translate(raw)
                content = f"{raw} (Spoken guidance: {math_spoken})" if math_spoken else raw
            else:
                content = clean or raw
        else:
            elem_type = "scene_overview"
            content = f"Slide introduction: {scene_title}"

        # Context summary of what has already been shown on this slide
        prior_elements = []
        for prev_elem in state.visible_elements:
            if elem and prev_elem.element_id == elem.element_id:
                continue
            prev_summary = prev_elem.clean_text or prev_elem.raw_content
            if prev_summary:
                prior_elements.append(prev_summary.strip()[:60])

        context_str = f"Slide: {scene_title}"
        if prior_elements:
            context_str += f" | Prior on slide: {'; '.join(prior_elements[-2:])}"

        descriptors.append({
            "frame": frame_num,
            "scene_index": state.scene_index,
            "scene_title": scene_title,
            "element_type": elem_type,
            "content": content,
            "context": context_str,
        })

    return descriptors


# ---------------------------------------------------------------------------
# LLM Narration Planner
# ---------------------------------------------------------------------------

class LLMNarrationPlanner:
    """
    Generates intelligent, frame-by-frame teacher narration using Groq or Gemini.
    Transforms raw visual frame content (Frame n: content x) into intuitive,
    pedagogical voiceover scripts without reading LaTeX syntax.
    """

    def __init__(self):
        pass
    def build_prompt(self, descriptors: List[Dict[str, Any]], lesson_title: str = "") -> str:
        """Constructs a structured pedagogical prompt with all frame information."""
        frames_text = []
        for d in descriptors:
            num = d["frame"]
            scene = d.get("scene_title", "")
            etype = d.get("element_type", "element")
            content = d.get("content", "")
            if num == 1 or etype in ("title", "section"):
                note = " [INTRODUCTORY HEADING - MUST BE STRICTLY 5 TO 10 WORDS / 2-3 SECONDS SO CONTENT REVEALS RAPIDLY]"
            else:
                note = ""
            frames_text.append(f"Frame {num} [Slide: {scene} | {etype}]{note}: {content}")

        frames_str = "\n".join(frames_text)
        max_words = getattr(config, "NARRATION_MAX_WORDS_PER_FRAME", 25)

        # Detect intent from the lesson title and frame content to set narrator style
        combined_hint = f"{lesson_title} {frames_str}".lower()
        # Algorithm / process
        if any(kw in combined_hint for kw in ["algorithm", "sort", "bfs", "dfs", "dynamic programming",
                                               "photosynthesis", "krebs", "process", "procedure", "how does"]):
            intent = "algorithm"
        # Formal proof
        elif any(kw in combined_hint for kw in ["prove", "proof", "lemma", "theorem", "corollary",
                                                  "by induction", "q.e.d", "irrational"]):
            intent = "proof"
        # Problem solving
        elif any(kw in combined_hint for kw in ["solve", "solution", "find the", "calculate", "boxed",
                                                  "step-by-step solution", "final answer"]):
            intent = "problem"
        else:
            # Default: theory / conceptual explanation
            intent = "theory"

        # Mode-specific narration guidance
        if intent == "theory":
            mode_instructions = (
                "CONTENT TYPE: CONCEPTUAL EXPLANATION / THEORY\n"
                "- Your goal is to EXPLAIN and BUILD INTUITION. Speak like an enthusiastic professor illuminating a concept.\n"
                "- For definition frames: Explain what it IS and WHY it matters in vivid, relatable terms. Use analogies.\n"
                "- For formula/equation frames: Translate each symbol into plain language, then say what the equation tells us physically or mathematically.\n"
                "- For property/application frames: Tell a brief story about a real-world context where this applies.\n"
                "- NEVER sound like you're just listing facts. Make the student feel the insight."
            )
        elif intent == "proof":
            mode_instructions = (
                "CONTENT TYPE: MATHEMATICAL PROOF\n"
                "- Your goal is to guide the student through rigorous logical reasoning.\n"
                "- For theorem frames: State the claim in plain English before the formal statement.\n"
                "- For derivation frames: Explain the logical REASON for each step, not just the algebraic manipulation.\n"
                "- Use language like: 'This step works because...', 'Notice that...', 'The key insight here is...'.\n"
                "- For conclusion frames: Summarize what has been established and why it's significant."
            )
        elif intent == "algorithm":
            mode_instructions = (
                "CONTENT TYPE: ALGORITHM / PROCESS / PROCEDURE\n"
                "- Your goal is to walk the student through a step-by-step procedure with clarity.\n"
                "- For overview frames: Explain the GOAL of the algorithm and the central trick or insight.\n"
                "- For step frames: Describe what is happening in plain English—not just restating the text.\n"
                "- For complexity/property frames: Connect the complexity result to the algorithm's behavior.\n"
                "- Use active language: 'Now we compare...', 'At each step, we halve the search space...'"
            )
        else:  # problem
            mode_instructions = (
                "CONTENT TYPE: PROBLEM SOLVING / WORKED EXAMPLE\n"
                "- Your goal is to coach the student through a solution step by step.\n"
                "- For problem setup frames: Briefly orient the student: what are we given, what do we want?\n"
                "- For derivation frames: Explain WHAT algebraic/calculus operation is being done and WHY.\n"
                "- For final answer frames: Celebrate the result, state it clearly, and optionally sanity-check it.\n"
                "- Use coaching language: 'Let's isolate x by...', 'Substituting back, we find...'"
            )

        return f"""You are an active, warm, and expressive STEM educator and video narrator.
We are producing an animated whiteboard/slide educational video.
Below is the chronological frame-by-frame breakdown of the visual lesson (from Frame 1 to Frame {len(descriptors)}).
In each frame, a new equation, derivation step, definition, or visual element appears on screen.

LESSON TOPIC: {lesson_title or 'Educational Lesson'}

{mode_instructions}

FRAME SEQUENCE:
{frames_str}

YOUR TASK:
Write an active, expressive, warm, and professional teacher narration script for EACH frame (Frame 1 through Frame {len(descriptors)}).

CRITICAL PACING & PEDAGOGICAL INSTRUCTIONS:
1. RAPID 2-3 SECOND DELIVERY FOR HEADINGS & PROBLEM STATEMENTS (FRAME 1):
   - For Frame 1 (Title, Section, or Problem Introduction): Keep the narration EXTREMELY BRIEF and punchy (strictly 5 to 10 words, ~2 to 3 seconds of speech, e.g. "Let's explore Newton's Second Law." or "Today, we prove this classic result.").
   - CRITICAL REQUIREMENT: Never give a long monologue or pause on an introductory heading! The viewer MUST see the actual working content appear within 2 to 3 seconds!
2. WARM, ACTIVE, AND PROFESSIONAL TONE:
   - Speak with lively, enthusiastic energy—warm, natural, and expressive (neither robotic nor overly hyped).
   - For working equation steps, explain the mathematical step or intuition in 1 clear, active sentence (about 10 to {max_words} words, ~3 to 5 seconds).
   - Use active phrasing (e.g. "Subtracting two from both sides isolates the squared term.").
3. NEVER READ VERBATIM OR UTTER LATEX:
   - Never simply read formulas or text verbatim off the screen.
   - Never say LaTeX syntax, backslashes, "frac", "sqrt", "begin", "end", "section", or braces.
   - Describe all math fluently in natural spoken English.
4. NUMBERING & COMPLETENESS:
   - Provide an entry for EVERY frame from 1 to {len(descriptors)} matching the frame numbers exactly. Do not skip any frame.

OUTPUT FORMAT:
Respond ONLY with a JSON object in this exact schema (no markdown fences, no other text):
{{
  "frames": [
    {{"frame": 1, "narration": "..."}},
    {{"frame": 2, "narration": "..."}}
  ]
}}
"""


    def generate_narration_scripts(
        self,
        descriptors: List[Dict[str, Any]],
        lesson_title: str = "",
    ) -> Dict[int, str]:
        """
        Calls LLM to generate frame-by-frame narration.
        Returns a mapping of {frame_number: narration_text}.
        """
        if not descriptors:
            return {}

        prompt = self.build_prompt(descriptors, lesson_title=lesson_title)
        try:
            from shared.ai_client import ai_client
            response_text = ai_client.generate_content(
                prompt,
                system_instruction="You are an expert educational scriptwriter."
            )
        except Exception as e:
            print(f"[NarrationPlanner] Generation failed: {e}")
            response_text = ""

        if not response_text:
            return {}

        return self.parse_narration_json(response_text)

    def parse_narration_json(self, raw_text: str) -> Dict[int, str]:
        """Parses LLM JSON response and maps frame numbers to narration strings."""
        if not raw_text or not raw_text.strip():
            return {}

        cleaned = re.sub(r"^```(?:json)?", "", raw_text.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"```$", "", cleaned.strip(), flags=re.MULTILINE).strip()

        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return {}

        try:
            data = json.loads(match.group(0))
            frames = data.get("frames", [])
            result: Dict[int, str] = {}
            for item in frames:
                if isinstance(item, dict) and "frame" in item and "narration" in item:
                    try:
                        f_num = int(item["frame"])
                        text = str(item["narration"]).strip()
                        if text:
                            text = re.sub(r"\s+([.,;:!?])", r"\1", text)
                            text = re.sub(r"\.{2,}", ".", text)
                            result[f_num] = text
                    except (ValueError, TypeError):
                        continue
            return result
        except Exception as err:
            print(f"[LLMNarration] JSON parse error: {err}")
            return {}


# ---------------------------------------------------------------------------
# Narration Planner
# ---------------------------------------------------------------------------

class NarrationPlanner:
    """
    Builds an educational NarrationPlan from an AnimationTimeline.
    Supports both:
    1. Intelligent frame-by-frame LLM teacher narration (default for video jobs)
    2. Slide-scene based heuristic narration (legacy / fallback)
    """

    _SKIP_TYPES = frozenset({
        ElementType.TABLE,
        ElementType.FIGURE,
    })

    def __init__(self):
        self.llm_planner = LLMNarrationPlanner()

    def plan(
        self,
        timeline: AnimationTimeline,
        by_frame: Optional[bool] = None,
        lesson_title: str = "",
    ) -> NarrationPlan:
        """
        Produce a NarrationPlan from the timeline.
        If by_frame is None, dynamically plans by frame when timeline states exist
        and have elements, or by scene if states have no new_elements.
        """
        if by_frame is None:
            by_frame = any(st.new_element is not None for st in timeline.states)

        if by_frame and timeline.states:
            return self.plan_frames(timeline, lesson_title=lesson_title)
        return self.plan_scenes(timeline)

    def plan_frames(
        self,
        timeline: AnimationTimeline,
        lesson_title: str = "",
    ) -> NarrationPlan:
        """
        Frame-by-frame educational teacher narration:
        1. Extract descriptors for Frame 1 to N
        2. Ask LLM for pedagogical commentary
        3. Parse JSON scripts matching frame numbers
        4. Fall back to heuristic rule-based commentary for missing frames
        """
        descriptors = extract_frame_descriptors(timeline)
        if not descriptors:
            return NarrationPlan()

        llm_scripts = self.llm_planner.generate_narration_scripts(
            descriptors, lesson_title=lesson_title
        )

        plan = NarrationPlan()
        for idx, state in enumerate(timeline.states):
            frame_num = idx + 1
            narration_text = llm_scripts.get(frame_num, "").strip()

            if not narration_text:
                # Fallback to heuristic narration for this frame
                if state.new_element:
                    narration_text = self._narrate_element(
                        state.new_element, step_index=idx + 1
                    )
                if not narration_text:
                    scene_title = timeline.scenes[state.scene_index].title if state.scene_index < len(timeline.scenes) else ""
                    narration_text = f"Here we focus on {scene_title}." if scene_title else "Let's explore this step."

            plan.segments.append(
                NarrationSegment(
                    scene_index=state.scene_index,
                    text=narration_text,
                    frame_index=frame_num,
                )
            )

        return plan

    def plan_scenes(self, timeline: AnimationTimeline) -> NarrationPlan:
        """Produce one NarrationSegment per SlideScene with pedagogical narration (legacy)."""
        narration_plan = NarrationPlan()
        for scene in timeline.scenes:
            text = self._narrate_scene(scene)
            if text.strip():
                narration_plan.segments.append(
                    NarrationSegment(scene_index=scene.scene_index, text=text, frame_index=0)
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
            return f"Welcome to our lesson on {title}."

        if t == ElementType.SECTION:
            title = self._clean(elem.clean_text)
            if not title or title.lower() in ("introduction", "overview"):
                return "Let's begin."
            return f"In this section, we explore {title}."

        if t == ElementType.SUBSECTION:
            title = self._clean(elem.clean_text)
            return f"Let's look at {title}." if title else ""

        if t == ElementType.SUBSUBSECTION:
            title = self._clean(elem.clean_text)
            return f"Next, consider {title}." if title else ""

        if t == ElementType.PARAGRAPH:
            text = self._clean(elem.clean_text or elem.raw_content)
            if step_index == 1:
                return "Let's solve this problem step by step."
            if len(text) > 6:
                words = text.split()
                if len(words) > 15:
                    text = " ".join(words[:15]) + "."
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
