"""
Interactive AI Draft Layer Item for AI-TUTOR.
Ported from PenEcho's Unconfirmed Draft Layer architecture.

Provides:
- PenechoDraftLayerItem: Wraps AI-generated content (solutions, LaTeX cards, animation scenes,
  vector drawings) inside an editable unconfirmed draft overlay with Accept (✓), Discard (✕),
  Move, and Resize controls.
- Committing (Accept) permanently bakes content into CanvasScene.
- Discarding cleanly removes the draft without modifying existing canvas content.
"""

import math
from typing import List, Optional
from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QPainterPath, QFont
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QObject


class PenechoDraftLayerItem(QGraphicsItem):
    """
    PenEcho-style Unconfirmed Draft Layer.
    Wraps candidate AI responses on the canvas with interactive Accept/Discard affordances.
    """

    def __init__(self, inner_item: QGraphicsItem, title: str = "AI Draft", parent=None):
        super().__init__(parent)
        self.setZValue(5000) # Float above standard canvas content
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

        self.inner_item = inner_item
        self.inner_item.setParentItem(self)
        self.inner_item.setPos(0, 0)
        self._title = title

        self._pad = 20.0
        self._header_height = 28.0
        self._active_action: Optional[str] = None
        self._drag_start_pos: Optional[QPointF] = None
        self._initial_scale = 1.0

    def boundingRect(self) -> QRectF:
        inner_rect = self.inner_item.boundingRect()
        w = inner_rect.width() + self._pad * 2
        h = inner_rect.height() + self._pad * 2 + self._header_height
        return QRectF(-self._pad, -self._pad - self._header_height, w, h)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.boundingRect()
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

        # 1. Subtle Draft Backdrop & Animated Dashed Border
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)
        painter.setBrush(QBrush(QColor(59, 130, 246, 15)))
        painter.setPen(QPen(QColor("#3b82f6"), 1.8, Qt.PenStyle.DashLine))
        painter.drawPath(path)

        # 2. Header Tag Badge
        badge_rect = QRectF(x + 12, y + 6, 95, 20)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#2563eb")))
        painter.drawRoundedRect(badge_rect, 6, 6)

        painter.setPen(QPen(QColor("#ffffff")))
        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, f"✨ {self._title}")

        # 3. Action Buttons
        # Green Accept Button (Top Right)
        btn_acc_x = x + w - 24
        btn_acc_y = y + 16
        painter.setBrush(QBrush(QColor("#10b981")))
        painter.setPen(QPen(QColor("#ffffff"), 1.5))
        painter.drawEllipse(QPointF(btn_acc_x, btn_acc_y), 11, 11)
        painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        painter.drawText(QRectF(btn_acc_x - 11, btn_acc_y - 11, 22, 22), Qt.AlignmentFlag.AlignCenter, "✓")

        # Red Discard Button (Adjacent to Accept)
        btn_disc_x = btn_acc_x - 30
        btn_disc_y = btn_acc_y
        painter.setBrush(QBrush(QColor("#ef4444")))
        painter.setPen(QPen(QColor("#ffffff"), 1.5))
        painter.drawEllipse(QPointF(btn_disc_x, btn_disc_y), 11, 11)
        painter.drawText(QRectF(btn_disc_x - 11, btn_disc_y - 11, 22, 22), Qt.AlignmentFlag.AlignCenter, "✕")

        # Resize Handle (Bottom Right corner)
        res_x = x + w
        res_y = y + h
        painter.setBrush(QBrush(QColor("#3b82f6")))
        painter.setPen(QPen(QColor("#ffffff"), 1.0))
        painter.drawEllipse(QPointF(res_x - 4, res_y - 4), 6, 6)

        painter.restore()

    def mousePressEvent(self, event):
        pos = event.pos()
        rect = self.boundingRect()
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

        btn_acc_x = x + w - 24
        btn_acc_y = y + 16
        btn_disc_x = btn_acc_x - 30
        btn_disc_y = btn_acc_y

        if math.hypot(pos.x() - btn_acc_x, pos.y() - btn_acc_y) <= 14:
            self.accept_draft()
            event.accept()
            return

        if math.hypot(pos.x() - btn_disc_x, pos.y() - btn_disc_y) <= 14:
            self.discard_draft()
            event.accept()
            return

        res_x = x + w
        res_y = y + h
        if math.hypot(pos.x() - res_x, pos.y() - res_y) <= 14:
            self._active_action = "resize"
            self._drag_start_pos = pos
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._active_action == "resize" and self._drag_start_pos:
            delta = event.pos() - self._drag_start_pos
            orig_w = self.inner_item.boundingRect().width()
            if orig_w > 0:
                scale_change = 1.0 + (delta.x() / orig_w)
                new_scale = max(0.4, min(3.0, self.scale() * scale_change))
                self.setScale(new_scale)
                self._drag_start_pos = event.pos()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._active_action = None
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept_draft()
            event.accept()
            return
        elif event.key() == Qt.Key.Key_Escape:
            self.discard_draft()
            event.accept()
            return
        super().keyPressEvent(event)

    def accept_draft(self):
        """
        Confirms the draft: detaches the inner item from this wrapper,
        adds it permanently to the scene at current global position, and removes draft overlay.
        """
        scene = self.scene()
        if not scene:
            return
        
        final_scene_pos = self.scenePos()
        final_scale = self.scale()

        # Detach inner item
        self.inner_item.setParentItem(None)
        self.inner_item.setPos(final_scene_pos)
        self.inner_item.setScale(final_scale)

        scene.removeItem(self)
        if self.inner_item.scene() is None:
            scene.addItem(self.inner_item)
        if hasattr(scene, "scene_changed"):
            scene.scene_changed.emit()

    def discard_draft(self):
        """
        Rejects and deletes the draft candidate without affecting existing canvas content.
        """
        scene = self.scene()
        if scene:
            scene.removeItem(self)
            if hasattr(scene, "scene_changed"):
                scene.scene_changed.emit()
