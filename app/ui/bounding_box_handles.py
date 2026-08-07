import math
from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtGui import QPen, QColor, QPainter, QPainterPath
from PyQt6.QtCore import Qt, QRectF, QPointF

class BoundingBoxHandles(QGraphicsItem):
    """Generic bounding box overlay with resize handles for scaling items."""
    HANDLE_SIZE = 10.0

    def __init__(self, target_item, parent=None):
        super().__init__(parent)
        self.target_item = target_item
        self.setParentItem(target_item)
        self.setZValue(100)
        self._active_handle_index = None
        self._drag_start_pos = None
        self._drag_start_scale = 1.0

    def boundingRect(self) -> QRectF:
        if not self.target_item: return QRectF()
        rect = self.target_item.boundingRect()
        m = self.HANDLE_SIZE + 4.0
        return rect.adjusted(-m, -m, m, m)
        
    def shape(self) -> QPainterPath:
        # Only return the handles and the border so we can click through to the item itself
        path = QPainterPath()
        if not self.target_item: return path
        rect = self.target_item.boundingRect()
        
        # Border stroke region
        border_path = QPainterPath()
        border_path.addRect(rect)
        inner_path = QPainterPath()
        inner_path.addRect(rect.adjusted(2, 2, -2, -2))
        path.addPath(border_path.subtracted(inner_path))
        
        # Handles region
        hs = self.HANDLE_SIZE
        corners = [
            rect.topLeft(), rect.topRight(),
            rect.bottomRight(), rect.bottomLeft()
        ]
        for p in corners:
            path.addRect(QRectF(p.x() - hs, p.y() - hs, hs * 2, hs * 2))
            
        return path

    def paint(self, painter: QPainter, option, widget=None):
        if not self.target_item: return
        rect = self.target_item.boundingRect()
        
        # Draw bounding box
        painter.setPen(QPen(QColor("#7c3aed"), 1.5, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)
        
        # Draw handles at 4 corners
        painter.setPen(QPen(QColor("#7c3aed"), 1.5))
        painter.setBrush(QColor("#ffffff"))
        
        corners = [
            rect.topLeft(), rect.topRight(),
            rect.bottomRight(), rect.bottomLeft()
        ]
        hs = self.HANDLE_SIZE
        for p in corners:
            painter.drawRect(QRectF(p.x() - hs/2, p.y() - hs/2, hs, hs))

    def _get_handle_at(self, pos: QPointF):
        if not self.target_item: return None
        rect = self.target_item.boundingRect()
        corners = [
            rect.topLeft(), rect.topRight(),
            rect.bottomRight(), rect.bottomLeft()
        ]
        hs = self.HANDLE_SIZE
        for i, p in enumerate(corners):
            hr = QRectF(p.x() - hs, p.y() - hs, hs*2, hs*2)
            if hr.contains(pos):
                return i
        return None

    def mousePressEvent(self, event):
        idx = self._get_handle_at(event.pos())
        if idx is not None:
            self._active_handle_index = idx
            self._drag_start_pos = event.scenePos()
            self._drag_start_scale = self.target_item.scale()
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        if self._active_handle_index is not None:
            # Simple uniform scaling based on drag distance from center
            center = self.target_item.mapToScene(self.target_item.boundingRect().center())
            start_dist = math.hypot(self._drag_start_pos.x() - center.x(), self._drag_start_pos.y() - center.y())
            curr_pos = event.scenePos()
            curr_dist = math.hypot(curr_pos.x() - center.x(), curr_pos.y() - center.y())
            
            if start_dist > 0:
                scale_factor = curr_dist / start_dist
                new_scale = max(0.1, self._drag_start_scale * scale_factor)
                
                # Transform origin to center so scaling happens from center
                # This requires adjusting pos, but QGraphicsItem setScale scales from transformOriginPoint
                self.target_item.setTransformOriginPoint(self.target_item.boundingRect().center())
                self.target_item.setScale(new_scale)
                
                # We need to tell the scene to redraw this item's bounds
                self.prepareGeometryChange()
                
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event):
        if self._active_handle_index is not None:
            self._active_handle_index = None
            event.accept()
        else:
            event.ignore()
