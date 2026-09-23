"""
Freehand Lasso Selection System & Transformation Overlay for AI-TUTOR.

In addition to the existing move/resize/accept/cancel controls, the overlay now
exposes a Video action that sends the *actual selected QGraphicsItems* plus a
supplementary raster crop to the whiteboard-aware video pipeline.
"""

import math
from typing import List, Tuple, Dict, Any, Optional
from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QPainterPath, QFont
from PyQt6.QtCore import Qt, QRectF, QPointF


def point_in_polygon(px: float, py: float, polygon: List[Tuple[float, float]]) -> bool:
    if len(polygon) < 3:
        return False
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        crosses = ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / ((yj - yi) + 1e-12) + xi)
        if crosses:
            inside = not inside
        j = i
    return inside


def point_segment_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx = x2 - x1
    dy = y2 - y1
    len_sq = dx * dx + dy * dy
    if len_sq == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / len_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def point_near_path(px: float, py: float, path: List[Tuple[float, float]], tolerance: float = 6.0) -> bool:
    if len(path) < 2:
        return False
    for i in range(len(path) - 1):
        if point_segment_distance(px, py, path[i][0], path[i][1], path[i + 1][0], path[i + 1][1]) <= tolerance:
            return True
    return False


def polygon_bounds(points: List[Tuple[float, float]]) -> Optional[Tuple[float, float, float, float]]:
    if not points:
        return None
    min_x = min(p[0] for p in points)
    min_y = min(p[1] for p in points)
    max_x = max(p[0] for p in points)
    max_y = max(p[1] for p in points)
    return (min_x, min_y, max(1.0, max_x - min_x), max(1.0, max_y - min_y))


def map_point(pt: Tuple[float, float], src_box: Tuple[float, float, float, float], tgt_box: Tuple[float, float, float, float]) -> Tuple[float, float]:
    sx, sy, sw, sh = src_box
    tx, ty, tw, th = tgt_box
    scale_x = tw / sw if sw > 0 else 1.0
    scale_y = th / sh if sh > 0 else 1.0
    return (tx + (pt[0] - sx) * scale_x, ty + (pt[1] - sy) * scale_y)


class PenechoLassoOverlay(QGraphicsItem):
    """Interactive lasso selection overlay with a structured-video action."""

    def __init__(self, lasso_points: List[Tuple[float, float]], selected_items: List[QGraphicsItem], parent=None):
        super().__init__(parent)
        self.setZValue(9999)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)

        self.lasso_points = list(lasso_points)
        self.selected_items = list(selected_items)

        bounds = polygon_bounds(self.lasso_points)
        if bounds:
            self._box = list(bounds)
            self._orig_box = list(bounds)
        else:
            self._box = [0, 0, 100, 100]
            self._orig_box = [0, 0, 100, 100]

        self._initial_item_positions = {item: item.pos() for item in self.selected_items}
        self._handle_size = 18.0
        self._active_action: Optional[str] = None
        self._drag_start_pos: Optional[QPointF] = None
        self._video_request_in_flight = False

    def boundingRect(self) -> QRectF:
        x, y, w, h = self._box
        pad = 46.0
        return QRectF(x - pad, y - pad, w + pad * 2, h + pad * 2)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        x, y, w, h = self._box

        if len(self.lasso_points) >= 3:
            path = QPainterPath()
            path.moveTo(self.lasso_points[0][0], self.lasso_points[0][1])
            for pt in self.lasso_points[1:]:
                path.lineTo(pt[0], pt[1])
            path.closeSubpath()
            painter.setBrush(QBrush(QColor(59, 130, 246, 25)))
            painter.setPen(QPen(QColor("#3b82f6"), 1.5, Qt.PenStyle.DashLine))
            painter.drawPath(path)

        box_rect = QRectF(x, y, w, h)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#2563eb"), 2.0))
        painter.drawRect(box_rect)

        painter.setBrush(QBrush(QColor("#2563eb")))
        painter.setPen(QPen(QColor("#ffffff"), 1.5))
        painter.drawEllipse(QPointF(x + w / 2, y - 16), 10, 10)
        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(x + w / 2 - 10, y - 26, 20, 20), Qt.AlignmentFlag.AlignCenter, "✥")

        painter.drawEllipse(QPointF(x + w, y + h), 8, 8)

        painter.setBrush(QBrush(QColor("#10b981")))
        painter.drawEllipse(QPointF(x + w + 16, y - 16), 10, 10)
        painter.drawText(QRectF(x + w + 6, y - 26, 20, 20), Qt.AlignmentFlag.AlignCenter, "✓")

        painter.setBrush(QBrush(QColor("#ef4444")))
        painter.drawEllipse(QPointF(x - 16, y - 16), 10, 10)
        painter.drawText(QRectF(x - 26, y - 26, 20, 20), Qt.AlignmentFlag.AlignCenter, "✕")

        # New: generate video from this exact structured selection.
        painter.setBrush(QBrush(QColor("#7c3aed")))
        painter.drawEllipse(QPointF(x + w + 18, y + h + 18), 12, 12)
        painter.setPen(QPen(QColor("#ffffff"), 1.3))
        painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        painter.drawText(QRectF(x + w + 6, y + h + 6, 24, 24), Qt.AlignmentFlag.AlignCenter, "▶")

        badge_rect = QRectF(x + w / 2 - 48, y + h + 10, 96, 22)
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.setPen(QPen(QColor("#e2e8f0"), 1.5))
        painter.drawRoundedRect(badge_rect, 6, 6)
        painter.setPen(QPen(QColor("#475569")))
        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, f"{len(self.selected_items)} Items • Video ▶")
        painter.restore()

    def mousePressEvent(self, event):
        pos = event.pos()
        x, y, w, h = self._box

        if math.hypot(pos.x() - (x + w + 18), pos.y() - (y + h + 18)) <= 17:
            self._request_video_from_selection()
            event.accept()
            return
        if math.hypot(pos.x() - (x + w + 16), pos.y() - (y - 16)) <= 15:
            self.commit_selection()
            event.accept()
            return
        if math.hypot(pos.x() - (x - 16), pos.y() - (y - 16)) <= 15:
            self.cancel_selection()
            event.accept()
            return
        if math.hypot(pos.x() - (x + w), pos.y() - (y + h)) <= 15:
            self._active_action = "resize"
            self._drag_start_pos = pos
            event.accept()
            return
        if math.hypot(pos.x() - (x + w / 2), pos.y() - (y - 16)) <= 15 or QRectF(x, y, w, h).contains(pos):
            self._active_action = "move"
            self._drag_start_pos = pos
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._active_action == "move" and self._drag_start_pos:
            delta = event.pos() - self._drag_start_pos
            self._drag_start_pos = event.pos()
            self.prepareGeometryChange()
            self._box[0] += delta.x()
            self._box[1] += delta.y()
            self.lasso_points = [(x + delta.x(), y + delta.y()) for x, y in self.lasso_points]
            for item in self.selected_items:
                item.setPos(item.pos().x() + delta.x(), item.pos().y() + delta.y())
            self.update()
            event.accept()
            return
        if self._active_action == "resize" and self._drag_start_pos:
            self.prepareGeometryChange()
            self._box[2] = max(30.0, event.pos().x() - self._box[0])
            self._box[3] = max(30.0, event.pos().y() - self._box[1])
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._active_action = None
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)

    def _request_video_from_selection(self):
        if self._video_request_in_flight:
            return
        scene = self.scene()
        if not scene or not self.selected_items:
            return
        self._video_request_in_flight = True
        try:
            from app.services.tutoring.selection_payload import (
                build_board_selection_payload,
                infer_prompt_from_selection,
            )
            from app.services.tutoring.video_gen_client import request_video_generation
            from ..items.video_float_item import VideoFloatItem

            board_id = ""
            main_window = None
            try:
                views = scene.views()
                main_window = views[0].window() if views else None
                current_board = getattr(main_window, "current_board", None)
                board_id = str(getattr(current_board, "board_id", "") or "")
            except Exception:
                pass

            payload = build_board_selection_payload(
                scene=scene,
                selected_items=self.selected_items,
                lasso_points=self.lasso_points,
                user_instruction="Explain the selected whiteboard region using the clearest, shortest visual lesson.",
                board_id=board_id,
            )
            prompt = infer_prompt_from_selection(payload)
            subject_id = ""
            try:
                subject_view = getattr(main_window, "subject_detail_view", None)
                subject_id = str(getattr(subject_view, "current_subject_id", "") or "")
            except Exception:
                pass

            job_id = request_video_generation(
                selected_text=prompt,
                subject_id=subject_id,
                selection_payload=payload,
            )
            x, y, w, _ = self._box
            video_item = VideoFloatItem(
                job_id=job_id,
                title=f"Selection Video: {prompt[:28]}...",
                video_url_or_path="",
            )
            video_item.setPos(x + w + 70, y)
            scene.addItem(video_item)
            if hasattr(scene, "scene_changed"):
                scene.scene_changed.emit()
        except Exception as exc:
            print(f"[PenechoLassoOverlay] Video request failed: {exc}")
        finally:
            self._video_request_in_flight = False

    def commit_selection(self):
        scene = self.scene()
        if scene:
            scene.removeItem(self)
            if hasattr(scene, "scene_changed"):
                scene.scene_changed.emit()

    def cancel_selection(self):
        for item, orig_pos in self._initial_item_positions.items():
            item.setPos(orig_pos)
        scene = self.scene()
        if scene:
            scene.removeItem(self)
            if hasattr(scene, "scene_changed"):
                scene.scene_changed.emit()
