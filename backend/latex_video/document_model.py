"""
Intermediate Representation (IR) Data Models for LaTeX Video Generation.

Provides a structured, semantic abstraction of educational LaTeX documents,
allowing the AnimationPlanner to reason about hierarchy, importance, complexity,
and progressive revealing without dealing with raw string markup.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


class ElementType(str, Enum):
    TITLE = "title"
    SECTION = "section"
    SUBSECTION = "subsection"
    SUBSUBSECTION = "subsubsection"
    PARAGRAPH = "paragraph"
    EQUATION_DISPLAY = "equation_display"
    EQUATION_STEP = "equation_step"
    BULLET_ITEM = "bullet_item"
    NUMBERED_ITEM = "numbered_item"
    BOXED_RESULT = "boxed_result"
    TABLE = "table"
    FIGURE = "figure"
    CALLOUT = "callout"


class ImportanceLevel(str, Enum):
    NORMAL = "normal"
    MEDIUM = "medium"
    HIGH = "high"


class TransitionType(str, Enum):
    FADE_IN = "fade_in"
    SLIDE_UP = "slide_up"
    WRITE_REVEAL = "write_reveal"
    BOX_HIGHLIGHT = "box_highlight"
    SCENE_DISSOLVE = "scene_dissolve"


@dataclass
class DocumentElement:
    """
    A discrete pedagogical element in the lesson document.
    """
    element_id: str
    type: ElementType
    raw_content: str
    clean_text: str = ""
    importance: ImportanceLevel = ImportanceLevel.NORMAL
    complexity_score: float = 1.0
    group_id: Optional[str] = None
    align_env: bool = False
    is_boxed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_latex_snippet(self) -> str:
        """Returns the formatted LaTeX snippet to represent this element in a slide."""
        content = self.raw_content.strip()
        if self.type == ElementType.TITLE:
            return f"{{\\Huge \\textbf{{{content}}}}}\n\\par\\vspace{{1.2em}}\n"
        elif self.type == ElementType.SECTION:
            return f"{{\\LARGE \\textbf{{{content}}}}}\n\\par\\vspace{{0.8em}}\n"
        elif self.type == ElementType.SUBSECTION:
            return f"{{\\Large \\textbf{{{content}}}}}\n\\par\\vspace{{0.5em}}\n"
        elif self.type == ElementType.SUBSUBSECTION:
            return f"{{\\large \\textbf{{{content}}}}}\n\\par\\vspace{{0.4em}}\n"
        elif self.type == ElementType.PARAGRAPH:
            return f"{content}\n\\par\\vspace{{0.8em}}\n"
        elif self.type == ElementType.EQUATION_DISPLAY:
            if not content.startswith("\\[") and not content.startswith("\\begin"):
                return f"\\[\n{content}\n\\]\n"
            return f"{content}\n"
        elif self.type == ElementType.EQUATION_STEP:
            return f"{content}\\\\"
        elif self.type == ElementType.BOXED_RESULT:
            if "\\boxed" in content or "\\begin{tcolorbox}" in content:
                return f"\\[\n{content}\n\\]\n"
            return f"\\[\n\\boxed{{{content}}}\n\\]\n"
        elif self.type in (ElementType.BULLET_ITEM, ElementType.NUMBERED_ITEM):
            return f"\\item {content}\n"
        return f"{content}\n"


@dataclass
class LessonSection:
    """A pedagogical section grouping related elements."""
    section_id: str
    title: str
    elements: List[DocumentElement] = field(default_factory=list)


@dataclass
class LessonDocument:
    """
    Root semantic representation of the educational lesson document.
    """
    title: str = "Lesson"
    sections: List[LessonSection] = field(default_factory=list)
    raw_source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def all_elements(self) -> List[DocumentElement]:
        """Flattened list of all document elements in sequential presentation order."""
        result: List[DocumentElement] = []
        for sec in self.sections:
            result.extend(sec.elements)
        return result

    def total_element_count(self) -> int:
        return sum(len(sec.elements) for sec in self.sections)
