"""
Freeform Canvas Scene (Infinite SceneRect, Dotted & Ruled Paper Backgrounds, Freehand Drawing, Shape Snapping & Serialization)
"""

import math
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPathItem, QGraphicsProxyWidget
from PyQt6.QtGui import QPen, QColor, QBrush, QPainterPath, QPainter
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, pyqtSignal

from .items.ink_stroke import InkStroke
from .items.sticky_note import StickyNote
from .items.handwriting_note import HandwritingNote
from .items.table_item import TableItem
from .items.card_item import CardItem
from .items.graph_card import GraphCard
from .items.video_float_item import VideoFloatItem
from .items.answer_bubble import AnswerBubble
from .items.group_selection import GroupSelection
from .items.image_item import ImageItem
from .items.smart_shape_item import SmartShapeItem
from .shape_handles import ShapeResizeHandles
from .shape_properties_panel import ShapePropertiesPanel
from .stroke_processor import (
    StrokeProcessor, HOLD_DURATION_MS, HOLD_MOVE_THRESHOLD_PX, SHAPE_DEBUG
)

class CanvasScene(QGraphicsScene):
    ink_written_detected = pyqtSignal(str, QPointF)

    def __init__(self, parent=None):
        super().__init__(parent)
        # Infinite canvas bounds
        self.setSceneRect(QRectF(-50000, -50000, 100000, 100000))
        
        # Background mode: "dotted" or "ruled" (ruled is default notebook mode)
        self.background_mode = "ruled"
        
        # Active tool state: "select", "pen", "highlighter", "eraser"
        self.active_tool = "select"
        self.pen_color = "#1c1c1e"
        self.pen_width = 3.0
        self.highlighter_color = "#ffe066"
        
        self.stroke_processor = StrokeProcessor(enable_smart_shapes=True, enable_smoothing=True)
        self._current_path_item = None
        self._current_painter_path = None
        self._stroke_start_pos = None
        self._is_erasing = False

        # Live Hold-to-Snap State Machine
        self._hold_snap_timer = QTimer(self)
        self._hold_snap_timer.setSingleShot(True)
        self._hold_snap_timer.timeout.connect(self._on_hold_snap_timeout)
        self._hold_last_pos = None
        self._is_live_snapped = False
        self._snapped_shape_item = None

        # Active Shape & Overlay Controls
        self._active_shape_item: SmartShapeItem = None
        self._active_handles: ShapeResizeHandles = None
        self._active_properties_panel: ShapePropertiesPanel = None

        # Auto-convert handwriting timer (Apple Notes Math Notes style)
        self._recent_ink_strokes = []
        self._auto_convert_timer = QTimer(self)
        self._auto_convert_timer.setSingleShot(True)
        self._auto_convert_timer.timeout.connect(self._on_auto_convert_ink)

    def set_highlighter_color(self, color_hex: str):
        self.highlighter_color = color_hex
        self.active_tool = "highlighter"

    def set_background_mode(self, mode: str):
        if mode in ["dotted", "ruled"]:
            self.background_mode = mode
            self.update()

    def drawBackground(self, painter: QPainter, rect: QRectF):
        painter.fillRect(rect, QColor("#f4f4f6"))
        
        grid_size = 28
        left = int(rect.left()) - (int(rect.left()) % grid_size)
        top = int(rect.top()) - (int(rect.top()) % grid_size)
        right = int(rect.right())
        bottom = int(rect.bottom())

        if self.background_mode == "dotted":
            painter.setPen(QPen(QColor("#c7c7cc"), 1.5))
            for x in range(left, right, grid_size):
                for y in range(top, bottom, grid_size):
                    painter.drawPoint(x, y)
                    
        elif self.background_mode == "ruled":
            painter.setPen(QPen(QColor("#d1d1d6"), 1))
            for y in range(top, bottom, grid_size):
                painter.drawLine(left, y, right, y)

    def erase_items_at(self, pos: QPointF):
        items = self.items(pos)
        for item in items:
            if item.scene() == self:
                if item == self._active_handles or item == self._active_properties_panel:
                    continue
                if item == self._active_shape_item:
                    self.deactivate_active_shape()
                self.removeItem(item)

    def erase_selected_items(self):
        for item in self.selectedItems():
            if item == self._active_shape_item:
                self.deactivate_active_shape()
            self.removeItem(item)

    def clear_all(self):
        self.deactivate_active_shape()
        self.clear()

    def activate_shape(self, shape_item: SmartShapeItem):
        """Activates a SmartShapeItem, attaching interactive resize handles and properties panel."""
        if not shape_item or shape_item.scene() != self:
            return

        if self._active_shape_item == shape_item:
            return

        self.deactivate_active_shape()

        self._active_shape_item = shape_item
        self._active_handles = ShapeResizeHandles(shape_item)
        # Note: _active_handles is a child item (setParentItem(shape_item)), so it is automatically in the scene.

        self._active_properties_panel = ShapePropertiesPanel(shape_item)
        # Note: _active_properties_panel is parented to shape_item (setParentItem), so it is automatically in the scene.

        # Connect live handle drag signal to toolbar refresh
        self._active_handles.signals.geometry_changed.connect(self._active_properties_panel.refresh)

    def deactivate_active_shape(self):
        """Deactivates active shape and hides handles and properties toolbar.
        Also clears Qt's native selection state so selectedItems() stays in sync
        with the visual deselection — preventing the Delete handler from acting on
        a shape that the user has already visually dismissed.
        """
        if self._active_handles:
            self._active_handles.setParentItem(None)
            if self._active_handles.scene() == self:
                self.removeItem(self._active_handles)
            self._active_handles = None

        if self._active_properties_panel:
            self._active_properties_panel.detach_from_scene()
            if self._active_properties_panel.scene() == self:
                self.removeItem(self._active_properties_panel)
            self._active_properties_panel = None

        # Always clear Qt selection state so Delete/Backspace key handler (which
        # reads scene.selectedItems()) cannot delete a shape that is no longer
        # visually active.  clearSelection() is safe to call even when nothing
        # is selected.
        self.clearSelection()

        self._active_shape_item = None

    def _on_hold_snap_timeout(self):
        """Fires only when user holds cursor steady for HOLD_DURATION_MS after drawing.
        Delegates classification and snapping entirely to StrokeProcessor.classify_and_snap.
        Shape snapping must NEVER happen on release — only here.
        """
        if SHAPE_DEBUG:
            pt_count = len(self.stroke_processor.raw_points) if self.stroke_processor else 0
            print(f"[HoldSnapTimer] TIMEOUT FIRED! Evaluating stroke with {pt_count} points...", flush=True)

        if not self._current_path_item or not self.stroke_processor.raw_points:
            if SHAPE_DEBUG:
                print(f"[HoldSnapTimer] Timeout aborted: missing path_item or raw_points", flush=True)
            return

        tool_name = self.active_tool
        color = self.highlighter_color if tool_name == "highlighter" else self.pen_color

        snapped_item = self.stroke_processor.classify_and_snap(
            color=color,
            width=self.pen_width,
            tool_mode=tool_name
        )

        if isinstance(snapped_item, SmartShapeItem):
            if SHAPE_DEBUG:
                print(f"[HoldSnapTimer] SNAP SUCCESS! Replacing raw stroke with SmartShapeItem({snapped_item.stroke_type}) live while held.", flush=True)
            # Hide live raw path and show snapped shape
            if self._current_path_item and self._current_path_item.scene() == self:
                self.removeItem(self._current_path_item)

            self.addItem(snapped_item)
            self._snapped_shape_item = snapped_item
            self._is_live_snapped = True
            self.activate_shape(snapped_item)
        else:
            if SHAPE_DEBUG:
                print(f"[HoldSnapTimer] Classified as handwriting. Kept raw stroke.", flush=True)

    def to_dict_list(self) -> list[dict]:
        items_data = []
        for item in self.items():
            if hasattr(item, "to_dict") and item not in [self._active_handles, self._active_properties_panel]:
                try:
                    items_data.append(item.to_dict())
                except Exception as err:
                    print(f"[CanvasScene] Notice serializing item: {err}")
        return items_data

    def load_from_dict_list(self, items_data: list[dict], video_requested_callback=None, solve_requested_callback=None):
        self.clear_all()
        if not items_data:
            return

        for data in items_data:
            itype = data.get("type")
            x = data.get("x", 0)
            y = data.get("y", 0)

            item = None
            if itype == "SmartShapeItem":
                pen = QPen(QColor(data.get("color", "#1c1c1e")), data.get("width", 3.0))
                item = SmartShapeItem(
                    shape_type=data.get("stroke_type", "rectangle"),
                    fit_data={},
                    pen=pen,
                    raw_stroke=data.get("raw_stroke", [])
                )
                dims = data.get("dimensions_px", {})
                if dims:
                    item.set_dimensions_px(dims)
            elif itype == "StickyNote":
                item = StickyNote(text=data.get("text", ""), color_key=data.get("color_key", "yellow"))
            elif itype == "HandwritingNote":
                item = HandwritingNote(text=data.get("text", ""))
            elif itype == "TableItem":
                item = TableItem(headers=data.get("headers"), rows=data.get("rows"))
            elif itype == "CardItem":
                item = CardItem(title=data.get("title", "Card"), content=data.get("content", ""))
            elif itype == "GraphCard":
                item = GraphCard(title=data.get("title", "Plot"), image_path=data.get("image_path", ""))
            elif itype == "VideoFloatItem":
                item = VideoFloatItem(
                    job_id=data.get("job_id", ""),
                    title=data.get("title", "Video"),
                    video_url_or_path=data.get("video_path", "")
                )
            elif itype == "AnswerBubble":
                item = AnswerBubble(
                    question=data.get("question", ""),
                    full_text=data.get("full_text", "")
                )
            elif itype == "GroupSelection":
                item = GroupSelection(title=data.get("title", "Group"))

            if item:
                item.setPos(x, y)
                if "z_value" in data:
                    item.setZValue(data["z_value"])
                self.addItem(item)

    def handle_tablet_event(self, event, scene_pos: QPointF) -> bool:
        import time
        if self.active_tool not in ["pen", "highlighter"]:
            return False

        pressure = event.pressure() if hasattr(event, "pressure") else 1.0
        timestamp = event.timestamp() if hasattr(event, "timestamp") else time.time()

        event_type = event.type()
        if event_type == event.Type.TabletPress:
            self.deactivate_active_shape()
            self._stroke_start_pos = scene_pos
            self._hold_last_pos = scene_pos
            self._is_live_snapped = False
            self._snapped_shape_item = None

            self.stroke_processor.start_stroke(scene_pos, pressure=pressure, timestamp=timestamp)
            self._current_painter_path = QPainterPath()
            self._current_painter_path.moveTo(scene_pos)
            
            tool_name = self.active_tool
            color = self.highlighter_color if tool_name == "highlighter" else self.pen_color
            self._current_path_item = InkStroke(
                path=self._current_painter_path,
                tool_mode=tool_name,
                color=color,
                width=self.pen_width
            )
            self.addItem(self._current_path_item)
            self._hold_snap_timer.start(HOLD_DURATION_MS)
            return True

        elif event_type == event.Type.TabletMove and self._current_path_item:
            self.stroke_processor.add_point(scene_pos, pressure=pressure, timestamp=timestamp)
            
            # Check movement threshold for hold timer
            dist_moved = math.hypot(scene_pos.x() - self._hold_last_pos.x(), scene_pos.y() - self._hold_last_pos.y())
            if dist_moved > HOLD_MOVE_THRESHOLD_PX:
                if SHAPE_DEBUG:
                    print(f"[HoldSnapTimer] Tablet Move ({dist_moved:.2f}px > {HOLD_MOVE_THRESHOLD_PX}px) -> Resetting hold timer ({HOLD_DURATION_MS}ms)", flush=True)
                self._hold_last_pos = scene_pos
                self._hold_snap_timer.start(HOLD_DURATION_MS)
                
                # If user moved again after live snap, revert back to raw stroke
                if self._is_live_snapped:
                    if self._snapped_shape_item and self._snapped_shape_item.scene() == self:
                        self.deactivate_active_shape()
                        self.removeItem(self._snapped_shape_item)
                    self._snapped_shape_item = None
                    self._is_live_snapped = False
                    if self._current_path_item.scene() != self:
                        self.addItem(self._current_path_item)

            if not self._is_live_snapped:
                self._current_painter_path.lineTo(scene_pos)
                self._current_path_item.setPath(self._current_painter_path)
            return True

        elif event_type == event.Type.TabletRelease and self._current_path_item:
            self._hold_snap_timer.stop()
            if self._is_live_snapped and self._snapped_shape_item:
                self._current_path_item = None
                self._current_painter_path = None
                self._stroke_start_pos = None
                return True

            self.stroke_processor.add_point(scene_pos, pressure=pressure, timestamp=timestamp)
            tool_name = self.active_tool
            color = self.highlighter_color if tool_name == "highlighter" else self.pen_color
            
            # process_stroke on release always produces a handwriting item (no snapping).
            # Shape snapping only happens in _on_hold_snap_timeout.
            final_item = self.stroke_processor.process_stroke(
                color=color,
                width=self.pen_width,
                tool_mode=tool_name
            )
            if final_item:
                self.removeItem(self._current_path_item)
                self.addItem(final_item)

            self._current_path_item = None
            self._current_painter_path = None
            self._stroke_start_pos = None
            return True

        return False

    def mousePressEvent(self, event):
        pos = event.scenePos()
        clicked_items = self.items(pos)

        # Identify clicked shape or active shape controls
        shape_clicked = None
        is_active_control_clicked = False

        for item in clicked_items:
            if isinstance(item, SmartShapeItem):
                shape_clicked = item
                break

        for item in clicked_items:
            if item in [self._active_shape_item, self._active_handles, self._active_properties_panel]:
                is_active_control_clicked = True
                break
            if self._active_properties_panel and item == self._active_properties_panel.popup_proxy:
                is_active_control_clicked = True
                break
            if self._active_shape_item and item and item.parentItem() == self._active_shape_item:
                is_active_control_clicked = True
                break

        if SHAPE_DEBUG:
            print(f"[CanvasScene] mousePressEvent at ({pos.x():.1f}, {pos.y():.1f}): "
                  f"shape_clicked={type(shape_clicked).__name__ if shape_clicked else None}, "
                  f"is_active_control_clicked={is_active_control_clicked}, "
                  f"tool={self.active_tool}", flush=True)

        if is_active_control_clicked:
            # Clicked active shape body, handle, or properties toolbar/popup card.
            # Do NOT deactivate! Route event to item/widgets natively.
            super().mousePressEvent(event)
            return

        if shape_clicked:
            # Clicked an inactive shape item
            self.activate_shape(shape_clicked)
            super().mousePressEvent(event)
            return

        # Clicked blank canvas -> deactivate active shape controls
        self.deactivate_active_shape()

        if self.active_tool == "eraser" and event.button() == Qt.MouseButton.LeftButton:
            self._is_erasing = True
            self.erase_selected_items()
            self.erase_items_at(event.scenePos())
            event.accept()
        elif self.active_tool in ["pen", "highlighter"] and event.button() == Qt.MouseButton.LeftButton:
            self._stroke_start_pos = pos
            self._hold_last_pos = pos
            self._is_live_snapped = False
            self._snapped_shape_item = None

            self.stroke_processor.start_stroke(pos, pressure=1.0)
            
            self._current_painter_path = QPainterPath()
            self._current_painter_path.moveTo(pos)
            
            tool_name = self.active_tool
            color = self.highlighter_color if tool_name == "highlighter" else self.pen_color
            
            self._current_path_item = InkStroke(
                path=self._current_painter_path,
                tool_mode=tool_name,
                color=color,
                width=self.pen_width
            )
            self.addItem(self._current_path_item)
            if SHAPE_DEBUG:
                print(f"[HoldSnapTimer] Mouse Press -> Starting hold timer ({HOLD_DURATION_MS}ms)", flush=True)
            self._hold_snap_timer.start(HOLD_DURATION_MS)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.scenePos()

        if self._is_erasing and self.active_tool == "eraser":
            self.erase_items_at(pos)
            event.accept()
        elif self._current_path_item and self._current_painter_path:
            self.stroke_processor.add_point(pos, pressure=1.0)

            # Check hold distance
            dist_moved = math.hypot(pos.x() - self._hold_last_pos.x(), pos.y() - self._hold_last_pos.y())
            if dist_moved > HOLD_MOVE_THRESHOLD_PX:
                if SHAPE_DEBUG:
                    print(f"[HoldSnapTimer] Mouse Move ({dist_moved:.2f}px > {HOLD_MOVE_THRESHOLD_PX}px) -> Resetting hold timer ({HOLD_DURATION_MS}ms)", flush=True)
                self._hold_last_pos = pos
                self._hold_snap_timer.start(HOLD_DURATION_MS)

                # Revert live snap if user continues drawing
                if self._is_live_snapped:
                    if self._snapped_shape_item and self._snapped_shape_item.scene() == self:
                        self.deactivate_active_shape()
                        self.removeItem(self._snapped_shape_item)
                    self._snapped_shape_item = None
                    self._is_live_snapped = False
                    if self._current_path_item.scene() != self:
                        self.addItem(self._current_path_item)

            if not self._is_live_snapped:
                if self.active_tool == "highlighter" and self._stroke_start_pos:
                    snapped_pos = QPointF(pos.x(), self._stroke_start_pos.y())
                    new_path = QPainterPath()
                    new_path.moveTo(self._stroke_start_pos)
                    new_path.lineTo(snapped_pos)
                    self._current_path_item.setPath(new_path)
                else:
                    self._current_painter_path.lineTo(pos)
                    self._current_path_item.setPath(self._current_painter_path)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._hold_snap_timer.stop()

        if self._is_erasing:
            self._is_erasing = False
            event.accept()
        elif self._current_path_item:
            if self._is_live_snapped and self._snapped_shape_item:
                self._current_path_item = None
                self._current_painter_path = None
                self._stroke_start_pos = None
                event.accept()
                return

            pos = event.scenePos()
            self.stroke_processor.add_point(pos, pressure=1.0)
            
            tool_name = self.active_tool
            color = self.highlighter_color if tool_name == "highlighter" else self.pen_color
            
            # process_stroke on release always produces a handwriting item (no snapping).
            # Shape snapping only happens in _on_hold_snap_timeout.
            final_item = self.stroke_processor.process_stroke(
                color=color,
                width=self.pen_width,
                tool_mode=tool_name
            )
            
            if final_item:
                self.removeItem(self._current_path_item)
                self.addItem(final_item)
                if self.active_tool == "pen":
                    self._recent_ink_strokes.append(final_item)

            self._current_path_item = None
            self._current_painter_path = None
            self._stroke_start_pos = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _on_auto_convert_ink(self):
        if not self._recent_ink_strokes:
            return

        from ..backend.ocr.handwriting_ocr import recognize_handwriting

        valid_strokes = [s for s in self._recent_ink_strokes if s.scene() == self]
        if not valid_strokes:
            self._recent_ink_strokes.clear()
            return

        min_x = min(s.sceneBoundingRect().x() for s in valid_strokes)
        min_y = min(s.sceneBoundingRect().y() for s in valid_strokes)
        pos = QPointF(min_x, min_y)

        text = recognize_handwriting(stroke_count=len(valid_strokes))

        for s in valid_strokes:
            self.removeItem(s)

        self._recent_ink_strokes.clear()

        if text:
            self.ink_written_detected.emit(text, pos)
