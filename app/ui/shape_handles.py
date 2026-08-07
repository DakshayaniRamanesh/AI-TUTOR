"""
Generic Shape Resize Handles for PyQt6 Canvas Shapes.

Attaches to any SmartShapeItem based on SHAPE_METADATA handle rules.
Supports live interactive handle dragging for all 7 shape types:
- Circle (4 circumference handles)
- Ellipse (4 cardinal handles)
- Rectangle (8 boundary handles)
- Square (8 boundary handles with 1:1 lock)
- Straight Line & Arrow (2 endpoint handles)
- Cloud (4 corner handles)

Bug-1 & Bug-2 Fixes:
- Added shape() override returning ONLY handle regions so clicks on the shape body
  pass through to SmartShapeItem for native moving/dragging.
- Added SHAPE_DEBUG logs for handle press and drag events.
- Smooth handle-drag geometry recalculations for all 7 shape types.
"""

import math
from typing import Optional

from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtGui import QPen, QColor, QBrush, QPainter, QPainterPath
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QObject

from .shape_metadata import SHAPE_METADATA
from .stroke_processor import SHAPE_DEBUG


class HandleSignalRelay(QObject):
    """QObject helper relay for pyqtSignal in QGraphicsItem."""
    geometry_changed = pyqtSignal()


class ShapeResizeHandles(QGraphicsItem):
    """
    Generic reusable resize handles overlay attached to an active SmartShapeItem.
    """

    HANDLE_SIZE: float = 8.0

    def __init__(self, target_item, parent=None):
        super().__init__(parent)
        self.target_item = target_item
        self.setParentItem(target_item)
        self.setZValue(100)

        self.signals = HandleSignalRelay()
        self._active_handle_index: Optional[int] = None
        self._drag_start_pos: Optional[QPointF] = None
        self._drag_start_dims: dict = {}
        self._drag_start_p1: Optional[tuple] = None
        self._drag_start_p2: Optional[tuple] = None

    def boundingRect(self) -> QRectF:
        if not self.target_item:
            return QRectF()
        rect = self.target_item.boundingRect()
        m = self.HANDLE_SIZE + 4.0
        return rect.adjusted(-m, -m, m, m)

    def shape(self) -> QPainterPath:
        """
        Defines hit-test region for handle overlay.
        Returns ONLY the small handle areas so clicks inside the shape body
        pass through directly to SmartShapeItem for native dragging.
        """
        path = QPainterPath()
        positions = self.get_handle_positions()
        hs = self.HANDLE_SIZE + 6.0
        for name, pt in positions:
            path.addEllipse(QRectF(pt.x() - hs / 2.0, pt.y() - hs / 2.0, hs, hs))
        return path

    def get_handle_positions(self) -> list[tuple[str, QPointF]]:
        """Computes current local handle positions based on shape type and dimensions."""
        if not self.target_item:
            return []

        st = self.target_item.stroke_type
        dims = self.target_item.dimensions_px
        positions = []

        if st == "circle":
            r = dims.get("radius", 40.0)
            positions = [
                ("right", QPointF(r, 0)),
                ("bottom", QPointF(0, r)),
                ("left", QPointF(-r, 0)),
                ("top", QPointF(0, -r))
            ]

        elif st in ["ellipse", "rectangle", "square", "cloud"]:
            w = dims.get("width", dims.get("side", 80.0))
            h = dims.get("height", dims.get("side", 50.0))
            hw, hh = w / 2.0, h / 2.0

            if st in ["rectangle", "square"]:
                positions = [
                    ("top_left", QPointF(-hw, -hh)),
                    ("top_mid", QPointF(0, -hh)),
                    ("top_right", QPointF(hw, -hh)),
                    ("right_mid", QPointF(hw, 0)),
                    ("bottom_right", QPointF(hw, hh)),
                    ("bottom_mid", QPointF(0, hh)),
                    ("bottom_left", QPointF(-hw, hh)),
                    ("left_mid", QPointF(-hw, 0))
                ]
            elif st == "cloud":
                positions = [
                    ("top_left", QPointF(-hw, -hh)),
                    ("top_right", QPointF(hw, -hh)),
                    ("bottom_right", QPointF(hw, hh)),
                    ("bottom_left", QPointF(-hw, hh))
                ]
            elif st == "ellipse":
                positions = [
                    ("right", QPointF(hw, 0)),
                    ("bottom", QPointF(0, hh)),
                    ("left", QPointF(-hw, 0)),
                    ("top", QPointF(0, -hh))
                ]

        elif st in ["line", "arrow"]:
            p1_loc = getattr(self.target_item, "_p1_local", (-50.0, 0.0))
            p2_loc = getattr(self.target_item, "_p2_local", (50.0, 0.0))
            positions = [
                ("p1", QPointF(*p1_loc)),
                ("p2", QPointF(*p2_loc))
            ]

        return positions

    def paint(self, painter: QPainter, option, widget=None):
        """Draws resize handles overlay."""
        positions = self.get_handle_positions()
        if not positions:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Bounding border guide
        painter.setPen(QPen(QColor("#007aff"), 1.0, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        rect = self.target_item.boundingRect()
        painter.drawRect(rect)

        # Handle rects
        painter.setPen(QPen(QColor("#007aff"), 1.5))
        painter.setBrush(QBrush(QColor("#ffffff")))
        hs = self.HANDLE_SIZE

        for name, pt in positions:
            handle_rect = QRectF(pt.x() - hs / 2.0, pt.y() - hs / 2.0, hs, hs)
            painter.drawEllipse(handle_rect)

    def mousePressEvent(self, event):
        pos = event.pos()
        positions = self.get_handle_positions()
        hs = self.HANDLE_SIZE + 6.0

        for idx, (name, pt) in enumerate(positions):
            if QRectF(pt.x() - hs / 2.0, pt.y() - hs / 2.0, hs, hs).contains(pos):
                self._active_handle_index = idx
                self._drag_start_pos = event.pos()
                self._drag_start_dims = self.target_item.get_dimensions_px()
                self._drag_start_p1 = getattr(self.target_item, "_p1_local", None)
                self._drag_start_p2 = getattr(self.target_item, "_p2_local", None)
                if SHAPE_DEBUG:
                    print(f"[ShapeResizeHandles] MousePress on handle '{name}' (idx={idx})", flush=True)
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._active_handle_index is not None and self.target_item:
            st = self.target_item.stroke_type
            pos = event.pos()
            delta = pos - self._drag_start_pos
            dims = dict(self._drag_start_dims)

            if SHAPE_DEBUG:
                print(f"[ShapeResizeHandles] MouseMove dragging handle idx={self._active_handle_index} pos=({pos.x():.1f}, {pos.y():.1f})", flush=True)

            if st == "circle":
                dist = math.hypot(pos.x(), pos.y())
                new_r = max(5.0, dist)
                self.target_item.set_dimensions_px({"radius": new_r})

            elif st == "square":
                dist = math.hypot(pos.x(), pos.y())
                new_side = max(5.0, dist * 2.0 / math.sqrt(2.0) if "top" in self.get_handle_positions()[self._active_handle_index][0] else dist * 2.0)
                self.target_item.set_dimensions_px({"side": new_side})

            elif st in ["rectangle", "ellipse", "cloud"]:
                w = dims.get("width", 80.0)
                h = dims.get("height", 50.0)
                idx = self._active_handle_index
                positions = self.get_handle_positions()
                name, _ = positions[idx]

                if "right" in name:
                    w = max(10.0, pos.x() * 2.0)
                if "left" in name:
                    w = max(10.0, -pos.x() * 2.0)
                if "bottom" in name:
                    h = max(10.0, pos.y() * 2.0)
                if "top" in name:
                    h = max(10.0, -pos.y() * 2.0)

                self.target_item.set_dimensions_px({"width": w, "height": h})

            elif st in ["line", "arrow"]:
                idx = self._active_handle_index
                if idx == 0:  # Drag p1
                    self.target_item._p1_local = (pos.x(), pos.y())
                else:  # Drag p2
                    self.target_item._p2_local = (pos.x(), pos.y())

                new_len = math.hypot(
                    self.target_item._p2_local[0] - self.target_item._p1_local[0],
                    self.target_item._p2_local[1] - self.target_item._p1_local[1]
                )
                self.target_item.dimensions_px["length"] = max(1.0, float(new_len))
                self.target_item.update_path()

            self.update()
            self.prepareGeometryChange()
            self.signals.geometry_changed.emit()
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._active_handle_index is not None:
            if SHAPE_DEBUG:
                print(f"[ShapeResizeHandles] MouseRelease handle drag finished.", flush=True)
            self._active_handle_index = None
            self._drag_start_pos = None
            event.accept()
            return
        super().mouseReleaseEvent(event)
