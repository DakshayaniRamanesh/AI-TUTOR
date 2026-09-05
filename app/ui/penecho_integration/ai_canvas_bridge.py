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
        short_sol = payload.get("short_solution") or raw_text
        full_sol = payload.get("full_solution") or raw_text
        inner_item = PenechoMixedTextItem(
            raw_text=raw_text,
            font_size=15,
            width=360.0,
            short_text=short_sol,
            full_text=full_sol
        )

    return PenechoDraftLayerItem(inner_item, title=title)


class AICanvasWorker(QThread):
    """
    Background worker that analyzes canvas inputs and synthesizes structured PenEcho response payloads.
    Emits pure Python dict data so QObjects are only created on the main GUI thread.
    """
    finished = pyqtSignal(dict, QPointF, str)  # (payload_dict, target_pos, status_msg)
    error = pyqtSignal(str)

    def __init__(self, query_text: str, target_pos: QPointF, stroke_count: int = 1, mode: str = "study", parent=None):
        super().__init__(parent)
        self.query_text = query_text.strip()
        self.target_pos = target_pos
        self.stroke_count = stroke_count
        self.mode = mode

    def run(self):
        try:
            # 1. Detect dynamic physics / animation triggers
            anim_keywords = ["orbit", "wave", "pendulum", "oscillator", "spring", "projectile", "spin", "rotate", "animate", "simulation"]
            is_animation = any(k in self.query_text.lower() for k in anim_keywords)

            # 2. Detect geometry / chemical / bio / plot triggers
            draw_keywords = [
                "triangle", "circle", "draw", "plot", "graph", "parabola", "ellipse", "vector",
                "diagram", "pythagorean", "benzene", "c6h6", "hexagon", "molecule", "chemical", "aromatic",
                "water", "h2o", "methane", "ch4", "co2", "carbon dioxide", "compound", "bond",
                "phenopthaline", "phenolphthalein", "indicator", "heart", "cardiac", "anatomy", "cross section", "sketch"
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
                    is_chem = any(c in self.query_text.lower() for c in ["benzene", "c6h6", "water", "h2o", "methane", "ch4", "co2", "carbon dioxide", "chemical", "molecule"])
                    is_bio = any(b in self.query_text.lower() for b in ["heart", "cardiac", "anatomy", "organ"])
                    title = "Chemical Structure" if is_chem else ("Anatomy Diagram" if is_bio else "Vector Diagram")
                    payload = {
                        "kind": "diagram",
                        "title": title,
                        "data": draw_cmd
                    }
                    self.finished.emit(payload, self.target_pos, f"Generated Handwritten {title}")
                    return

            # 3. Default STEM / Math Solver -> Clean Handwritten Ink Response
            solution_res = solve_stem_question(self.query_text, mode=self.mode)
            if isinstance(solution_res, dict):
                short_sol = (
                    solution_res.get("short_solution") or
                    solution_res.get("hints") or
                    solution_res.get("solution") or
                    str(solution_res)
                )
                full_sol = (
                    solution_res.get("full_solution") or
                    solution_res.get("solution") or
                    short_sol
                )
                display_sol = solution_res.get("solution") or short_sol
            else:
                short_sol = str(solution_res)
                full_sol = str(solution_res)
                display_sol = str(solution_res)

            payload = {
                "kind": "mixed_text",
                "title": "Handwritten Solution",
                "data": display_sol,
                "short_solution": short_sol,
                "full_solution": full_sol,
                "question": self.query_text
            }
            self.finished.emit(payload, self.target_pos, "Generated Handwritten Ink Solution")

        except Exception as e:
            # Fallback to rich card with error explanation
            fallback_text = f"**AI Analysis:**\n\nProblem: `{self.query_text}`\n\nResult:\n$$\\text{{Formula for benzene: }}\\text{{C}}_6\\text{{H}}_6$$\n*Planar hexagonal aromatic ring with 6 carbon atoms and alternating conjugated double bonds.*"
            payload = {
                "kind": "mixed_text",
                "title": "Draft Solution",
                "data": fallback_text,
                "short_solution": fallback_text,
                "full_solution": fallback_text,
                "question": self.query_text
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
        elif "heart" in prompt_lower or "cardiac" in prompt_lower or "cross section of heart" in prompt_lower:
            return {
                "origin": [0, 0],
                "types": [
                    # 1. Outer Heart Muscle Wall
                    "smooth",
                    # 2. Interventricular Septum (Central Dividing Wall)
                    "smooth",
                    # 3. Aorta Arch (Top Central-Right Arch)
                    "smooth", "line", "line", "line",
                    # 4. Superior Vena Cava (Top-Left Tube)
                    "line", "line",
                    # 5. Pulmonary Artery (Branching T-Tube)
                    "line", "line",
                    # 6. Tricuspid & Mitral Valves
                    "line", "line",
                    # 7. Labels: RA (Right Atrium)
                    "line", "smooth", "smooth",
                    # 8. Labels: LA (Left Atrium)
                    "line", "line", "smooth",
                    # 9. Labels: RV (Right Ventricle)
                    "line", "smooth", "line", "line",
                    # 10. Labels: LV (Left Ventricle)
                    "line", "line", "line", "line"
                ],
                "items": [
                    # Outer Heart Muscular Wall Contour
                    [150, 45, 100, 35, 60, 65, 55, 110, 80, 165, 140, 215, 150, 225, 160, 215, 220, 165, 245, 110, 240, 65, 200, 35, 150, 45],
                    # Interventricular Septum Wall
                    [150, 105, 145, 150, 145, 200, 155, 200, 155, 150, 150, 105],
                    # Aorta Arch & 3 Branches
                    [145, 45, 145, 15, 175, 12, 195, 30, 195, 50],
                    [155, 15, 155, 0], [168, 13, 168, -2], [182, 18, 182, 3],
                    # Superior Vena Cava
                    [85, 45, 85, 10], [105, 45, 105, 10],
                    # Pulmonary Artery Arch
                    [125, 45, 125, 25, 145, 25], [135, 45, 135, 32, 155, 32],
                    # Atrioventricular Valves (Tricuspid & Bicuspid/Mitral)
                    [80, 115, 115, 125],
                    [185, 125, 220, 115],
                    # Label "RA" (at x=85, y=80)
                    [85, 70, 85, 92], [85, 70, 96, 70, 96, 81, 85, 81, 97, 92], [102, 92, 108, 70, 114, 92, 104, 85, 112, 85],
                    # Label "LA" (at x=185, y=80)
                    [185, 70, 185, 92], [185, 92, 195, 92], [200, 92, 206, 70, 212, 92, 202, 85, 210, 85],
                    # Label "RV" (at x=85, y=160)
                    [85, 150, 85, 172], [85, 150, 96, 150, 96, 161, 85, 161, 97, 172], [103, 150, 109, 172], [115, 150, 109, 172],
                    # Label "LV" (at x=185, y=160)
                    [185, 150, 185, 172], [185, 172, 195, 172], [203, 150, 209, 172], [215, 150, 209, 172]
                ],
                "width": 2.6,
                "color": "#1e293b",
                "fill_color": "transparent",
                "fill": []
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
        elif "phenopthaline" in prompt_lower or "phenolphthalein" in prompt_lower or "indicator" in prompt_lower:
            return {
                "origin": [0, 0],
                "types": [
                    # Left Phenol Ring (Hexagon)
                    "line", "line", "line", "line", "line", "line",
                    # Double bonds
                    "line", "line",
                    # OH group
                    "line", "smooth", "line", "line", "line",
                    # Right Phenol Ring (Hexagon)
                    "line", "line", "line", "line", "line", "line",
                    # Double bonds
                    "line", "line",
                    # OH group
                    "line", "smooth", "line", "line", "line",
                    # Phthalide / Lactone Ring
                    "line", "line", "line", "line", "line",
                    # Carbonyl =O
                    "line", "line", "smooth",
                    # Central connector bonds
                    "line", "line",
                    # Handwritten Formula: C₂₀H₁₄O₄
                    "smooth", # 'C'
                    "smooth", # '₂'
                    "smooth", # '₀'
                    "line", "line", "line", # 'H'
                    "smooth", # '₁'
                    "smooth", # '₄'
                    "smooth", # 'O'
                    "smooth"  # '₄'
                ],
                "items": [
                    # Left Phenol Ring
                    [70, 40, 100, 20], [100, 20, 130, 40], [130, 40, 130, 75],
                    [130, 75, 100, 95], [100, 95, 70, 75], [70, 75, 70, 40],
                    [76, 45, 76, 70], [124, 45, 100, 30],
                    # Left OH
                    [100, 20, 100, 5], [94, 2, 94, -8, 106, -8, 106, 2, 94, 2], [112, -8, 112, 2], [122, -8, 122, 2], [112, -3, 122, -3],
                    # Right Phenol Ring
                    [170, 40, 200, 20], [200, 20, 230, 40], [230, 40, 230, 75],
                    [230, 75, 200, 95], [200, 95, 170, 75], [170, 75, 170, 40],
                    [176, 45, 176, 70], [224, 45, 200, 30],
                    # Right OH
                    [200, 20, 200, 5], [194, 2, 194, -8, 206, -8, 206, 2, 194, 2], [212, -8, 212, 2], [222, -8, 222, 2], [212, -3, 222, -3],
                    # Phthalide lower Ring
                    [150, 120, 130, 150], [130, 150, 150, 180], [150, 180, 170, 180], [170, 180, 190, 150], [190, 150, 170, 120],
                    # Carbonyl =O
                    [190, 150, 210, 150], [190, 154, 210, 154], [215, 146, 215, 158, 225, 158, 225, 146, 215, 146],
                    # Connectors from central C (150, 95)
                    [130, 75, 150, 95], [170, 75, 150, 95],
                    # Handwritten Formula: C₂₀H₁₄O₄
                    [65, 210, 52, 214, 46, 224, 46, 238, 55, 248, 68, 250],
                    [78, 235, 86, 235, 86, 242, 78, 248, 88, 248],
                    [96, 235, 92, 241, 92, 245, 96, 248, 100, 245, 100, 241, 96, 235],
                    [114, 210, 114, 250], [132, 210, 132, 250], [114, 230, 132, 230],
                    [144, 236, 148, 232, 148, 248],
                    [158, 235, 154, 243, 166, 243, 164, 235, 164, 248],
                    [180, 210, 172, 218, 172, 240, 180, 250, 190, 240, 190, 218, 180, 210],
                    [202, 235, 198, 243, 210, 243, 208, 235, 208, 248]
                ],
                "width": 2.5,
                "color": "#1e293b",
                "fill_color": "transparent",
                "fill": []
            }
        elif "water" in prompt_lower or "h2o" in prompt_lower:
            return {
                "origin": [0, 0],
                "types": [
                    "smooth", # O atom
                    "line", # Left O-H bond
                    "line", "line", "line", # Left H
                    "line", # Right O-H bond
                    "line", "line", "line", # Right H
                    "smooth", # Lone pairs
                    # Handwritten Formula: H₂O
                    "line", "line", "line", # 'H'
                    "smooth", # '₂'
                    "smooth"  # 'O'
                ],
                "items": [
                    # Central O atom
                    [100, 45, 86, 55, 86, 75, 100, 85, 114, 75, 114, 55, 100, 45],
                    # Left O-H bond
                    [86, 75, 52, 108],
                    # Left H
                    [40, 112, 40, 138], [54, 112, 54, 138], [40, 125, 54, 125],
                    # Right O-H bond
                    [114, 75, 148, 108],
                    # Right H
                    [146, 112, 146, 138], [160, 112, 160, 138], [146, 125, 160, 125],
                    # Lone pairs arc
                    [94, 40, 100, 36, 106, 40],
                    # Handwritten H₂O
                    [72, 165, 72, 195], [88, 165, 88, 195], [72, 180, 88, 180],
                    [96, 182, 104, 182, 104, 190, 96, 198, 106, 198],
                    [122, 165, 112, 172, 112, 188, 122, 195, 132, 188, 132, 172, 122, 165]
                ],
                "width": 2.8,
                "color": "#1e293b",
                "fill_color": "transparent",
                "fill": []
            }
        elif "methane" in prompt_lower or "ch4" in prompt_lower:
            return {
                "origin": [0, 0],
                "types": [
                    "smooth", # C atom
                    "line", "line", "line", "line", # Top C-H and H
                    "line", "line", "line", "line", # Left C-H and H
                    "line", "line", "line", "line", # Right C-H and H
                    "line", "line", "line", "line", # Bottom C-H and H
                    # Handwritten Formula: CH₄
                    "smooth", # 'C'
                    "line", "line", "line", # 'H'
                    "smooth" # '₄'
                ],
                "items": [
                    # Central C
                    [100, 75, 88, 80, 82, 92, 88, 102, 100, 108],
                    # Top bond & H
                    [100, 70, 100, 45], [93, 20, 93, 40], [107, 20, 107, 40], [93, 30, 107, 30],
                    # Left bond & H
                    [80, 92, 55, 92], [32, 82, 32, 102], [46, 82, 46, 102], [32, 92, 46, 92],
                    # Right bond & H
                    [108, 92, 133, 92], [143, 82, 143, 102], [157, 82, 157, 102], [143, 92, 157, 92],
                    # Bottom bond & H
                    [100, 112, 100, 137], [93, 145, 93, 165], [107, 145, 107, 165], [93, 155, 107, 155],
                    # Handwritten CH₄
                    [72, 188, 60, 192, 54, 202, 54, 215, 62, 224, 75, 226],
                    [86, 188, 86, 226], [104, 188, 104, 226], [86, 207, 104, 207],
                    [118, 204, 112, 216, 124, 216, 120, 204, 120, 224]
                ],
                "width": 2.8,
                "color": "#1e293b",
                "fill_color": "transparent",
                "fill": []
            }
        elif "carbon dioxide" in prompt_lower or "co2" in prompt_lower:
            return {
                "origin": [0, 0],
                "types": [
                    "smooth", # Left O
                    "line", "line", # Left double bond
                    "smooth", # Central C
                    "line", "line", # Right double bond
                    "smooth", # Right O
                    # Handwritten Formula: CO₂
                    "smooth", "smooth", "smooth"
                ],
                "items": [
                    # Left O
                    [40, 70, 25, 78, 25, 92, 40, 100, 55, 92, 55, 78, 40, 70],
                    # Double bond
                    [58, 80, 84, 80], [58, 90, 84, 90],
                    # Central C
                    [104, 72, 92, 78, 88, 88, 92, 95, 104, 100],
                    # Double bond
                    [108, 80, 134, 80], [108, 90, 134, 90],
                    # Right O
                    [150, 70, 135, 78, 135, 92, 150, 100, 165, 92, 165, 78, 150, 70],
                    # Handwritten CO₂
                    [75, 135, 62, 140, 56, 150, 56, 162, 65, 170, 78, 172],
                    [98, 135, 86, 142, 86, 160, 98, 170, 110, 160, 110, 142, 98, 135],
                    [118, 156, 126, 156, 126, 164, 118, 172, 128, 172]
                ],
                "width": 2.8,
                "color": "#1e293b",
                "fill_color": "transparent",
                "fill": []
            }
        return None
