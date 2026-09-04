"""
Declarative 2D Animation Engine & QGraphicsItem for AI-TUTOR.
Ported from penecho/public/animation.js.

Provides:
1. Data models and normalizers for declarative 2D animation scenes:
   - Object Types: group, circle, ellipse, rect, line, path, text.
   - Motion Types: orbit, spin, translate, pulse, fade, keyframes.
2. Motion Evaluator for computing transforms (translation, rotation, scale, opacity) at time t.
3. PenechoAnimationItem: High-performance 60 FPS interactive scene player with
   Play/Pause, Reset, Speed multipliers, interactive handles, and full serialization.
"""

import time
import math
from typing import Dict, List, Any, Optional, Tuple, Set
from PyQt6.QtWidgets import (
    QGraphicsItem, QStyleOptionGraphicsItem, QWidget,
    QGraphicsSceneMouseEvent
)
from PyQt6.QtGui import (
    QPainter, QPen, QColor, QBrush, QFont, QPainterPath,
    QTransform, QPolygonF
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, pyqtSignal, QObject

OBJECT_TYPES = {"group", "circle", "ellipse", "rect", "line", "path", "text"}
MOTION_TYPES = {"orbit", "spin", "translate", "pulse", "fade", "keyframes"}
DEFAULT_PALETTE = ["#f59e0b", "#2563eb", "#ef4444", "#10b981", "#8b5cf6", "#06b6d4", "#f97316", "#64748b"]


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        f = float(val)
        return f if math.isfinite(f) else default
    except (ValueError, TypeError):
        return default


def _clamp(val: float, min_v: float, max_v: float) -> float:
    return max(min_v, min(max_v, val))


def _normalize_object(source: Dict[str, Any], index: int, width: float, height: float) -> Optional[Dict[str, Any]]:
    if not isinstance(source, dict):
        return None
    otype = source.get("type")
    if otype not in OBJECT_TYPES:
        return None
    oid = str(source.get("id", f"obj_{index}"))
    
    is_outlined = otype in ("line", "path")
    fill = source.get("fill", None if is_outlined else DEFAULT_PALETTE[index % len(DEFAULT_PALETTE)])
    stroke = source.get("stroke", DEFAULT_PALETTE[index % len(DEFAULT_PALETTE)] if is_outlined else None)
    line_width = _clamp(_safe_float(source.get("lineWidth", 4 if is_outlined else 2)), 0.5, 80.0)
    opacity = _clamp(_safe_float(source.get("opacity", 1.0)), 0.0, 1.0)

    base = {
        "id": oid,
        "type": otype,
        "fill": fill,
        "stroke": stroke,
        "lineWidth": line_width,
        "opacity": opacity,
    }

    if otype == "group":
        children = [str(c) for c in source.get("children", []) if isinstance(c, str)]
        return {
            **base,
            "x": _safe_float(source.get("x", 0)),
            "y": _safe_float(source.get("y", 0)),
            "rotation": _safe_float(source.get("rotation", 0)),
            "scale": _clamp(_safe_float(source.get("scale", 1.0)), 0.05, 20.0),
            "children": children
        }
    elif otype == "circle":
        return {
            **base,
            "cx": _safe_float(source.get("cx", 0)),
            "cy": _safe_float(source.get("cy", 0)),
            "r": max(1.0, _safe_float(source.get("r", 20.0)))
        }
    elif otype == "ellipse":
        return {
            **base,
            "cx": _safe_float(source.get("cx", 0)),
            "cy": _safe_float(source.get("cy", 0)),
            "rx": max(1.0, _safe_float(source.get("rx", 30.0))),
            "ry": max(1.0, _safe_float(source.get("ry", 20.0)))
        }
    elif otype == "rect":
        return {
            **base,
            "x": _safe_float(source.get("x", 0)),
            "y": _safe_float(source.get("y", 0)),
            "w": max(1.0, _safe_float(source.get("w", 60.0))),
            "h": max(1.0, _safe_float(source.get("h", 40.0))),
            "radius": max(0.0, _safe_float(source.get("radius", 0.0)))
        }
    elif otype == "line":
        return {
            **base,
            "x1": _safe_float(source.get("x1", 0)),
            "y1": _safe_float(source.get("y1", 0)),
            "x2": _safe_float(source.get("x2", 50)),
            "y2": _safe_float(source.get("y2", 50))
        }
    elif otype == "path":
        pts = []
        for p in source.get("points", []):
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                pts.append((_safe_float(p[0]), _safe_float(p[1])))
        if len(pts) < 2:
            return None
        return {
            **base,
            "points": pts,
            "closed": bool(source.get("closed", False)),
            "smooth": bool(source.get("smooth", False))
        }
    elif otype == "text":
        return {
            **base,
            "x": _safe_float(source.get("x", 0)),
            "y": _safe_float(source.get("y", 0)),
            "text": str(source.get("text", "")),
            "fontSize": _clamp(_safe_float(source.get("fontSize", 20.0)), 8.0, 120.0),
            "fontFamily": str(source.get("fontFamily", "-apple-system, sans-serif")),
            "fontWeight": str(source.get("fontWeight", "500")),
            "align": str(source.get("align", "left"))
        }
    return None


def _normalize_motion(source: Dict[str, Any], ids: Set[str], duration_ms: float) -> Optional[Dict[str, Any]]:
    if not isinstance(source, dict):
        return None
    mtype = source.get("type")
    target = str(source.get("target", ""))
    if mtype not in MOTION_TYPES or target not in ids:
        return None
    
    period_ms = _clamp(_safe_float(source.get("periodMs", duration_ms)), 200.0, 600000.0)
    phase_rad = math.radians(_safe_float(source.get("phaseDeg", 0.0)))

    base = {
        "type": mtype,
        "target": target,
        "periodMs": period_ms,
        "phase": phase_rad
    }

    if mtype == "orbit":
        center = source.get("center", [0, 0])
        center_pt = [_safe_float(center[0]), _safe_float(center[1])] if isinstance(center, (list, tuple)) and len(center) >= 2 else str(center)
        return {
            **base,
            "center": center_pt,
            "rx": max(1.0, _safe_float(source.get("rx", 50.0))),
            "ry": max(1.0, _safe_float(source.get("ry", 50.0))),
            "clockwise": source.get("clockwise", True) is not False
        }
    elif mtype == "spin":
        return {
            **base,
            "clockwise": source.get("clockwise", True) is not False
        }
    elif mtype == "translate":
        from_pt = source.get("from", [0, 0])
        to_pt = source.get("to", [50, 50])
        return {
            **base,
            "from": (_safe_float(from_pt[0]), _safe_float(from_pt[1])) if isinstance(from_pt, (list, tuple)) and len(from_pt) >= 2 else (0, 0),
            "to": (_safe_float(to_pt[0]), _safe_float(to_pt[1])) if isinstance(to_pt, (list, tuple)) and len(to_pt) >= 2 else (50, 50),
            "alternate": source.get("alternate", True) is not False
        }
    elif mtype == "pulse":
        return {
            **base,
            "from": _clamp(_safe_float(source.get("from", 0.85)), 0.05, 20.0),
            "to": _clamp(_safe_float(source.get("to", 1.15)), 0.05, 20.0)
        }
    elif mtype == "fade":
        return {
            **base,
            "from": _clamp(_safe_float(source.get("from", 0.2)), 0.0, 1.0),
            "to": _clamp(_safe_float(source.get("to", 1.0)), 0.0, 1.0)
        }
    elif mtype == "keyframes":
        frames = []
        for kf in source.get("frames", []):
            if isinstance(kf, dict) and "at" in kf:
                frames.append({
                    "at": _clamp(_safe_float(kf["at"]), 0.0, 1.0),
                    "x": _safe_float(kf.get("x", 0)),
                    "y": _safe_float(kf.get("y", 0)),
                    "rotation": _safe_float(kf.get("rotation", 0)),
                    "scale": _clamp(_safe_float(kf.get("scale", 1.0)), 0.05, 20.0),
                    "opacity": _clamp(_safe_float(kf.get("opacity", 1.0)), 0.0, 1.0)
                })
        frames.sort(key=lambda f: f["at"])
        if len(frames) < 2:
            return None
        return {**base, "frames": frames}
    return None


def normalize_animation_scene(scene: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(scene, dict):
        return None
    w = max(120.0, _safe_float(scene.get("w", 400.0)))
    h = max(90.0, _safe_float(scene.get("h", 300.0)))
    duration_ms = _clamp(_safe_float(scene.get("durationMs", 6000.0)), 500.0, 600000.0)
    title = str(scene.get("title", "Animation Scene"))

    raw_objects = scene.get("objects", [])
    raw_motions = scene.get("motions", [])
    if not isinstance(raw_objects, list) or not isinstance(raw_motions, list):
        return None

    objects = []
    for idx, obj in enumerate(raw_objects):
        norm_obj = _normalize_object(obj, idx, w, h)
        if norm_obj:
            objects.append(norm_obj)

    if not objects:
        return None

    ids = {obj["id"] for obj in objects}
    motions = []
    for mot in raw_motions:
        norm_mot = _normalize_motion(mot, ids, duration_ms)
        if norm_mot:
            motions.append(norm_mot)

    return {
        "title": title,
        "w": w,
        "h": h,
        "durationMs": duration_ms,
        "objects": objects,
        "motions": motions,
        "byId": {obj["id"]: obj for obj in objects}
    }


def evaluate_scene_state(scene: Dict[str, Any], elapsed_ms: float) -> Dict[str, Dict[str, float]]:
    """
    Computes current transformation (dx, dy, rotation_deg, scale, opacity) for each object at elapsed_ms.
    """
    transforms = {}
    for obj in scene.get("objects", []):
        transforms[obj["id"]] = {
            "dx": 0.0,
            "dy": 0.0,
            "rotation": 0.0,
            "scale": 1.0,
            "opacity": obj.get("opacity", 1.0)
        }

    for mot in scene.get("motions", []):
        target = mot["target"]
        if target not in transforms:
            continue
        t_data = transforms[target]
        mtype = mot["type"]
        period = mot["periodMs"]
        phase = mot["phase"]
        
        # Normalized phase time in [0, 1)
        phase_time = ((elapsed_ms / period) + (phase / (math.pi * 2))) % 1.0

        if mtype == "spin":
            sign = 1 if mot.get("clockwise", True) else -1
            t_data["rotation"] += sign * phase_time * 360.0

        elif mtype == "orbit":
            angle = (phase_time * math.pi * 2) * (1 if mot.get("clockwise", True) else -1)
            rx = mot["rx"]
            ry = mot["ry"]
            t_data["dx"] += rx * math.cos(angle)
            t_data["dy"] += ry * math.sin(angle)

        elif mtype == "translate":
            fx, fy = mot["from"]
            tx, ty = mot["to"]
            if mot.get("alternate", True):
                progress = 0.5 - 0.5 * math.cos(phase_time * math.pi * 2)
            else:
                progress = phase_time
            t_data["dx"] += fx + (tx - fx) * progress
            t_data["dy"] += fy + (ty - fy) * progress

        elif mtype == "pulse":
            f_scale = mot["from"]
            t_scale = mot["to"]
            progress = 0.5 - 0.5 * math.cos(phase_time * math.pi * 2)
            t_data["scale"] *= f_scale + (t_scale - f_scale) * progress

        elif mtype == "fade":
            f_op = mot["from"]
            t_op = mot["to"]
            progress = 0.5 - 0.5 * math.cos(phase_time * math.pi * 2)
            t_data["opacity"] *= f_op + (t_op - f_op) * progress

        elif mtype == "keyframes":
            frames = mot["frames"]
            # Find surrounding keyframes
            if phase_time <= frames[0]["at"]:
                curr_kf = frames[0]
                t_data["dx"] += curr_kf.get("x", 0)
                t_data["dy"] += curr_kf.get("y", 0)
                t_data["rotation"] += curr_kf.get("rotation", 0)
                t_data["scale"] *= curr_kf.get("scale", 1.0)
                t_data["opacity"] *= curr_kf.get("opacity", 1.0)
            elif phase_time >= frames[-1]["at"]:
                curr_kf = frames[-1]
                t_data["dx"] += curr_kf.get("x", 0)
                t_data["dy"] += curr_kf.get("y", 0)
                t_data["rotation"] += curr_kf.get("rotation", 0)
                t_data["scale"] *= curr_kf.get("scale", 1.0)
                t_data["opacity"] *= curr_kf.get("opacity", 1.0)
            else:
                for i in range(len(frames) - 1):
                    k1 = frames[i]
                    k2 = frames[i + 1]
                    if k1["at"] <= phase_time <= k2["at"]:
                        span = k2["at"] - k1["at"]
                        local_p = (phase_time - k1["at"]) / max(1e-6, span)
                        t_data["dx"] += k1.get("x", 0) + (k2.get("x", 0) - k1.get("x", 0)) * local_p
                        t_data["dy"] += k1.get("y", 0) + (k2.get("y", 0) - k1.get("y", 0)) * local_p
                        t_data["rotation"] += k1.get("rotation", 0) + (k2.get("rotation", 0) - k1.get("rotation", 0)) * local_p
                        t_data["scale"] *= k1.get("scale", 1.0) + (k2.get("scale", 1.0) - k1.get("scale", 1.0)) * local_p
                        t_data["opacity"] *= k1.get("opacity", 1.0) + (k2.get("opacity", 1.0) - k1.get("opacity", 1.0)) * local_p
                        break

    return transforms


class PenechoAnimationItem(QGraphicsItem):
    """
    High-performance 60 FPS interactive QGraphicsItem scene player.
    Supports playback toggle (Play/Pause), scrubbing, speed modification,
    bounding box transformation, and full state serialization.
    """

    def __init__(self, scene_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self._raw_scene = scene_data
        self._scene = normalize_animation_scene(scene_data) or {
            "title": "Animation", "w": 360, "h": 260, "durationMs": 4000, "objects": [], "motions": []
        }
        self._width = float(self._scene.get("w", 360.0))
        self._height = float(self._scene.get("h", 260.0))
        self._header_height = 36.0
        self._control_bar_height = 32.0

        self._is_playing = True
        self._speed_multiplier = 1.0
        self._elapsed_ms = 0.0
        self._last_tick_time = time.perf_counter()

        # 60 FPS update timer
        self._timer = QTimer()
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

    def _on_tick(self):
        now = time.perf_counter()
        dt_ms = (now - self._last_tick_time) * 1000.0 * self._speed_multiplier
        self._last_tick_time = now

        if self._is_playing:
            self._elapsed_ms = (self._elapsed_ms + dt_ms) % max(1.0, float(self._scene.get("durationMs", 4000.0)))
            self.update()

    def toggle_playback(self):
        self._is_playing = not self._is_playing
        self._last_tick_time = time.perf_counter()
        self.update()

    def reset_playback(self):
        self._elapsed_ms = 0.0
        self._last_tick_time = time.perf_counter()
        self.update()

    def set_speed(self, speed: float):
        self._speed_multiplier = max(0.2, min(5.0, speed))

    def boundingRect(self) -> QRectF:
        total_h = self._header_height + self._height + self._control_bar_height
        return QRectF(0, 0, self._width, total_h)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.boundingRect()
        total_h = rect.height()

        # 1. Main frame container with rounded card design
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)
        painter.setPen(QPen(QColor("#3b82f6") if self.isSelected() else QColor("#e2e8f0"), 1.5))
        painter.setBrush(QBrush(QColor("#0f172a" if not self.isSelected() else "#0b1329")))
        painter.drawPath(path)

        # 2. Header Bar
        painter.setPen(QColor("#94a3b8"))
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        title = self._scene.get("title", "PenEcho Animation")
        painter.drawText(QRectF(14, 0, self._width - 28, self._header_height), Qt.AlignmentFlag.AlignVCenter, title)

        # Speed badge
        speed_text = f"{self._speed_multiplier:.1f}x"
        painter.setPen(QColor("#38bdf8"))
        painter.drawText(QRectF(self._width - 60, 0, 48, self._header_height), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, speed_text)

        # 3. Canvas Viewport Area
        viewport_rect = QRectF(0, self._header_height, self._width, self._height)
        painter.save()
        painter.setClipRect(viewport_rect)
        painter.translate(0, self._header_height)

        transforms = evaluate_scene_state(self._scene, self._elapsed_ms)

        for obj in self._scene.get("objects", []):
            oid = obj["id"]
            t_data = transforms.get(oid, {"dx": 0, "dy": 0, "rotation": 0, "scale": 1, "opacity": 1})
            
            painter.save()
            painter.setOpacity(t_data.get("opacity", 1.0))
            
            # Apply translations & rotation
            painter.translate(t_data.get("dx", 0), t_data.get("dy", 0))
            if t_data.get("rotation", 0) != 0:
                # Pivot center
                cx = obj.get("cx", obj.get("x", 0) + obj.get("w", 0) / 2)
                cy = obj.get("cy", obj.get("y", 0) + obj.get("h", 0) / 2)
                painter.translate(cx, cy)
                painter.rotate(t_data["rotation"])
                painter.scale(t_data["scale"], t_data["scale"])
                painter.translate(-cx, -cy)
            elif t_data.get("scale", 1.0) != 1.0:
                cx = obj.get("cx", obj.get("x", 0) + obj.get("w", 0) / 2)
                cy = obj.get("cy", obj.get("y", 0) + obj.get("h", 0) / 2)
                painter.translate(cx, cy)
                painter.scale(t_data["scale"], t_data["scale"])
                painter.translate(-cx, -cy)

            self._paint_object(painter, obj)
            painter.restore()

        painter.restore()

        # 4. Bottom Playback Control Bar & Scrubber
        ctrl_y = self._header_height + self._height
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#1e293b")))
        ctrl_path = QPainterPath()
        ctrl_path.addRoundedRect(QRectF(0, ctrl_y, self._width, self._control_bar_height), 0, 0)
        painter.drawPath(ctrl_path)

        # Progress bar
        duration = max(1.0, float(self._scene.get("durationMs", 4000.0)))
        prog = self._elapsed_ms / duration
        painter.fillRect(QRectF(0, ctrl_y, self._width, 3), QColor("#334155"))
        painter.fillRect(QRectF(0, ctrl_y, self._width * prog, 3), QColor("#3b82f6"))

        # Play / Pause icon
        painter.setPen(QColor("#f8fafc"))
        painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        play_symbol = "⏸" if self._is_playing else "▶"
        painter.drawText(QRectF(14, ctrl_y + 4, 24, self._control_bar_height - 4), Qt.AlignmentFlag.AlignVCenter, play_symbol)

        # Time code
        cur_sec = self._elapsed_ms / 1000.0
        tot_sec = duration / 1000.0
        time_text = f"{cur_sec:.1f}s / {tot_sec:.1f}s"
        painter.setPen(QColor("#94a3b8"))
        painter.setFont(QFont("Arial", 9))
        painter.drawText(QRectF(42, ctrl_y + 4, 120, self._control_bar_height - 4), Qt.AlignmentFlag.AlignVCenter, time_text)

        painter.restore()

    def _paint_object(self, painter: QPainter, obj: Dict[str, Any]):
        otype = obj["type"]
        fill = obj.get("fill")
        stroke = obj.get("stroke")
        lw = obj.get("lineWidth", 2)

        pen = QPen(QColor(stroke), lw) if stroke else Qt.PenStyle.NoPen
        brush = QBrush(QColor(fill)) if fill else Qt.BrushStyle.NoBrush
        painter.setPen(pen)
        painter.setBrush(brush)

        if otype == "circle":
            painter.drawEllipse(QPointF(obj["cx"], obj["cy"]), obj["r"], obj["r"])
        elif otype == "ellipse":
            painter.drawEllipse(QPointF(obj["cx"], obj["cy"]), obj["rx"], obj["ry"])
        elif otype == "rect":
            r = QRectF(obj["x"], obj["y"], obj["w"], obj["h"])
            rad = obj.get("radius", 0)
            if rad > 0:
                painter.drawRoundedRect(r, rad, rad)
            else:
                painter.drawRect(r)
        elif otype == "line":
            painter.drawLine(QPointF(obj["x1"], obj["y1"]), QPointF(obj["x2"], obj["y2"]))
        elif otype == "path":
            pts = obj.get("points", [])
            if len(pts) >= 2:
                path = QPainterPath()
                path.moveTo(pts[0][0], pts[0][1])
                for px, py in pts[1:]:
                    path.lineTo(px, py)
                if obj.get("closed"):
                    path.closeSubpath()
                painter.drawPath(path)
        elif otype == "text":
            painter.setPen(QPen(QColor(fill or "#f8fafc")))
            font = QFont(obj.get("fontFamily", "Arial"), int(obj.get("fontSize", 16)))
            if obj.get("fontWeight") == "700":
                font.setBold(True)
            painter.setFont(font)
            painter.drawText(QPointF(obj["x"], obj["y"]), obj.get("text", ""))

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        ctrl_y = self._header_height + self._height
        if event.pos().y() >= ctrl_y:
            # Clicked control bar
            if event.pos().x() < 40:
                self.toggle_playback()
            else:
                # Seek in timeline
                duration = max(1.0, float(self._scene.get("durationMs", 4000.0)))
                prog = _clamp(event.pos().x() / self._width, 0.0, 1.0)
                self._elapsed_ms = prog * duration
                self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        # Cycle speed 1.0x -> 1.5x -> 2.0x -> 0.5x -> 1.0x
        speeds = [0.5, 1.0, 1.5, 2.0]
        cur_idx = 1
        for i, s in enumerate(speeds):
            if abs(self._speed_multiplier - s) < 0.1:
                cur_idx = i
                break
        self._speed_multiplier = speeds[(cur_idx + 1) % len(speeds)]
        self.update()
        event.accept()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "PenechoAnimationItem",
            "x": self.pos().x(),
            "y": self.pos().y(),
            "z_value": self.zValue(),
            "scene": self._raw_scene,
            "speed": self._speed_multiplier,
            "is_playing": self._is_playing
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PenechoAnimationItem":
        item = cls(data.get("scene", {}))
        if "speed" in data:
            item._speed_multiplier = float(data["speed"])
        if "is_playing" in data:
            item._is_playing = bool(data["is_playing"])
        return item
