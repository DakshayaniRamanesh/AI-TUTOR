"""
Freeform Canvas Scene (Infinite SceneRect, Dotted & Ruled Paper Backgrounds, Freehand Drawing, Shape Snapping & Serialization)
"""

import math
import time
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPathItem, QGraphicsProxyWidget
from PyQt6.QtGui import QPen, QColor, QBrush, QPainterPath, QPainter
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, QThread, pyqtSignal

from .theme_manager import ThemeManager
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
from .penecho_integration import (
    PenechoDrawItem, PenechoAnimationItem, PenechoMixedTextItem,
    PenechoSummonItem, PenechoLassoOverlay, PenechoDraftLayerItem, point_in_polygon
)

class CanvasScene(QGraphicsScene):
    ink_written_detected = pyqtSignal(str, QPointF)
    auto_ai_requested = pyqtSignal(str, QPointF)
    # Emitted whenever the scene content changes (stroke, erase, shape add/remove).
    # MainWindow connects this to the debounced autosave timer.
    scene_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Infinite canvas bounds
        self.setSceneRect(QRectF(-50000, -50000, 100000, 100000))
        
        # Background mode: "dotted", "ruled", or "blank"
        self.background_mode = "blank"
        
        # Active tool state: "select", "pen", "highlighter", "eraser"
        self.active_tool = "select"
        self.pen_color = "#1c1c1e"
        self.pen_width = 3.0
        self.highlighter_color = "#ffe066"
        self.active_shape_type = "rectangle"
        self.eraser_size = 2 # 1=small, 2=medium, 3=large
        
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

        tm = ThemeManager.instance()
        if tm.is_dark():
            self.pen_color = "#ffffff"
        tm.theme_changed.connect(self._on_theme_changed)
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

        # Freehand Lasso Tool State
        self._lasso_path_item = None
        self._lasso_points = []

        # PenEcho Auto-AI Engine (Post-stroke attention detection)
        # Disabled by default — only the explicit "Ask AI" button (or the user opting
        # into Auto-AI mode via the Magic Orb menu) should trigger a solve request.
        self.auto_ai_enabled = False
        self.auto_ai_delay_sec = 2.0
        self._auto_ai_timer = QTimer(self)
        self._auto_ai_timer.setSingleShot(True)
        self._auto_ai_timer.timeout.connect(self._on_auto_ai_timeout)
        # Keep references to background OCR workers to prevent premature GC
        self._ocr_workers: list = []

    def _on_theme_changed(self, theme_name: str):
        is_dark = theme_name == "dark"
        
        # 1. Update default pen color to maintain high contrast readability
        if is_dark and self.pen_color in ["#1c1c1e", "#000000", "#0b2545", "#0f172a", "#111111"]:
            self.pen_color = "#ffffff"
        elif not is_dark and self.pen_color in ["#ffffff", "#f4f4f5", "#f8f9fa", "#e2e8f0"]:
            self.pen_color = "#1c1c1e"

        # 2. Automatically adjust existing canvas stroke & item colors for maximum legibility!
        for item in self.items():
            if isinstance(item, InkStroke):
                col = item.pen().color().name().lower()
                if is_dark and col in ["#1c1c1e", "#000000", "#0b2545", "#0f172a", "#111111"]:
                    new_pen = QPen(QColor("#ffffff"), item.stroke_width)
                    new_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    new_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    item.setPen(new_pen)
                    item.stroke_color = QColor("#ffffff")
                elif not is_dark and col in ["#ffffff", "#f4f4f5", "#f8f9fa", "#e2e8f0"]:
                    new_pen = QPen(QColor("#1c1c1e"), item.stroke_width)
                    new_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    new_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    item.setPen(new_pen)
                    item.stroke_color = QColor("#1c1c1e")
            elif isinstance(item, SmartShapeItem):
                col = item.pen.color().name().lower()
                if is_dark and col in ["#1c1c1e", "#000000", "#0b2545", "#0f172a", "#111111"]:
                    item.set_pen_color("#ffffff")
                elif not is_dark and col in ["#ffffff", "#f4f4f5", "#f8f9fa", "#e2e8f0"]:
                    item.set_pen_color("#1c1c1e")
                    
        self.update()

    def set_highlighter_color(self, color_hex: str):
        self.highlighter_color = color_hex
        self.active_tool = "highlighter"

    def set_pen_color(self, color_hex: str):
        self.pen_color = color_hex
        self.active_tool = "pen"

    def set_background_mode(self, mode: str):
        if mode in ["dotted", "ruled", "blank", "math_ruled"]:
            self.background_mode = mode
            self.update()

    def drawBackground(self, painter: QPainter, rect: QRectF):
        c = ThemeManager.instance().get_colors()

        if self.background_mode == "blank":
            painter.fillRect(rect, QColor(c["canvas_bg"]))
            return
        painter.fillRect(rect, QColor(c["canvas_bg"]))
              
        grid_size = 28
        left = int(rect.left()) - (int(rect.left()) % grid_size)
        top = int(rect.top()) - (int(rect.top()) % grid_size)
        right = int(rect.right())
        bottom = int(rect.bottom())

        grid_pen_color = QColor(c["canvas_grid"])

        if self.background_mode == "dotted":
            painter.setPen(QPen(grid_pen_color, 1.5))
            for x in range(left, right, grid_size):
                for y in range(top, bottom, grid_size):
                    painter.drawPoint(x, y)
                    
        elif self.background_mode == "ruled":
            painter.setPen(QPen(grid_pen_color, 1))
            for y in range(top, bottom, grid_size):
                painter.drawLine(left, y, right, y)

        elif self.background_mode == "math_ruled":
            painter.setPen(QPen(grid_pen_color, 1))
            for y in range(top, bottom, grid_size):
                painter.drawLine(left, y, right, y)
            for x in range(left, right, grid_size):
                painter.drawLine(x, top, x, bottom)

    def erase_items_at(self, pos: QPointF):
        radius = self.eraser_size * 5  # 1=5px, 2=10px, 3=15px
        path = QPainterPath()
        path.addEllipse(pos, radius, radius)
        
        items = self.items(path, Qt.ItemSelectionMode.IntersectsItemShape)
        erased_any = False
        for item in items:
            if item.scene() == self:
                if item == self._active_handles or item == self._active_properties_panel:
                    continue
                if item == self._active_shape_item:
                    self.deactivate_active_shape()
                self.removeItem(item)
                erased_any = True
        if erased_any:
            self.scene_changed.emit()

    def erase_selected_items(self):
        items_to_remove = list(self.selectedItems())
        for item in items_to_remove:
            if item == self._active_shape_item:
                self.deactivate_active_shape()
            self.removeItem(item)
        if items_to_remove:
            self.scene_changed.emit()

    def clear_all(self):
        self.deactivate_active_shape()
        self.clear()

    def activate_shape(self, shape_item):
        """Activates an item, attaching interactive resize handles and properties panel."""
        if not shape_item or shape_item.scene() != self:
            return

        if self._active_shape_item == shape_item:
            return

        self.deactivate_active_shape()

        self._active_shape_item = shape_item
        
        if isinstance(shape_item, SmartShapeItem):
            self._active_handles = ShapeResizeHandles(shape_item)
            self._active_properties_panel = ShapePropertiesPanel(shape_item)
            self._active_handles.signals.geometry_changed.connect(self._active_properties_panel.refresh)
        else:
            from .bounding_box_handles import BoundingBoxHandles
            self._active_handles = BoundingBoxHandles(shape_item)
            self._active_properties_panel = None

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
            self.scene_changed.emit()
        else:
            if SHAPE_DEBUG:
                print(f"[HoldSnapTimer] Classified as handwriting. Kept raw stroke.", flush=True)

    def to_dict_list(self) -> list[dict]:
        items_data = [{"type": "_canvas_meta", "background_mode": self.background_mode}]
        for item in self.items():
            if hasattr(item, "to_dict") and item not in [self._active_handles, self._active_properties_panel] and not isinstance(item, (PenechoLassoOverlay, PenechoDraftLayerItem)):
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
            if itype == "_canvas_meta":
                bg_mode = data.get("background_mode", "ruled")
                self.set_background_mode(bg_mode)
                continue

            x = data.get("x", 0)
            y = data.get("y", 0)

            item = self.create_item_from_dict(data)
            if item:
                item.setPos(x, y)
                if "z_value" in data:
                    item.setZValue(data["z_value"])
                if "item_id" in data and data["item_id"]:
                    item.item_id = data["item_id"]
                self.addItem(item)

    def create_item_from_dict(self, data: dict):
        """Deserializes a single item dict into a QGraphicsItem subclass.
        Returns None for unknown types and logs a warning — never silently drops data.
        """
        itype = data.get("type")
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

        elif itype == "InkStroke":
            # NOTE: to_dict() saves key "elements" — NOT "path_elements".
            path = QPainterPath()
            elements = data.get("elements") or data.get("path_elements", [])
            i = 0
            while i < len(elements):
                el = elements[i]
                el_type = el.get("type", -1)
                if el_type == 0:   # MoveTo
                    path.moveTo(el["x"], el["y"])
                    i += 1
                elif el_type == 1: # LineTo
                    path.lineTo(el["x"], el["y"])
                    i += 1
                elif el_type == 2: # CurveTo (control point 1 — next two are ctrl2 + end)
                    if i + 2 < len(elements):
                        el2, el3 = elements[i + 1], elements[i + 2]
                        path.cubicTo(el["x"], el["y"], el2["x"], el2["y"], el3["x"], el3["y"])
                        i += 3
                    else:
                        i += 1  # Incomplete curve — skip
                else:
                    i += 1  # CurveToData or unknown — already consumed by type 2
            item = InkStroke(
                path=path,
                tool_mode=data.get("tool_mode", "pen"),
                color=data.get("color", "#1c1c1e"),
                width=data.get("width", 3.0)
            )

        elif itype == "TextBoxItem":
            from .items.text_box_item import TextBoxItem
            item = TextBoxItem(text=data.get("text", ""))

        elif itype == "ImageItem":
            import base64
            from PyQt6.QtGui import QImage, QPixmap
            # to_dict() saves key "image_b64" — support both for backward compat.
            b64_data = data.get("image_b64") or data.get("image_base64", "")
            if b64_data:
                try:
                    img_data = base64.b64decode(b64_data)
                    img = QImage.fromData(img_data)
                    if not img.isNull():
                        item = ImageItem(QPixmap.fromImage(img))
                        saved_scale = data.get("scale")
                        if saved_scale is not None:
                            item.setScale(saved_scale)
                except Exception as err:
                    print(f"[CanvasScene] Warning: Could not decode ImageItem: {err}")

        elif itype == "StickyNote":
            item = StickyNote(text=data.get("text", ""), color_key=data.get("color_key", "yellow"))
            # Restore minimized state
            if data.get("is_minimized") and hasattr(item, 'widget'):
                item.widget._toggle_minimize()

        elif itype == "HandwritingNote":
            item = HandwritingNote(text=data.get("text", ""))
            # Restore minimized and font state
            if hasattr(item, 'widget'):
                if data.get("is_minimized"):
                    item.widget._toggle_minimize()
                if "use_handwriting_font" in data:
                    item.widget.use_handwriting_font = data["use_handwriting_font"]

        elif itype == "TableItem":
            item = TableItem(headers=data.get("headers"), rows=data.get("rows"))

        elif itype == "CardItem":
            # to_dict() uses "subtitle" and "source_url" — NOT "content".
            item = CardItem(
                title=data.get("title", "Card"),
                subtitle=data.get("subtitle", data.get("content", "")),
                source_url=data.get("source_url", "")
            )

        elif itype == "GraphCard":
            item = GraphCard(title=data.get("title", "Plot"), image_path=data.get("image_path", ""))

        elif itype == "VideoFloatItem":
            item = VideoFloatItem(
                job_id=data.get("job_id", ""),
                title=data.get("title", "Video"),
                video_url_or_path=data.get("video_path", "")
            )
            # Restore minimized state
            if data.get("is_minimized") and hasattr(item, 'player_widget'):
                item.player_widget._toggle_minimize()

        elif itype == "AnswerBubble":
            item = AnswerBubble(
                question=data.get("question", ""),
                full_text=data.get("full_text", ""),
                hints=data.get("hints", ""),
                is_direct_math=data.get("is_direct_math", False)
            )

        elif itype == "GroupSelection":
            item = GroupSelection(title=data.get("title", "Group"))
            # Restore collapsed state
            if data.get("is_collapsed") and hasattr(item, 'group_widget'):
                item.group_widget._toggle_collapse()

        elif itype == "MapPinCard":
            from .items.map_pin_card import MapPinCard
            item = MapPinCard(
                title=data.get("title", ""),
                address=data.get("address", "")
            )

        elif itype == "PenechoDrawItem":
            item = PenechoDrawItem.from_dict(data)

        elif itype == "PenechoAnimationItem":
            item = PenechoAnimationItem.from_dict(data)

        elif itype == "PenechoMixedTextItem":
            item = PenechoMixedTextItem.from_dict(data)

        elif itype == "PenechoSummonItem":
            item = PenechoSummonItem.from_dict(data)

        else:
            print(f"[CanvasScene] WARNING: Unrecognized item type '{itype}' — skipping. "
                  f"Add a load branch in create_item_from_dict() to prevent silent data loss.")

        return item

    def handle_tablet_event(self, event, scene_pos: QPointF) -> bool:
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
        elif self.active_tool == "lasso" and event.button() == Qt.MouseButton.LeftButton:
            self._lasso_points = [(pos.x(), pos.y())]
            path = QPainterPath()
            path.moveTo(pos)
            self._lasso_path_item = QGraphicsPathItem()
            lasso_pen = QPen(QColor("#3b82f6"), 1.5, Qt.PenStyle.DashLine)
            self._lasso_path_item.setPen(lasso_pen)
            self._lasso_path_item.setBrush(QBrush(QColor(59, 130, 246, 25)))
            self._lasso_path_item.setPath(path)
            self._lasso_path_item.setZValue(9998)
            self.addItem(self._lasso_path_item)
            event.accept()
        elif self.active_tool == "shapes" and event.button() == Qt.MouseButton.LeftButton:
            self._shape_start_pos = pos
            shape_type = self.active_shape_type
            if shape_type in ["rectangle", "circle", "ellipse", "square"]:
                fit_data = {"bbox": (pos.x(), pos.y(), 0, 0)}
            elif shape_type in ["line", "arrow"]:
                fit_data = {"p1": (pos.x(), pos.y()), "p2": (pos.x(), pos.y())}
            else:
                fit_data = {}
                
            pen = QPen(QColor(self.pen_color), self.pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            self._current_drawing_shape = SmartShapeItem(shape_type=shape_type, fit_data=fit_data, pen=pen)
            self.addItem(self._current_drawing_shape)
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
        elif self.active_tool == "lasso" and self._lasso_path_item and self._lasso_points:
            self._lasso_points.append((pos.x(), pos.y()))
            path = QPainterPath()
            path.moveTo(QPointF(self._lasso_points[0][0], self._lasso_points[0][1]))
            for pt in self._lasso_points[1:]:
                path.lineTo(QPointF(pt[0], pt[1]))
            self._lasso_path_item.setPath(path)
            event.accept()
        elif self.active_tool == "shapes" and hasattr(self, '_shape_start_pos') and self._shape_start_pos:
            st = self.active_shape_type
            if st in ["rectangle", "circle", "ellipse", "square"]:
                x = min(pos.x(), self._shape_start_pos.x())
                y = min(pos.y(), self._shape_start_pos.y())
                w = abs(pos.x() - self._shape_start_pos.x())
                h = abs(pos.y() - self._shape_start_pos.y())
                if st in ["circle", "square"]:
                    side = max(w, h)
                    w, h = side, side
                self._current_drawing_shape.fit_data["bbox"] = (x, y, w, h)
            elif st in ["line", "arrow"]:
                self._current_drawing_shape.fit_data["p2"] = (pos.x(), pos.y())
                
            self._current_drawing_shape._init_geometry_from_fit()
            self._current_drawing_shape.update_path()
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
        elif self.active_tool == "lasso" and self._lasso_path_item:
            if self._lasso_path_item.scene() == self:
                self.removeItem(self._lasso_path_item)
            self._lasso_path_item = None
            
            if len(self._lasso_points) >= 3:
                # Find all items enclosed by the lasso polygon
                selected = []
                for item in self.items():
                    if item.scene() == self and hasattr(item, "to_dict") and not isinstance(item, (PenechoLassoOverlay, ShapeResizeHandles)):
                        center = item.sceneBoundingRect().center()
                        if point_in_polygon(center.x(), center.y(), self._lasso_points):
                            selected.append(item)
                if selected:
                    # Mark items as Qt-selected so selectedItems() works for video gen, etc.
                    self.clearSelection()
                    for item in selected:
                        item.setSelected(True)
                    # Store on scene for easy retrieval by lasso-video flow
                    self._last_lasso_items = selected
                    overlay = PenechoLassoOverlay(self._lasso_points, selected)
                    self.addItem(overlay)
                else:
                    self._last_lasso_items = []
            self._lasso_points = []
            event.accept()
        elif self.active_tool == "shapes" and hasattr(self, '_shape_start_pos') and self._shape_start_pos:
            self.activate_shape(self._current_drawing_shape)
            self._shape_start_pos = None
            self._current_drawing_shape = None
            self.scene_changed.emit()
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
                    if self.auto_ai_enabled:
                        self._auto_ai_timer.start(int(self.auto_ai_delay_sec * 1000))
                self.scene_changed.emit()
            elif self._current_path_item:  # Highlighter or very short stroke — keep it
                self.scene_changed.emit()

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

    def _render_strokes_base64(self, strokes: list) -> str:
        import base64
        from PyQt6.QtGui import QImage, QPainter, QColor
        from PyQt6.QtWidgets import QStyleOptionGraphicsItem
        from PyQt6.QtCore import QBuffer, QIODevice

        if not strokes:
            return ""

        rect = strokes[0].sceneBoundingRect()
        for s in strokes[1:]:
            rect = rect.united(s.sceneBoundingRect())

        rect = rect.adjusted(-15, -15, 15, 15)
        w = max(40, int(rect.width()))
        h = max(40, int(rect.height()))

        img = QImage(w, h, QImage.Format.Format_ARGB32)
        img.fill(QColor("#ffffff"))

        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.translate(-rect.left(), -rect.top())

        for s in strokes:
            s.paint(painter, QStyleOptionGraphicsItem(), None)

        painter.end()

        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buffer, "PNG")
        return base64.b64encode(buffer.data().data()).decode("utf-8")

    def _on_auto_ai_timeout(self):
        """Fires in PenEcho Auto-AI mode after post-stroke delay.

        The Gemini OCR call (recognize_handwriting) is a blocking network request
        and MUST NOT run on the main thread — doing so freezes the canvas.
        This method spawns a background QThread to do the OCR work and emits
        auto_ai_requested only from the thread-finished callback on the main thread.
        """
        valid_strokes = [s for s in self._recent_ink_strokes if s.scene() == self]
        if not valid_strokes:
            return

        min_y = min(s.sceneBoundingRect().y() for s in valid_strokes)
        max_x = max(s.sceneBoundingRect().right() for s in valid_strokes)
        target_pos = QPointF(max_x + 35, min_y)
        b64_img = self._render_strokes_base64(valid_strokes)
        stroke_count = len(valid_strokes)

        class _OCRWorker(QThread):
            ocr_done = pyqtSignal(str)

            def __init__(self, b64, count, parent=None):
                super().__init__(parent)
                self._b64 = b64
                self._count = count

            def run(self):
                try:
                    from ..backend.ocr.handwriting_ocr import recognize_handwriting
                    text = recognize_handwriting(b64_image=self._b64, stroke_count=self._count)
                    if text:
                        self.ocr_done.emit(text)
                except Exception as exc:
                    print(f"[AutoAI OCR] Error: {exc}")

        worker = _OCRWorker(b64_img, stroke_count, parent=self)
        self._ocr_workers.append(worker)

        def _on_done(text):
            self.auto_ai_requested.emit(text, target_pos)
            if worker in self._ocr_workers:
                self._ocr_workers.remove(worker)

        worker.ocr_done.connect(_on_done)
        worker.finished.connect(lambda: self._ocr_workers.remove(worker) if worker in self._ocr_workers else None)
        worker.start()

    def trigger_ai_on_dirty_ink(self, prompt: str = ""):
        """Explicitly triggers PenEcho AI on the latest ink strokes or selection.

        This is the ONLY intended entry point for the explicit \"Ask AI\" button.
        If a prompt is already known it is used directly; otherwise the Gemini
        Vision OCR call runs in a background QThread so the canvas never freezes.
        """
        valid_strokes = [s for s in self._recent_ink_strokes if s.scene() == self]
        if valid_strokes:
            min_y = min(s.sceneBoundingRect().y() for s in valid_strokes)
            max_x = max(s.sceneBoundingRect().right() for s in valid_strokes)
            target_pos = QPointF(max_x + 35, min_y)
        else:
            target_pos = QPointF(200, 200)

        # If a prompt is already provided, fire immediately without OCR
        if prompt:
            self.auto_ai_requested.emit(prompt, target_pos)
            return

        if not valid_strokes:
            return

        b64_img = self._render_strokes_base64(valid_strokes)
        stroke_count = len(valid_strokes)

        class _OCRWorker(QThread):
            ocr_done = pyqtSignal(str)

            def __init__(self, b64, count, parent=None):
                super().__init__(parent)
                self._b64 = b64
                self._count = count

            def run(self):
                try:
                    from ..backend.ocr.handwriting_ocr import recognize_handwriting
                    text = recognize_handwriting(b64_image=self._b64, stroke_count=self._count)
                    if text:
                        self.ocr_done.emit(text)
                except Exception as exc:
                    print(f"[TriggerAI OCR] Error: {exc}")

        worker = _OCRWorker(b64_img, stroke_count, parent=self)
        self._ocr_workers.append(worker)

        def _on_done(text):
            self.auto_ai_requested.emit(text, target_pos)
            if worker in self._ocr_workers:
                self._ocr_workers.remove(worker)

        worker.ocr_done.connect(_on_done)
        worker.finished.connect(lambda: self._ocr_workers.remove(worker) if worker in self._ocr_workers else None)
        worker.start()
