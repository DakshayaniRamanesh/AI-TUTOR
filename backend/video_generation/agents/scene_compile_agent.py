import json
import math
from typing import Any, Dict, List

from backend.video_generation.models import SceneSpec, VideoJob


class SceneCompileAgent:
    """Deterministically compile SceneSpec objects into safe Manim CE Python."""

    def run(self, job: VideoJob) -> VideoJob:
        job.step = "scene_compile"
        job.progress_percentage = 60
        if not job.scene_specs:
            return job
        job.manim_code = self.compile(job.scene_specs)
        return job

    def compile(self, scenes: List[SceneSpec]) -> str:
        body: List[str] = [
            "from manim import *",
            "import numpy as np",
            "import math",
        ]
        for index, scene in enumerate(scenes):
            safe_id = "".join(c if c.isalnum() else "_" for c in scene.scene_id)
            if not safe_id:
                safe_id = f"{index}"
            body.extend([
                "",
                f"class Scene_{safe_id}(Scene):",
                "    def construct(self):",
                "        self.camera.background_color = '#090d16'",
            ])
            body.extend(self._compile_scene(scene, index))
            body.append("        self.wait(0.5)")
        return "\n".join(body) + "\n"

    def _compile_scene(self, scene: SceneSpec, index: int) -> List[str]:
        lines: List[str] = [f"        # ---- {scene.scene_id}: {self._comment(scene.title)} ----"]
        object_vars: Dict[str, str] = {}
        for obj_index, obj in enumerate(scene.objects):
            oid = str(obj.get("id", f"obj_{obj_index}"))
            var = f"s{index}_{self._identifier(oid)}"
            object_vars[oid] = var
            lines.extend(self._compile_object(var, obj))
            
            # If it's a term_equation, expose the term IDs to object_vars
            if obj.get("type") == "term_equation":
                for t in obj.get("terms", []):
                    tid = t.get("id")
                    if tid:
                        tvar = f"{var}_{self._identifier(tid)}"
                        object_vars[tid] = tvar

        # If layout is 'equation_with_rule_below', shift up everything that is not a question or rule
        if scene.layout == "equation_with_rule_below":
            lines.append("        if self.mobjects:")
            lines.append("            self.play(VGroup(*self.mobjects).animate.shift(UP * 1.5), run_time=0.8)")

        acted = set()
        for action in scene.actions:
            target = str(action.get("target", ""))
            acted.add(target)
            lines.extend(self._compile_action(action, object_vars))

        # Any object omitted from actions still appears, so the scene never renders empty.
        unacted = []
        for oid, var in object_vars.items():
            if oid not in acted and var not in acted:
                # Do not auto-fade-in sub-terms if their parent equation was already acted on
                if "_" not in oid:  # Hacky heuristic for now
                    unacted.append(var)
                    
        if unacted:
            args = ", ".join(unacted)
            lines.append(f"        self.play(FadeIn({args}), run_time=0.8)")

        # Calculate dynamic reading time based on visible text word count
        total_words = 0
        for obj in scene.objects:
            if obj.get("type") == "text":
                total_words += len(str(obj.get("text", "")).split())
        for action in scene.actions:
            atype = str(action.get("type", ""))
            if atype == "AskQuestion":
                total_words += len(str(action.get("question", "")).split())
            elif atype == "RevealRule":
                total_words += len(str(action.get("rule", "")).split())
                
        # Base wait time plus time for reading
        wait_time = max(1.5, (total_words / 2.5))
        
        lines.append(f"        self.wait({wait_time:.2f})")
        # Do not automatically FadeOut(all) at the end of every scene to preserve persistence.
        return lines

    def _compile_object(self, var: str, obj: Dict[str, Any]) -> List[str]:
        otype = str(obj.get("type", "text"))
        position = self._position_expr(str(obj.get("position", "center")))
        color = self._color(obj.get("color"))

        if otype in {"text", "equation"}:
            text = str(obj.get("text") or obj.get("value") or obj.get("label") or "")[:180]
            font = self._safe_number(obj.get("font_size"), 28, 14, 42)
            return [f"        {var} = Text({json.dumps(text)}, font_size={font}, color={color}).move_to({position})"]

        if otype == "term_equation":
            terms = obj.get("terms", [])
            term_strings = [str(t.get("value", "")) for t in terms]
            # Use MathTex to separate terms
            lines = [f"        {var} = MathTex(*{json.dumps(term_strings)}, color={color}).move_to({position})"]
            # Expose term parts dynamically via dictionary-like access if needed
            for i, t in enumerate(terms):
                tid = t.get("id")
                if tid:
                    tvar = f"{var}_{self._identifier(tid)}"
                    lines.append(f"        {tvar} = {var}[{i}]")
            return lines

        if otype == "circle":
            radius = self._safe_number(obj.get("radius"), 1.1, 0.2, 2.5)
            return [f"        {var} = Circle(radius={radius}, color={color}, fill_opacity=0.15).move_to({position})"]

        if otype == "rectangle":
            width = self._safe_number(obj.get("width"), 3.6, 0.6, 8.0)
            height = self._safe_number(obj.get("height"), 1.8, 0.4, 5.0)
            return [f"        {var} = RoundedRectangle(width={width}, height={height}, corner_radius=0.18, color={color}, fill_opacity=0.12).move_to({position})"]

        if otype in {"arrow", "vector"}:
            dx = self._safe_number(obj.get("dx"), 2.4, -5.0, 5.0)
            dy = self._safe_number(obj.get("dy"), 0.8 if otype == "vector" else 0.0, -3.0, 3.0)
            return [
                f"        {var} = Arrow(ORIGIN, np.array([{dx}, {dy}, 0.0]), color={color}, buff=0.0)",
                f"        {var}.move_to({position})",
            ]

        if otype == "line":
            return [
                f"        {var} = Line(LEFT * 1.6, RIGHT * 1.6, color={color})",
                f"        {var}.move_to({position})",
            ]

        if otype == "axes":
            return [
                f"        {var} = Axes(x_range=[-3, 3, 1], y_range=[-2, 2, 1], x_length=5.2, y_length=3.2, tips=False, axis_config={{'color': {color}}})",
                f"        {var}.move_to({position})",
            ]

        if otype == "plot":
            curve = str(obj.get("curve", "parabola"))
            expr = {
                "sine": "lambda x: math.sin(x)",
                "cosine": "lambda x: math.cos(x)",
                "linear": "lambda x: 0.65*x",
                "parabola": "lambda x: 0.35*(x**2)-1",
            }.get(curve, "lambda x: 0.35*(x**2)-1")
            axes_var = f"{var}_axes"
            return [
                f"        {axes_var} = Axes(x_range=[-3, 3, 1], y_range=[-2, 2, 1], x_length=5.0, y_length=3.0, tips=False)",
                f"        {axes_var}.move_to({position})",
                f"        {var}_curve = {axes_var}.plot({expr}, x_range=[-3, 3], color={color})",
                f"        {var} = VGroup({axes_var}, {var}_curve)",
            ]

        if otype == "matrix":
            values = obj.get("values") if isinstance(obj.get("values"), list) else [["1", "0"], ["0", "1"]]
            rows = values[:4]
            cell_lines = [f"        {var} = VGroup()"]
            for r, row in enumerate(rows):
                if not isinstance(row, list):
                    continue
                for c, value in enumerate(row[:4]):
                    cell = f"{var}_c_{r}_{c}"
                    cell_lines.append(f"        {cell}_box = Square(side_length=0.75, color={color}, fill_opacity=0.08)")
                    cell_lines.append(f"        {cell}_txt = Text({json.dumps(str(value)[:12])}, font_size=20, color=WHITE).move_to({cell}_box.get_center())")
                    cell_lines.append(f"        {cell} = VGroup({cell}_box, {cell}_txt).shift(RIGHT*{c*0.8:.2f} + DOWN*{r*0.8:.2f})")
                    cell_lines.append(f"        {var}.add({cell})")
            cell_lines.append(f"        {var}.move_to({position})")
            return cell_lines

        if otype == "vector_field":
            pattern = str(obj.get("pattern", "uniform"))
            lines = [f"        {var} = VGroup()"]
            for xi in (-2, -1, 0, 1, 2):
                for yi in (-1, 0, 1):
                    if xi == 0 and yi == 0 and pattern in {"radial_outward", "radial_inward", "rotational"}:
                        continue
                    sx, sy = xi * 0.65, yi * 0.65
                    if pattern == "radial_outward":
                        vx, vy = sx, sy
                    elif pattern == "radial_inward":
                        vx, vy = -sx, -sy
                    elif pattern == "rotational":
                        vx, vy = -sy, sx
                    else:
                        vx, vy = 1.0, 0.25
                    mag = max(0.001, math.hypot(vx, vy))
                    vx, vy = vx / mag * 0.42, vy / mag * 0.42
                    lines.append(f"        {var}.add(Arrow(np.array([{sx:.3f}, {sy:.3f}, 0]), np.array([{sx+vx:.3f}, {sy+vy:.3f}, 0]), buff=0, stroke_width=2.5, max_tip_length_to_length_ratio=0.28, color={color}))")
            lines.append(f"        {var}.move_to({position})")
            return lines

        if otype in {"path", "board_stroke"}:
            points = obj.get("points") if isinstance(obj.get("points"), list) else []
            clean_pts = []
            for p in points[:120]:
                if isinstance(p, (list, tuple)) and len(p) >= 2:
                    try:
                        clean_pts.append([float(p[0]), float(p[1]), 0.0])
                    except Exception:
                        pass
            if len(clean_pts) >= 2:
                # Normalize source points into a compact Manim region.
                xs = [p[0] for p in clean_pts]
                ys = [p[1] for p in clean_pts]
                minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
                span = max(maxx-minx, maxy-miny, 1.0)
                norm = [[(x-(minx+maxx)/2)/span*3.5, -((y-(miny+maxy)/2)/span*3.5), 0.0] for x, y, _ in clean_pts]
                return [
                    f"        {var} = VMobject(color={color}, stroke_width=3)",
                    f"        {var}.set_points_as_corners([np.array(p) for p in {json.dumps(norm)}])",
                    f"        {var}.move_to({position})",
                ]

        fallback_text = str(obj.get("text") or obj.get("label") or otype.replace("_", " ").title())[:120]
        return [f"        {var} = Text({json.dumps(fallback_text)}, font_size=26, color={color}).move_to({position})"]

    def _compile_action(self, action: Dict[str, Any], object_vars: Dict[str, str]) -> List[str]:
        atype = str(action.get("type", "create"))
        target = str(action.get("target", ""))
        var = object_vars.get(target, "None")

        if atype == "AskQuestion":
            q = str(action.get("question", "Question?"))
            return [
                f"        _q_txt = Text({json.dumps(q)}, font_size=24, color=YELLOW).to_edge(UP)",
                f"        self.play(Write(_q_txt), run_time=1.0)"
            ]
        if atype == "RevealRule":
            rule = str(action.get("rule", "Rule"))
            return [
                f"        _rule_txt = MathTex({json.dumps(rule)}, color=GREEN).to_edge(DOWN)",
                f"        _rule_box = SurroundingRectangle(_rule_txt, color=GREEN)",
                f"        self.play(FadeIn(VGroup(_rule_box, _rule_txt)), run_time=1.0)"
            ]
        if atype == "HighlightTerm":
            return [f"        if {var} is not None: self.play(Indicate({var}, color=YELLOW), run_time=0.8)"]
        if atype == "MapTerms":
            src = object_vars.get(str(action.get("source", "")), "None")
            return [
                f"        if {src} is not None and {var} is not None:",
                f"            _map_line = Line({src}.get_bottom(), {var}.get_top(), color=YELLOW)",
                f"            self.play(Create(_map_line), run_time=0.8)",
                f"            self.play(FadeOut(_map_line), run_time=0.5)"
            ]
        if atype == "SubstituteValues":
            src = object_vars.get(str(action.get("source", "")), "None")
            return [
                f"        if {src} is not None and {var} is not None:",
                f"            self.play(Transform({src}, {var}), run_time=1.2)"
            ]
        if atype == "transform":
            to = object_vars.get(str(action.get("to", "")), "None")
            return [
                f"        if {var} is not None and {to} is not None:",
                f"            self.play(Transform({var}, {to}), run_time=1.2)"
            ]
            
        if not var or var == "None":
            return []

        if atype == "write":
            return [f"        self.play(Write({var}), run_time=0.8)"]
        if atype == "fade_in":
            return [f"        self.play(FadeIn({var}), run_time=0.7)"]
        if atype == "fade_out":
            return [f"        self.play(FadeOut({var}), run_time=0.6)"]
        if atype in {"highlight", "indicate"}:
            return [f"        self.play(Indicate({var}, color=YELLOW), run_time=0.8)"]
        if atype == "translate":
            direction = self._direction_expr(str(action.get("direction", "right")))
            amount = self._safe_number(action.get("amount"), 1.0, 0.1, 4.0)
            return [f"        self.play({var}.animate.shift({direction} * {amount}), run_time=0.8)"]
        if atype == "rotate":
            angle = self._safe_number(action.get("angle_degrees"), 45.0, -360.0, 360.0)
            return [f"        self.play(Rotate({var}, angle={math.radians(angle):.6f}), run_time=0.8)"]
        if atype == "scale":
            factor = self._safe_number(action.get("factor"), 1.15, 0.3, 3.0)
            return [f"        self.play({var}.animate.scale({factor}), run_time=0.8)"]
        return [f"        self.play(Create({var}), run_time=0.8)"]

    @staticmethod
    def _identifier(value: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in value)
        if not cleaned:
            cleaned = "obj"
        if cleaned[0].isdigit():
            cleaned = "obj_" + cleaned
        return cleaned[:60]

    @staticmethod
    def _comment(value: str) -> str:
        return value.replace("\n", " ").replace("#", "")[:100]

    @staticmethod
    def _position_expr(position: str) -> str:
        return {
            "center": "ORIGIN",
            "top": "UP * 2.6",
            "bottom": "DOWN * 2.5",
            "left": "LEFT * 3.6",
            "right": "RIGHT * 3.6",
            "upper_left": "LEFT * 3.5 + UP * 2.0",
            "upper_right": "RIGHT * 3.5 + UP * 2.0",
            "lower_left": "LEFT * 3.5 + DOWN * 2.0",
            "lower_right": "RIGHT * 3.5 + DOWN * 2.0",
        }.get(position, "ORIGIN")

    @staticmethod
    def _direction_expr(direction: str) -> str:
        return {
            "left": "LEFT", "right": "RIGHT", "up": "UP", "down": "DOWN",
        }.get(direction, "RIGHT")

    @staticmethod
    def _color(value: Any) -> str:
        name = str(value or "TEAL").upper()
        allowed = {"BLUE", "TEAL", "GREEN", "YELLOW", "RED", "PURPLE", "ORANGE", "WHITE", "GRAY"}
        return name if name in allowed else "TEAL"

    @staticmethod
    def _safe_number(value: Any, default: float, low: float, high: float) -> float:
        try:
            num = float(value)
        except Exception:
            num = float(default)
        return max(low, min(high, num))
