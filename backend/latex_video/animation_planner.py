"""
Animation Planner for LaTeX-Based Educational Video.

Transforms the semantic LessonDocument intermediate representation into a
chronological animation timeline consisting of progressive document states,
content-aware reading intervals, and professional educational transitions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from .document_model import (
    ElementType,
    ImportanceLevel,
    TransitionType,
    DocumentElement,
    LessonSection,
    LessonDocument,
)


@dataclass
class TimelineState:
    """
    Represents one discrete temporal state in the video.
    In this state, `visible_elements` are rendered on the slide.
    `new_element` is the element introduced in this state.
    """
    state_index: int
    scene_index: int
    visible_elements: List[DocumentElement]
    new_element: Optional[DocumentElement]
    start_time: float
    transition_duration: float
    hold_duration: float
    transition_type: TransitionType
    pause_after: float = 0.0

    @property
    def total_state_duration(self) -> float:
        return self.transition_duration + self.hold_duration + self.pause_after

    @property
    def end_time(self) -> float:
        return self.start_time + self.total_state_duration


@dataclass
class SlideScene:
    """
    A logical visual slide containing a bounded group of elements.
    Prevents text overflowing 16:9 presentation bounds.
    """
    scene_index: int
    title: str
    elements: List[DocumentElement] = field(default_factory=list)


@dataclass
class AnimationTimeline:
    """The master timeline containing all progressive states in chronological order."""
    states: List[TimelineState] = field(default_factory=list)
    scenes: List[SlideScene] = field(default_factory=list)
    total_duration: float = 0.0

    def get_state_at(self, timestamp: float) -> Optional[TimelineState]:
        for st in self.states:
            if st.start_time <= timestamp <= st.end_time:
                return st
        return self.states[-1] if self.states else None


class AnimationPlanner:
    """Plans slide layout, progressive states, and timing from a LessonDocument."""

    def __init__(self, target_fps: int = 30):
        self.fps = target_fps

    def plan(self, document: LessonDocument) -> AnimationTimeline:
        """Main entry point: converts LessonDocument to AnimationTimeline."""
        # 1. Paginate elements into 16:9 Slide Scenes
        scenes = self._paginate_into_scenes(document)
        
        timeline = AnimationTimeline(scenes=scenes)
        current_time = 0.0
        state_idx = 0

        # 2. For each scene, build progressive states (State 1..K)
        for scene in scenes:
            scene_visible: List[DocumentElement] = []
            
            for elem_idx, elem in enumerate(scene.elements):
                scene_visible.append(elem)
                
                # Compute content-aware duration and transition
                t_duration = self._calculate_transition_duration(elem)
                h_duration = self._calculate_hold_duration(elem)
                p_after = self._calculate_pause_after(elem, is_last_in_scene=(elem_idx == len(scene.elements) - 1))
                t_type = self._determine_transition_type(elem)

                state = TimelineState(
                    state_index=state_idx,
                    scene_index=scene.scene_index,
                    visible_elements=list(scene_visible),
                    new_element=elem,
                    start_time=current_time,
                    transition_duration=t_duration,
                    hold_duration=h_duration,
                    transition_type=t_type,
                    pause_after=p_after
                )
                
                timeline.states.append(state)
                current_time += state.total_state_duration
                state_idx += 1

            # Inter-scene transition pause
            current_time += 0.5

        timeline.total_duration = current_time
        return timeline

    def _paginate_into_scenes(self, document: LessonDocument) -> List[SlideScene]:
        """
        Groups document elements into slides so that no slide overflows 16:9 canvas.
        Starts a new slide when:
        - A major new Section begins (and previous slide already has content)
        - The visual weight of elements on the current slide exceeds slide capacity
        """
        scenes: List[SlideScene] = []
        current_scene = SlideScene(scene_index=0, title=document.title)
        current_weight = 0.0
        MAX_SLIDE_WEIGHT = 7.0  # Normalized weight capacity for 16:9 slide

        for sec in document.sections:
            for elem in sec.elements:
                elem_weight = self._element_visual_weight(elem)
                
                # Rule 1: A major SECTION starts a new slide if current slide already has content
                is_major_section = (elem.type == ElementType.SECTION)
                # Rule 2: Slide weight overflow
                will_overflow = (current_weight + elem_weight > MAX_SLIDE_WEIGHT and len(current_scene.elements) >= 2)

                if (is_major_section and len(current_scene.elements) > 0) or will_overflow:
                    scenes.append(current_scene)
                    current_scene = SlideScene(
                        scene_index=len(scenes),
                        title=elem.clean_text if is_major_section else current_scene.title
                    )
                    current_weight = 0.0

                current_scene.elements.append(elem)
                current_weight += elem_weight

        if current_scene.elements:
            scenes.append(current_scene)

        return scenes

    def _element_visual_weight(self, elem: DocumentElement) -> float:
        """Estimates vertical screen space occupied by an element."""
        if elem.type == ElementType.TITLE:
            return 2.5
        elif elem.type == ElementType.SECTION:
            return 2.0
        elif elem.type == ElementType.SUBSECTION:
            return 1.4
        elif elem.type == ElementType.SUBSUBSECTION:
            return 1.0
        elif elem.type == ElementType.PARAGRAPH:
            words = len(elem.clean_text.split())
            return max(1.2, min(3.0, words / 18.0))
        elif elem.type == ElementType.EQUATION_DISPLAY:
            return 2.2
        elif elem.type == ElementType.EQUATION_STEP:
            return 1.0
        elif elem.type == ElementType.BOXED_RESULT:
            return 2.5
        elif elem.type in (ElementType.BULLET_ITEM, ElementType.NUMBERED_ITEM):
            return 0.9
        elif elem.type == ElementType.TABLE:
            return 3.0
        return 1.5

    def _calculate_transition_duration(self, elem: DocumentElement) -> float:
        """Determines the smooth entrance animation duration for an element."""
        if elem.type in (ElementType.TITLE, ElementType.SECTION):
            return 0.6
        elif elem.type == ElementType.SUBSECTION:
            return 0.5
        elif elem.type in (ElementType.EQUATION_DISPLAY, ElementType.EQUATION_STEP):
            return 0.6
        elif elem.type == ElementType.BOXED_RESULT:
            return 0.7
        return 0.45

    def _calculate_hold_duration(self, elem: DocumentElement) -> float:
        """
        Calculates content-aware reading/comprehension time.
        Based on natural human reading rates (~200 words/minute) and
        cognitive load for equations and derivations.
        """
        if elem.type == ElementType.TITLE:
            return 2.2
        elif elem.type == ElementType.SECTION:
            return 2.0
        elif elem.type in (ElementType.SUBSECTION, ElementType.SUBSUBSECTION):
            return 1.8
        elif elem.type == ElementType.PARAGRAPH:
            word_count = len(elem.clean_text.split())
            # ~0.28 seconds per word
            reading_time = word_count * 0.28
            return max(2.5, min(7.0, reading_time))
        elif elem.type == ElementType.EQUATION_DISPLAY:
            # Display equation: 3.5s base + complexity scale
            return max(3.5, min(6.5, 2.5 * elem.complexity_score))
        elif elem.type == ElementType.EQUATION_STEP:
            # Step in aligned derivation: 2.2s - 4.5s
            return max(2.2, min(4.5, 1.8 * elem.complexity_score))
        elif elem.type == ElementType.BOXED_RESULT:
            # Key result / boxed answer: give student time to absorb
            return max(4.5, min(7.5, 3.2 * elem.complexity_score))
        elif elem.type in (ElementType.BULLET_ITEM, ElementType.NUMBERED_ITEM):
            word_count = len(elem.clean_text.split())
            return max(2.0, min(4.5, word_count * 0.3))
        elif elem.type == ElementType.TABLE:
            return 4.5
        return 3.0

    def _calculate_pause_after(self, elem: DocumentElement, is_last_in_scene: bool) -> float:
        """Pedagogical pause after critical conclusions or section endings."""
        if elem.importance == ImportanceLevel.HIGH or elem.type == ElementType.BOXED_RESULT:
            return 1.0  # Pause after key theorem or boxed solution
        if is_last_in_scene:
            return 0.8  # Pause before turning slide
        return 0.2

    def _determine_transition_type(self, elem: DocumentElement) -> TransitionType:
        """Selects the cleanest, most professional transition for each element."""
        if elem.type in (ElementType.TITLE, ElementType.SECTION):
            return TransitionType.SLIDE_UP
        elif elem.type in (ElementType.EQUATION_DISPLAY, ElementType.EQUATION_STEP):
            return TransitionType.WRITE_REVEAL
        elif elem.type == ElementType.BOXED_RESULT:
            return TransitionType.BOX_HIGHLIGHT
        return TransitionType.FADE_IN
