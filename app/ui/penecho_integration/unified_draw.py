"""
Unified Drawing Protocol Module & QGraphicsItem for AI-TUTOR.
Ported from penecho/public/draw.js.

Provides:
1. Normalization and validation for structured multi-primitive drawing commands.
2. Catmull-Rom / cubic Bezier tension smoothing.
3. Arc extrema and cubic Bezier extrema solvers for exact bounding box calculation.
4. Arrowhead tangent geometry generation.
5. PenechoDrawItem: Interactive PyQt6 QGraphicsItem rendering full unified drawings
   with selection, scaling, fill/stroke customization, and JSON serialization.
"""

import math
import re
from typing import Dict, List, Any, Optional, Set, Tuple
from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QPainterPath, QPolygonF
from PyQt6.QtCore import Qt, QRectF, QPointF

TYPES = {"line", "smooth", "rect", "ellipse", "circle", "arc"}
MAX_ITEMS = 64
MAX_VALUES = 2048
TAU = math.pi * 2


def _clamp(value: float, min_v: float, max_v: float) -> float:
    return max(min_v, min(max_v, value))


def _normalize_angle(angle: float) -> float:
    return ((angle % TAU) + TAU) % TAU


def _angle_on_sweep(angle: float, start: float, sweep: float) -> bool:
    if abs(sweep) >= TAU:
        return True
    dist = _normalize_angle(angle - start) if sweep > 0 else _normalize_angle(start - angle)
    return dist <= abs(sweep) + 1e-9


def _cubic_at(start: float, c1: float, c2: float, end: float, t: float) -> float:
    inv = 1.0 - t
    return (inv ** 3) * start + 3 * (inv ** 2) * t * c1 + 3 * inv * (t ** 2) * c2 + (t ** 3) * end


def _cubic_extrema(start: float, c1: float, c2: float, end: float) -> List[float]:
    a = -start + 3 * c1 - 3 * c2 + end
    b = 2 * (start - 2 * c1 + c2)
    c = c1 - start
    roots = []
    if abs(a) < 1e-9:
        if abs(b) >= 1e-9:
            roots.append(-c / b)
    else:
        discriminant = b * b - 4 * a * c
        if discriminant >= 0:
            root = math.sqrt(discriminant)
            roots.append((-b + root) / (2 * a))
            roots.append((-b - root) / (2 * a))
    return [r for r in roots if 0 < r < 1]


def _smooth_segments(points: List[Tuple[float, float]], closed: bool, tension: float) -> List[Dict[str, Tuple[float, float]]]:
    if len(points) < 3:
        return []
    segments = []
    count = len(points) if closed else len(points) - 1
    strength = tension / 50.0 / 6.0
    for idx in range(count):
        p1 = points[idx]
        p2 = points[(idx + 1) % len(points)]
        p0 = points[(idx - 1 + len(points)) % len(points)] if closed else points[max(0, idx - 1)]
        p3 = points[(idx + 2) % len(points)] if closed else points[min(len(points) - 1, idx + 2)]
        
        c1 = (p1[0] + (p2[0] - p0[0]) * strength, p1[1] + (p2[1] - p0[1]) * strength)
        c2 = (p2[0] - (p3[0] - p1[0]) * strength, p2[1] - (p3[1] - p1[1]) * strength)
        segments.append({"from": p1, "c1": c1, "c2": c2, "to": p2})
    return segments


def _arrow_geometry(end: Tuple[float, float], tangent_from: Tuple[float, float], width: float) -> List[Tuple[float, float]]:
    angle = math.atan2(end[1] - tangent_from[1], end[0] - tangent_from[0])
    size = max(14.0, width * 2.2)
    spread = 0.52
    return [
        (end[0], end[1]),
        (end[0] - size * math.cos(angle - spread), end[1] - size * math.sin(angle - spread)),
        (end[0] - size * math.cos(angle + spread), end[1] - size * math.sin(angle + spread)),
    ]


def _terminal_tangent_from(points: List[Tuple[float, float]], segments: List[Dict[str, Tuple[float, float]]]) -> Optional[Tuple[float, float]]:
    if not points:
        return None
    end = points[-1]
    candidates = []
    if segments:
        for seg in reversed(segments):
            candidates.extend([seg["c2"], seg["c1"], seg["from"]])
    else:
        for idx in range(len(points) - 2, -1, -1):
            candidates.append(points[idx])
    for pt in candidates:
        if math.hypot(end[0] - pt[0], end[1] - pt[1]) > 1e-6:
            return pt
    return None


def normalize_drawing_command(command: Dict[str, Any], canvas_size: int = 100000) -> Optional[Dict[str, Any]]:
    """
    Validates and normalizes structured drawing commands from Penecho Unified Drawing Protocol.
    """
    if not isinstance(command, dict):
        return None
    origin = command.get("origin", [0, 0])
    if not isinstance(origin, (list, tuple)) or len(origin) != 2:
        return None
    
    types = command.get("types", [])
    items = command.get("items", [])
    if not isinstance(types, list) or not isinstance(items, list):
        return None
    if len(types) == 0 or len(types) != len(items) or len(types) > MAX_ITEMS:
        return None
    
    width = float(command.get("width", 3.0))
    tension = float(command.get("tension", 50.0))
    color = command.get("color", "#1c1c1e")
    fill_color = command.get("fill_color", "rgba(59, 130, 246, 0.15)")

    closed_indices = set(command.get("closed", []))
    fill_indices = set(command.get("fill", []))
    arrow_indices = set(command.get("arrows", []))

    primitives = []
    min_x, min_y = float("inf"), float("inf")
    max_x, max_y = float("-inf"), float("-inf")

    def include_pt(x: float, y: float):
        nonlocal min_x, min_y, max_x, max_y
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)

    for idx, (ptype, item_vals) in enumerate(zip(types, items)):
        if ptype not in TYPES or not isinstance(item_vals, (list, tuple)):
            return None
        
        is_closed = idx in closed_indices
        is_fill = idx in fill_indices
        has_arrow = idx in arrow_indices

        prim = {
            "type": ptype,
            "closed": is_closed,
            "fill": is_fill,
            "arrow": has_arrow,
            "raw_item": list(item_vals)
        }

        if ptype in ("line", "smooth"):
            if len(item_vals) < 4 or len(item_vals) % 2 != 0:
                return None
            pts = []
            for i in range(0, len(item_vals), 2):
                px = origin[0] + item_vals[i]
                py = origin[1] + item_vals[i + 1]
                pts.append((px, py))
                include_pt(px, py)
            prim["points"] = pts

            segments = _smooth_segments(pts, is_closed, tension) if ptype == "smooth" else []
            prim["segments"] = segments
            if segments:
                for seg in segments:
                    for t in _cubic_extrema(seg["from"][0], seg["c1"][0], seg["c2"][0], seg["to"][0]):
                        include_pt(_cubic_at(seg["from"][0], seg["c1"][0], seg["c2"][0], seg["to"][0], t),
                                   _cubic_at(seg["from"][1], seg["c1"][1], seg["c2"][1], seg["to"][1], t))
            if has_arrow:
                tangent_pt = _terminal_tangent_from(pts, segments)
                if tangent_pt:
                    arrow_pts = _arrow_geometry(pts[-1], tangent_pt, width)
                    prim["arrow_geometry"] = arrow_pts
                    for ax, ay in arrow_pts:
                        include_pt(ax, ay)

        elif ptype == "rect":
            if len(item_vals) != 4:
                return None
            rx, ry, rw, rh = origin[0] + item_vals[0], origin[1] + item_vals[1], item_vals[2], item_vals[3]
            prim["x"], prim["y"], prim["w"], prim["h"] = rx, ry, rw, rh
            include_pt(rx, ry)
            include_pt(rx + rw, ry + rh)

        elif ptype == "circle":
            if len(item_vals) != 3:
                return None
            cx, cy, r = origin[0] + item_vals[0], origin[1] + item_vals[1], item_vals[2]
            prim["cx"], prim["cy"], prim["r"] = cx, cy, r
            include_pt(cx - r, cy - r)
            include_pt(cx + r, cy + r)

        elif ptype == "ellipse":
            if len(item_vals) != 4:
                return None
            cx, cy, rx, ry = origin[0] + item_vals[0], origin[1] + item_vals[1], item_vals[2], item_vals[3]
            prim["cx"], prim["cy"], prim["rx"], prim["ry"] = cx, cy, rx, ry
            include_pt(cx - rx, cy - ry)
            include_pt(cx + rx, cy + ry)

        elif ptype == "arc":
            if len(item_vals) != 6:
                return None
            cx, cy, rx, ry, start_deg, sweep_deg = (
                origin[0] + item_vals[0], origin[1] + item_vals[1],
                item_vals[2], item_vals[3],
                math.radians(item_vals[4]), math.radians(item_vals[5])
            )
            prim["cx"], prim["cy"], prim["rx"], prim["ry"] = cx, cy, rx, ry
            prim["start_rad"], prim["sweep_rad"] = start_deg, sweep_deg
            # Arc bounding box
            include_pt(cx + rx * math.cos(start_deg), cy + ry * math.sin(start_deg))
            include_pt(cx + rx * math.cos(start_deg + sweep_deg), cy + ry * math.sin(start_deg + sweep_deg))
            for test_angle in [0, math.pi / 2, math.pi, 3 * math.pi / 2]:
                if _angle_on_sweep(test_angle, start_deg, sweep_deg):
                    include_pt(cx + rx * math.cos(test_angle), cy + ry * math.sin(test_angle))

        primitives.append(prim)

    if min_x == float("inf"):
        min_x, min_y, max_x, max_y = origin[0], origin[1], origin[0] + 100, origin[1] + 100

    padding = max(width * 2, 8.0)
    bounds = (min_x - padding, min_y - padding, (max_x - min_x) + padding * 2, (max_y - min_y) + padding * 2)

    return {
        "origin": list(origin),
        "types": list(types),
        "items": list(items),
        "width": width,
        "tension": tension,
        "color": color,
        "fill_color": fill_color,
        "closed": list(closed_indices),
        "fill": list(fill_indices),
        "arrows": list(arrow_indices),
        "primitives": primitives,
        "bounds": bounds,
    }


def _parse_color(val: Any, default: str = "#1c1c1e") -> QColor:
    if isinstance(val, QColor):
        return val
    if not val or not isinstance(val, str):
        return QColor(default)
    s = val.strip()
    if s.lower() in ("transparent", "none", ""):
        return QColor(0, 0, 0, 0)
    rgba_m = re.match(r'rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d\.]+))?\s*\)', s, re.IGNORECASE)
    if rgba_m:
        r, g, b = int(rgba_m.group(1)), int(rgba_m.group(2)), int(rgba_m.group(3))
        a = float(rgba_m.group(4)) if rgba_m.group(4) is not None else 1.0
        alpha_int = max(0, min(255, int(a * 255 if a <= 1.0 else a)))
        return QColor(r, g, b, alpha_int)
    c = QColor.fromString(s) if hasattr(QColor, "fromString") else QColor(s)
    if c.isValid():
        return c
    return QColor(default)


class PenechoDrawItem(QGraphicsItem):
    """
    QGraphicsItem that renders a Penecho Unified Drawing Protocol composite structure.
    Fully interactive: movable, selectable, resizable, and serializable.
    """

    def __init__(self, command: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self._command_data = command
        self._normalized = normalize_drawing_command(command) or {}
        self._pen_color = _parse_color(self._normalized.get("color", "#1c1c1e"), default="#1c1c1e")
        self._fill_color = _parse_color(self._normalized.get("fill_color", "transparent"), default="transparent")
        self._stroke_width = float(self._normalized.get("width", 3.0))

    def boundingRect(self) -> QRectF:
        bounds = self._normalized.get("bounds", (0, 0, 100, 100))
        # Relative to item origin (0, 0)
        return QRectF(bounds[0] - self._normalized.get("origin", [0, 0])[0],
                      bounds[1] - self._normalized.get("origin", [0, 0])[1],
                      bounds[2], bounds[3])

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pen = QPen(self._pen_color, self._stroke_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        brush = QBrush(self._fill_color)
        painter.setPen(pen)

        origin = self._normalized.get("origin", [0, 0])
        ox, oy = origin[0], origin[1]

        for prim in self._normalized.get("primitives", []):
            ptype = prim["type"]
            is_fill = prim.get("fill", False)
            painter.setBrush(brush if is_fill else Qt.BrushStyle.NoBrush)

            if ptype == "line":
                pts = prim.get("points", [])
                if len(pts) >= 2:
                    path = QPainterPath()
                    path.moveTo(pts[0][0] - ox, pts[0][1] - oy)
                    for px, py in pts[1:]:
                        path.lineTo(px - ox, py - oy)
                    if prim.get("closed"):
                        path.closeSubpath()
                    painter.drawPath(path)

            elif ptype == "smooth":
                segments = prim.get("segments", [])
                if segments:
                    path = QPainterPath()
                    path.moveTo(segments[0]["from"][0] - ox, segments[0]["from"][1] - oy)
                    for seg in segments:
                        path.cubicTo(
                            seg["c1"][0] - ox, seg["c1"][1] - oy,
                            seg["c2"][0] - ox, seg["c2"][1] - oy,
                            seg["to"][0] - ox, seg["to"][1] - oy
                        )
                    if prim.get("closed"):
                        path.closeSubpath()
                    painter.drawPath(path)

            elif ptype == "rect":
                rx = prim["x"] - ox
                ry = prim["y"] - oy
                painter.drawRect(QRectF(rx, ry, prim["w"], prim["h"]))

            elif ptype == "circle":
                cx = prim["cx"] - ox
                cy = prim["cy"] - oy
                r = prim["r"]
                painter.drawEllipse(QPointF(cx, cy), r, r)

            elif ptype == "ellipse":
                cx = prim["cx"] - ox
                cy = prim["cy"] - oy
                painter.drawEllipse(QPointF(cx, cy), prim["rx"], prim["ry"])

            elif ptype == "arc":
                cx = prim["cx"] - ox
                cy = prim["cy"] - oy
                rx, ry = prim["rx"], prim["ry"]
                start_deg = math.degrees(prim["start_rad"])
                sweep_deg = math.degrees(prim["sweep_rad"])
                # In Qt drawArc uses 1/16th of a degree
                rect = QRectF(cx - rx, cy - ry, rx * 2, ry * 2)
                painter.drawArc(rect, int(start_deg * 16), int(sweep_deg * 16))

            # Arrowhead
            if prim.get("arrow") and "arrow_geometry" in prim:
                arrow_pts = prim["arrow_geometry"]
                poly = QPolygonF([QPointF(ax - ox, ay - oy) for ax, ay in arrow_pts])
                painter.setBrush(QBrush(self._pen_color))
                painter.drawPolygon(poly)

        # Draw dashed selection bounding box when selected
        if self.isSelected():
            sel_pen = QPen(QColor("#3b82f6"), 1.5, Qt.PenStyle.DashLine)
            painter.setPen(sel_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.boundingRect())

        painter.restore()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "PenechoDrawItem",
            "x": self.pos().x(),
            "y": self.pos().y(),
            "z_value": self.zValue(),
            "command": self._command_data,
            "pen_color": self._pen_color.name(QColor.NameFormat.HexArgb),
            "fill_color": self._fill_color.name(QColor.NameFormat.HexArgb),
            "stroke_width": self._stroke_width
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PenechoDrawItem":
        cmd = data.get("command", {})
        item = cls(cmd)
        if "pen_color" in data:
            item._pen_color = QColor(data["pen_color"])
        if "fill_color" in data:
            item._fill_color = QColor(data["fill_color"])
        if "stroke_width" in data:
            item._stroke_width = float(data["stroke_width"])
        return item
