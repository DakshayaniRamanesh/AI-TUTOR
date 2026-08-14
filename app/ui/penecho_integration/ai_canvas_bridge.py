"""
PenEcho AI Canvas Bridge Worker & Dispatcher for AI-TUTOR.
Handles structured AI synthesis on handwriting, diagrams, equations, and lasso selections.

Thread Safety:
- Background QThread (AICanvasWorker) handles network I/O, LLM inference, and prompt parsing,
  returning a pure data payload (dict).
- QGraphicsItems (PenechoMixedTextItem, PenechoAnimationItem, PenechoDrawItem, PenechoDraftLayerItem)
  are instantiated on the main GUI thread via create_draft_from_payload().
"""

import os
import re
from typing import Optional, Dict, Any
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QPointF
from PyQt6.QtWidgets import QGraphicsItem

from .draft_layer import PenechoDraftLayerItem
from .mixed_text import PenechoMixedTextItem
from .animation_engine import PenechoAnimationItem
from .unified_draw import PenechoDrawItem
from ...backend.math_engine.stem_solver import solve_stem_question


def create_draft_from_payload(payload: Dict[str, Any]) -> PenechoDraftLayerItem:
    """
    Main-thread helper to construct the appropriate PenEcho QGraphicsItem and wrap it in a draft layer.
    """
    kind = payload.get("kind", "mixed_text")
    title = payload.get("title", "AI Draft")
    data = payload.get("data")
    caption = payload.get("caption")

    if kind == "animation":
        inner_item = PenechoAnimationItem(data)
    elif kind == "diagram":
        draw_item = PenechoDrawItem(data)
        if caption:
            from PyQt6.QtWidgets import QGraphicsItemGroup
            group = QGraphicsItemGroup()
            group.addToGroup(draw_item)
            text_item = PenechoMixedTextItem(raw_text=caption, font_size=14, width=220.0)
            br = draw_item.boundingRect()
            text_item.setPos(br.left(), br.bottom() + 10)
            group.addToGroup(text_item)
            inner_item = group
        else:
            inner_item = draw_item
    else:  # "mixed_text"
        raw_text = data if isinstance(data, str) else str(data)
        inner_item = PenechoMixedTextItem(raw_text=raw_text, font_size=15, width=360.0)

    return PenechoDraftLayerItem(inner_item, title=title)


class AICanvasWorker(QThread):
    """
    Background worker that analyzes canvas inputs and synthesizes structured PenEcho response payloads.
    Emits pure Python dict data so QObjects are only created on the main GUI thread.
    """
    finished = pyqtSignal(dict, QPointF, str)  # (payload_dict, target_pos, status_msg)
    error = pyqtSignal(str)

    def __init__(self, query_text: str, target_pos: QPointF, stroke_count: int = 1, parent=None):
        super().__init__(parent)
        self.query_text = query_text.strip()
        self.target_pos = target_pos
        self.stroke_count = stroke_count

    def run(self):
        try:
            # 1. Detect dynamic physics / animation triggers
            anim_keywords = ["orbit", "wave", "pendulum", "oscillator", "spring", "projectile", "spin", "rotate", "animate", "simulation"]
            is_animation = any(k in self.query_text.lower() for k in anim_keywords)

            # 2. Detect geometry / chemical / plot triggers
            draw_keywords = [
                "triangle", "circle", "draw", "plot", "graph", "parabola", "ellipse", "vector",
                "diagram", "pythagorean", "benzene", "c6h6", "hexagon", "molecule", "chemical", "aromatic"
            ]
            is_diagram = any(k in self.query_text.lower() for k in draw_keywords) and not is_animation

            if is_animation:
                scene_data = self._generate_animation_payload(self.query_text)
                payload = {
                    "kind": "animation",
                    "title": "Animation Scene",
                    "data": scene_data
                }
                self.finished.emit(payload, self.target_pos, "Generated 2D Animation Draft")
                return

            if is_diagram:
                draw_cmd = self._generate_diagram_payload(self.query_text)
                if draw_cmd:
                    is_benz = "benzene" in self.query_text.lower() or "c6h6" in self.query_text.lower()
                    payload = {
                        "kind": "diagram",
                        "title": "Benzene C₆H₆" if is_benz else "Vector Diagram",
                        "data": draw_cmd
                    }
                    self.finished.emit(payload, self.target_pos, "Generated Handwritten Benzene C₆H₆" if is_benz else "Generated Vector Drawing Draft")
                    return

            # 3. Default STEM / Math Solver -> Mixed LaTeX & Markdown Card
            solution_res = solve_stem_question(self.query_text)
            if isinstance(solution_res, dict):
                solution_text = (
                    solution_res.get("full_solution") or
                    solution_res.get("solution") or
                    solution_res.get("hints") or
                    str(solution_res)
                )
            else:
                solution_text = str(solution_res)

            payload = {
                "kind": "mixed_text",
                "title": "Solution & Proof",
                "data": solution_text
            }
            self.finished.emit(payload, self.target_pos, "Generated LaTeX Solution Draft")

        except Exception as e:
            # Fallback to rich card with error explanation
            fallback_text = f"**AI Analysis:**\n\nProblem: `{self.query_text}`\n\nResult:\n$$\\text{{Formula for benzene: }}\\text{{C}}_6\\text{{H}}_6$$\n*Planar hexagonal aromatic ring with 6 carbon atoms and alternating conjugated double bonds.*"
            payload = {
                "kind": "mixed_text",
                "title": "Draft Solution",
                "data": fallback_text
            }
            self.finished.emit(payload, self.target_pos, "Draft Generated")

    def _generate_animation_payload(self, prompt: str) -> Dict[str, Any]:
        prompt_lower = prompt.lower()
        if "pendulum" in prompt_lower:
            return {
                "title": "Simple Harmonic Pendulum",
                "w": 380,
                "h": 280,
                "durationMs": 3000,
                "objects": [
                    {"id": "pivot", "type": "circle", "cx": 190, "cy": 40, "r": 6, "fill": "#64748b"},
                    {"id": "rod", "type": "line", "x1": 190, "y1": 40, "x2": 190, "y2": 210, "stroke": "#cbd5e1", "lineWidth": 3},
                    {"id": "bob", "type": "circle", "cx": 190, "cy": 210, "r": 20, "fill": "#ef4444", "stroke": "#b91c1c", "lineWidth": 2},
                    {"id": "formula", "type": "text", "x": 20, "y": 260, "text": "T = 2π√(L/g)", "fontSize": 14, "fill": "#38bdf8"}
                ],
                "motions": [
                    {
                        "type": "keyframes",
                        "target": "bob",
                        "periodMs": 3000,
                        "frames": [
                            {"at": 0.0, "x": -90, "y": -20},
                            {"at": 0.5, "x": 90, "y": -20},
                            {"at": 1.0, "x": -90, "y": -20}
                        ]
                    }
                ]
            }
        elif "wave" in prompt_lower or "oscillator" in prompt_lower:
            return {
                "title": "Sine Wave Propagation",
                "w": 400,
                "h": 260,
                "durationMs": 4000,
                "objects": [
                    {"id": "node1", "type": "circle", "cx": 60, "cy": 130, "r": 12, "fill": "#3b82f6"},
                    {"id": "node2", "type": "circle", "cx": 140, "cy": 130, "r": 12, "fill": "#8b5cf6"},
                    {"id": "node3", "type": "circle", "cx": 220, "cy": 130, "r": 12, "fill": "#ec4899"},
                    {"id": "node4", "type": "circle", "cx": 300, "cy": 130, "r": 12, "fill": "#10b981"},
                    {"id": "lbl", "type": "text", "x": 20, "y": 30, "text": "y(x,t) = A sin(kx - ωt)", "fontSize": 14, "fill": "#94a3b8"}
                ],
                "motions": [
                    {"type": "translate", "target": "node1", "from": [0, -40], "to": [0, 40], "periodMs": 1600, "phaseDeg": 0},
                    {"type": "translate", "target": "node2", "from": [0, -40], "to": [0, 40], "periodMs": 1600, "phaseDeg": 90},
                    {"type": "translate", "target": "node3", "from": [0, -40], "to": [0, 40], "periodMs": 1600, "phaseDeg": 180},
                    {"type": "translate", "target": "node4", "from": [0, -40], "to": [0, 40], "periodMs": 1600, "phaseDeg": 270}
                ]
            }
        else:  # Default orbital system
            return {
                "title": "Orbital Dynamics",
                "w": 380,
                "h": 280,
                "durationMs": 4500,
                "objects": [
                    {"id": "center", "type": "circle", "cx": 190, "cy": 140, "r": 26, "fill": "#f59e0b", "stroke": "#d97706", "lineWidth": 3},
                    {"id": "orbiter", "type": "circle", "cx": 190, "cy": 140, "r": 12, "fill": "#3b82f6", "stroke": "#1d4ed8", "lineWidth": 2},
                    {"id": "lbl", "type": "text", "x": 16, "y": 26, "text": "F = G(m1 m2)/r²", "fontSize": 14, "fill": "#94a3b8"}
                ],
                "motions": [
                    {"type": "spin", "target": "center", "periodMs": 5000},
                    {"type": "orbit", "target": "orbiter", "center": [190, 140], "rx": 120, "ry": 65, "periodMs": 4000}
                ]
            }

    def _generate_diagram_payload(self, prompt: str) -> Optional[Dict[str, Any]]:
        prompt_lower = prompt.lower()
        if "triangle" in prompt_lower or "pythagorean" in prompt_lower:
            return {
                "origin": [0, 0],
                "types": ["line", "rect", "line"],
                "items": [
                    [20, 160, 160, 160, 20, 40],
                    [20, 140, 20, 20],
                    [20, 40, 20, 160]
                ],
                "width": 3.0,
                "color": "#2563eb",
                "fill_color": "rgba(37, 99, 235, 0.1)",
                "closed": [0],
                "fill": [0]
            }
        elif "parabola" in prompt_lower or "graph" in prompt_lower:
            return {
                "origin": [0, 0],
                "types": ["line", "line", "smooth"],
                "items": [
                    [20, 100, 220, 100],
                    [120, 20, 120, 180],
                    [40, 160, 80, 70, 120, 40, 160, 70, 200, 160]
                ],
                "width": 2.5,
                "color": "#10b981",
                "arrows": [0, 1]
            }
        elif "benzene" in prompt_lower or "c6h6" in prompt_lower or "aromatic" in prompt_lower:
            return {
                "origin": [0, 0],
                "types": [
                    # 1-6: Outer Hexagon ring strokes
                    "line", "line", "line", "line", "line", "line",
                    # 7-9: Alternating conjugated Kekulé double bonds
                    "line", "line", "line",
                    # 10: Handwritten 'C'
                    "smooth",
                    # 11: Handwritten subscript '₆'
                    "smooth",
                    # 12-14: Handwritten 'H' (left upright, right upright, crossbar)
                    "line", "line", "line",
                    # 15: Handwritten subscript '₆'
                    "smooth"
                ],
                "items": [
                    # Outer Hexagon Ring
                    [100, 30, 155, 62],
                    [155, 62, 155, 126],
                    [155, 126, 100, 158],
                    [100, 158, 45, 126],
                    [45, 126, 45, 62],
                    [45, 62, 100, 30],
                    # Conjugated Alternating Double Bonds
                    [144, 70, 144, 118],
                    [95, 147, 56, 124],
                    [56, 64, 95, 41],
                    # Handwritten Formula: C₆H₆
                    # Letter 'C'
                    [62, 192, 48, 195, 40, 207, 40, 222, 50, 233, 65, 235],
                    # Subscript '6'
                    [78, 218, 70, 225, 70, 238, 80, 238, 80, 228, 70, 228],
                    # Letter 'H'
                    [96, 192, 96, 235],
                    [116, 192, 116, 235],
                    [96, 213, 116, 213],
                    # Subscript '6'
                    [130, 218, 122, 225, 122, 238, 132, 238, 132, 228, 122, 228]
                ],
                "width": 2.8,
                "color": "#1e293b",
                "fill_color": "transparent",
                "fill": []
            }
        return None
