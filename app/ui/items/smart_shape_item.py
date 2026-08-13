"""
Smart Shape Canvas Item supporting all 7 shape types:
- Rectangle, Square, Circle, Ellipse, Straight Line, Arrow, Cloud

Integrates with BaseGraphicsItemMixin, ShapeResizeHandles, and ShapePropertiesPanel.
Preserves raw stroke history for future revert functionality.
"""

import math
from typing import Dict, Any, List, Tuple

from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsItem
from PyQt6.QtGui import QPen, QColor, QPainterPath, QBrush, QPolygonF
from PyQt6.QtCore import Qt, QRectF, QPointF, QLineF

from .base_item import BaseGraphicsItemMixin
from ..shape_metadata import SHAPE_METADATA, convert_px_to_unit, convert_unit_to_px
from ..stroke_processor import generate_arrowhead_polygon, generate_cloud_path_points, generate_regular_ngon


class SmartShapeItem(QGraphicsPathItem, BaseGraphicsItemMixin):
    """
    Unified canvas graphics item for snapped geometric shapes.
    """

    def __init__(self, 
                 shape_type: str, 
                 fit_data: dict, 
                 pen: QPen = None, 
                 raw_stroke: list = None, 
                 parent=None):
        super().__init__(parent)
        self.setup_base_properties()

        self.stroke_type = shape_type
        self.fit_data = fit_data or {}
        self.raw_stroke = raw_stroke or []
        self.classification_confidence = 0.95

        # Initialize default pen if not provided
        if pen is None:
            pen = QPen(QColor("#1c1c1e"), 3.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.setPen(pen)
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setZValue(10)

        # Store dimension parameters in canvas pixels
        self.dimensions_px: Dict[str, float] = {}

        # Set initial geometry based on shape type and fit data
        self._init_geometry_from_fit()
        self.update_path()

    def _init_geometry_from_fit(self):
        """Initializes internal position and dimensions_px from fit_data."""
        st = self.stroke_type

        if st == "circle":
            r = self.fit_data.get("radius", 40.0)
            cx, cy = self.fit_data.get("center", (0.0, 0.0))
            self.setPos(cx, cy)
            self.dimensions_px = {"radius": float(r)}

        elif st == "ellipse":
            w = self.fit_data.get("width", 80.0)
            h = self.fit_data.get("height", 50.0)
            cx, cy = self.fit_data.get("center", (0.0, 0.0))
            self.setPos(cx, cy)
            self.dimensions_px = {"width": float(w), "height": float(h)}

        elif st == "rectangle":
            bbox = self.fit_data.get("bbox", (0, 0, 100, 60))
            x, y, w, h = bbox
            cx = x + w / 2.0
            cy = y + h / 2.0
            self.setPos(cx, cy)
            self.dimensions_px = {"width": float(w), "height": float(h)}

        elif st == "square":
            side = self.fit_data.get("side", 70.0)
            bbox = self.fit_data.get("bbox", (0, 0, side, side))
            x, y, w, h = bbox
            cx = x + w / 2.0
            cy = y + h / 2.0
            self.setPos(cx, cy)
            self.dimensions_px = {"side": float(side)}

        elif st == "line":
            p1 = self.fit_data.get("p1", (0.0, 0.0))
            p2 = self.fit_data.get("p2", (100.0, 0.0))
            # Set pos at midpoint
            mx = (p1[0] + p2[0]) / 2.0
            my = (p1[1] + p2[1]) / 2.0
            self.setPos(mx, my)
            # Local coordinates relative to midpoint
            self._p1_local = (p1[0] - mx, p1[1] - my)
            self._p2_local = (p2[0] - mx, p2[1] - my)
            length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            self.dimensions_px = {"length": float(length)}

        elif st == "arrow":
            p1 = self.fit_data.get("p1", (0.0, 0.0))
            p2 = self.fit_data.get("p2", (100.0, 0.0))
            mx = (p1[0] + p2[0]) / 2.0
            my = (p1[1] + p2[1]) / 2.0
            self.setPos(mx, my)
            self._p1_local = (p1[0] - mx, p1[1] - my)
            self._p2_local = (p2[0] - mx, p2[1] - my)
            length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            self.dimensions_px = {"length": float(length)}

        elif st == "cloud":
            bbox = self.fit_data.get("bbox", (0, 0, 120, 80))
            x, y, w, h = bbox
            cx = x + w / 2.0
            cy = y + h / 2.0
            self.setPos(cx, cy)
            self.dimensions_px = {"width": float(w), "height": float(h)}

        elif st == "triangle":
            bbox = self.fit_data.get("bbox", (0, 0, 100, 100))
            x, y, w, h = bbox
            cx = x + w / 2.0
            cy = y + h / 2.0
            self.setPos(cx, cy)
            self.dimensions_px = {"width": float(w), "height": float(h), "num_sides": 3.0}

    def get_dimensions_px(self) -> Dict[str, float]:
        """Returns dictionary of shape dimensions in canvas pixels."""
        return dict(self.dimensions_px)

    def set_dimensions_px(self, dims: Dict[str, float]):
        """Updates shape dimensions in canvas pixels and regenerates path."""
        self.prepareGeometryChange()
        for k, v in dims.items():
            if v > 0:
                self.dimensions_px[k] = float(v)
        self.update_path()
        self.update()

    def itemChange(self, change, value):
        if change in [QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QGraphicsItem.GraphicsItemChange.ItemTransformHasChanged]:
            if hasattr(self, "_properties_panel") and self._properties_panel:
                self._properties_panel.update_position()
        return super().itemChange(change, value)

    def update_path(self):
        """Rebuilds QPainterPath matching active shape type and dimensions."""
        st = self.stroke_type
        path = QPainterPath()

        if st == "circle":
            r = max(1.0, self.dimensions_px.get("radius", 40.0))
            path.addEllipse(QRectF(-r, -r, 2.0 * r, 2.0 * r))

        elif st == "ellipse":
            w = max(1.0, self.dimensions_px.get("width", 80.0))
            h = max(1.0, self.dimensions_px.get("height", 50.0))
            path.addEllipse(QRectF(-w / 2.0, -h / 2.0, w, h))

        elif st == "rectangle":
            w = max(1.0, self.dimensions_px.get("width", 100.0))
            h = max(1.0, self.dimensions_px.get("height", 60.0))
            path.addRect(QRectF(-w / 2.0, -h / 2.0, w, h))

        elif st == "square":
            s = max(1.0, self.dimensions_px.get("side", 70.0))
            path.addRect(QRectF(-s / 2.0, -s / 2.0, s, s))

        elif st == "line":
            length = max(1.0, self.dimensions_px.get("length", 100.0))
            # Scale local endpoints to match length while preserving angle
            cur_len = math.hypot(self._p2_local[0] - self._p1_local[0], self._p2_local[1] - self._p1_local[1])
            if cur_len > 1e-4:
                scale = length / cur_len
                self._p1_local = (self._p1_local[0] * scale, self._p1_local[1] * scale)
                self._p2_local = (self._p2_local[0] * scale, self._p2_local[1] * scale)
            else:
                self._p1_local = (-length / 2.0, 0.0)
                self._p2_local = (length / 2.0, 0.0)
                
            path.moveTo(QPointF(*self._p1_local))
            path.lineTo(QPointF(*self._p2_local))

        elif st == "arrow":
            length = max(1.0, self.dimensions_px.get("length", 100.0))
            cur_len = math.hypot(self._p2_local[0] - self._p1_local[0], self._p2_local[1] - self._p1_local[1])
            if cur_len > 1e-4:
                scale = length / cur_len
                self._p1_local = (self._p1_local[0] * scale, self._p1_local[1] * scale)
                self._p2_local = (self._p2_local[0] * scale, self._p2_local[1] * scale)
            else:
                self._p1_local = (-length / 2.0, 0.0)
                self._p2_local = (length / 2.0, 0.0)

            # Shaft line
            path.moveTo(QPointF(*self._p1_local))
            path.lineTo(QPointF(*self._p2_local))

            # Triangular Arrowhead
            arrow_pts = generate_arrowhead_polygon(self._p1_local, self._p2_local)
            if len(arrow_pts) == 3:
                path.moveTo(QPointF(*arrow_pts[0]))
                path.lineTo(QPointF(*arrow_pts[1]))
                path.lineTo(QPointF(*arrow_pts[2]))
                path.lineTo(QPointF(*arrow_pts[0]))

        elif st == "cloud":
            w = max(10.0, self.dimensions_px.get("width", 120.0))
            h = max(10.0, self.dimensions_px.get("height", 80.0))
            bbox_local = (-w / 2.0, -h / 2.0, w, h)
            bumps = generate_cloud_path_points(bbox_local)
            
            if bumps:
                path.moveTo(QPointF(*bumps[0]["start"]))
                for b in bumps:
                    path.quadTo(QPointF(*b["control"]), QPointF(*b["end"]))
                path.closeSubpath()
            else:
                path.addEllipse(QRectF(-w / 2.0, -h / 2.0, w, h))

        elif st == "triangle":
            w = max(1.0, self.dimensions_px.get("width", 100.0))
            h = max(1.0, self.dimensions_px.get("height", 100.0))
            n = int(round(self.dimensions_px.get("num_sides", 3.0)))
            n = max(3, n)

            rx = w / 2.0
            ry = h / 2.0
            angle_offset = -math.pi / 2.0
            poly_pts = []
            for i in range(n):
                theta = angle_offset + 2.0 * math.pi * i / n
                poly_pts.append(QPointF(rx * math.cos(theta), ry * math.sin(theta)))

            polygon = QPolygonF(poly_pts)
            path.addPolygon(polygon)

        self.setPath(path)

    def contextMenuEvent(self, event):
        self.build_context_menu(event.screenPos())

    def to_dict(self) -> dict:
        """Serializes SmartShapeItem state into a dictionary payload."""
        pen = self.pen()
        return {
            "type": "SmartShapeItem",
            "stroke_type": self.stroke_type,
            "x": self.x(),
            "y": self.y(),
            "color": pen.color().name(QColor.NameFormat.HexArgb),
            "width": pen.widthF(),
            "dimensions_px": self.dimensions_px,
            "raw_stroke": self.raw_stroke,
            "z_value": self.zValue()
        }
