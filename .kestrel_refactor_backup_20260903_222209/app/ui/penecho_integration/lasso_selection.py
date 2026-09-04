"""
Freehand Lasso Selection System & Transformation Overlay for AI-TUTOR.
Ported from penecho/public/selection.js.

Provides:
1. Polygon geometry utilities:
   - Ray-casting point-in-polygon test.
   - Point-to-segment distance and tolerance calculation.
   - Bounding box transformations (mapping, resizing, moving).
2. PenechoLassoOverlay: Interactive freehand lasso selection overlay with
   bounding box handles, moving, scaling, recoloring, accept, and cancel controls.
"""

import math
from typing import List, Tuple, Dict, Any, Optional
from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QPainterPath, QPolygonF, QFont
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QObject


def point_in_polygon(px: float, py: float, polygon: List[Tuple[float, float]]) -> bool:
    """
    Ray-casting algorithm to determine if point (px, py) is inside polygon.
    """
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
    """
    Interactive Freehand Lasso Selection Overlay.
    Encloses selected canvas items with a bounding box and action controls.
    """

    def __init__(self, lasso_points: List[Tuple[float, float]], selected_items: List[QGraphicsItem], parent=None):
        super().__init__(parent)
        self.setZValue(9999) # Float above everything
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)

        self.lasso_points = list(lasso_points)
        self.selected_items = list(selected_items)
        
        # Calculate initial bounding box
        bounds = polygon_bounds(self.lasso_points)
        if bounds:
            self._box = list(bounds) # [x, y, w, h]
            self._orig_box = list(bounds)
        else:
            self._box = [0, 0, 100, 100]
            self._orig_box = [0, 0, 100, 100]

        # Initial relative positions of selected items
        self._initial_item_positions = {item: item.pos() for item in self.selected_items}

        self._handle_size = 18.0
        self._active_action: Optional[str] = None
        self._drag_start_pos: Optional[QPointF] = None

    def boundingRect(self) -> QRectF:
        x, y, w, h = self._box
        pad = 40.0
        return QRectF(x - pad, y - pad, w + pad * 2, h + pad * 2)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        x, y, w, h = self._box

        # 1. Draw Freehand Lasso Path
        if len(self.lasso_points) >= 3:
            path = QPainterPath()
            path.moveTo(self.lasso_points[0][0], self.lasso_points[0][1])
            for pt in self.lasso_points[1:]:
                path.lineTo(pt[0], pt[1])
            path.closeSubpath()

            # Fill translucent blue
            painter.setBrush(QBrush(QColor(59, 130, 246, 25)))
            painter.setPen(QPen(QColor("#3b82f6"), 1.5, Qt.PenStyle.DashLine))
            painter.drawPath(path)

        # 2. Draw Transformation Bounding Box
        box_rect = QRectF(x, y, w, h)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#2563eb"), 2.0))
        painter.drawRect(box_rect)

        # 3. Action Controls:
        # Move handle (top center)
        painter.setBrush(QBrush(QColor("#2563eb")))
        painter.setPen(QPen(QColor("#ffffff"), 1.5))
        painter.drawEllipse(QPointF(x + w / 2, y - 16), 10, 10)
        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(x + w / 2 - 10, y - 26, 20, 20), Qt.AlignmentFlag.AlignCenter, "✥")

        # Resize handle (bottom right)
        painter.drawEllipse(QPointF(x + w, y + h), 8, 8)

        # Accept button (top right)
        painter.setBrush(QBrush(QColor("#10b981")))
        painter.drawEllipse(QPointF(x + w + 16, y - 16), 10, 10)
        painter.drawText(QRectF(x + w + 6, y - 26, 20, 20), Qt.AlignmentFlag.AlignCenter, "✓")

        # Cancel button (top left)
        painter.setBrush(QBrush(QColor("#ef4444")))
        painter.drawEllipse(QPointF(x - 16, y - 16), 10, 10)
        painter.drawText(QRectF(x - 26, y - 26, 20, 20), Qt.AlignmentFlag.AlignCenter, "✕")

        # Recolor action badge (bottom center)
        badge_rect = QRectF(x + w / 2 - 35, y + h + 10, 70, 22)
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.setPen(QPen(QColor("#e2e8f0"), 1.5))
        painter.drawRoundedRect(badge_rect, 6, 6)
        painter.setPen(QPen(QColor("#475569")))
        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, f"{len(self.selected_items)} Items")

        painter.restore()

    def mousePressEvent(self, event):
        pos = event.pos()
        x, y, w, h = self._box

        # Hit test actions
        if math.hypot(pos.x() - (x + w + 16), pos.y() - (y - 16)) <= 15:
            # Commit / Accept
            self.commit_selection()
            event.accept()
            return
        elif math.hypot(pos.x() - (x - 16), pos.y() - (y - 16)) <= 15:
            # Cancel
            self.cancel_selection()
            event.accept()
            return
        elif math.hypot(pos.x() - (x + w), pos.y() - (y + h)) <= 15:
            # Resize
            self._active_action = "resize"
            self._drag_start_pos = pos
            event.accept()
            return
        elif math.hypot(pos.x() - (x + w / 2), pos.y() - (y - 16)) <= 15 or QRectF(x, y, w, h).contains(pos):
            # Move
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
            # Move selected items
            for item in self.selected_items:
                item.setPos(item.pos().x() + delta.x(), item.pos().y() + delta.y())
            self.update()
            event.accept()
            return
        elif self._active_action == "resize" and self._drag_start_pos:
            self.prepareGeometryChange()
            new_w = max(30.0, event.pos().x() - self._box[0])
            new_h = max(30.0, event.pos().y() - self._box[1])
            self._box[2] = new_w
            self._box[3] = new_h
            self.update()
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._active_action = None
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)

    def commit_selection(self):
        """Commits transformed items and removes overlay."""
        scene = self.scene()
        if scene:
            scene.removeItem(self)
            if hasattr(scene, "scene_changed"):
                scene.scene_changed.emit()

    def cancel_selection(self):
        """Restores original item positions and removes overlay."""
        for item, orig_pos in self._initial_item_positions.items():
            item.setPos(orig_pos)
        scene = self.scene()
        if scene:
            scene.removeItem(self)
            if hasattr(scene, "scene_changed"):
                scene.scene_changed.emit()
