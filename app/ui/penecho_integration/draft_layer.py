"""
Interactive AI Draft Layer Item for AI-TUTOR.
Ported from PenEcho's Unconfirmed Draft Layer architecture.

Provides:
- PenechoDraftLayerItem: Wraps AI-generated content (solutions, LaTeX cards, animation scenes,
  vector drawings) inside an editable unconfirmed draft overlay with Accept (✓), Discard (✕),
  Move, and Resize controls.
- Committing (Accept) permanently bakes content into CanvasScene with NO residual AI styling.
- Discarding cleanly removes the draft without modifying existing canvas content.

Containment guarantee
---------------------
While in the pending (not-yet-accepted) state, the inner item and ALL of its descendants
have ItemIsMovable and ItemIsSelectable stripped away.  The wrapper itself is the only
movable unit — dragging it moves the whole group as one locked piece.  There is no way
to drag sub-items out of the container independently while it is pending.

On Accept: flags are restored on the inner item tree before it is reparented to the scene,
           so accepted content immediately becomes freely editable canvas content.
On Discard: removeItem(self) cascades to all parented children — nothing can survive.

Visual behaviour
----------------
Default (no hover):  Plain — no background fill, no border, no label, no buttons.
                     The inner content blends naturally with other canvas items.
On hover:            A subtle, rounded hairline outline appears around the bounding box.
                     The ✓ (accept) and ✕ (discard) circles reveal themselves.
                     A small resize handle appears at the bottom-right corner.
Mouse leave:         All hover decorations vanish; back to plain appearance.
"""

import math
from typing import Optional
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsItemGroup, QStyleOptionGraphicsItem, QWidget
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QPainterPath, QFont
from PyQt6.QtCore import Qt, QRectF, QPointF


# Flags that must be stripped while content is pending
_LOCK_FLAGS = (
    QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
    QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
)
# Full interactive flag set to restore on accept
_FREE_FLAGS = (
    QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
    QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
    QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
)


def _collect_descendants(item: QGraphicsItem) -> list:
    """Recursively collect item and all of its QGraphicsItem children/grandchildren."""
    result = [item]
    for child in item.childItems():
        result.extend(_collect_descendants(child))
    return result


def _lock_item_tree(item: QGraphicsItem) -> None:
    """Remove movable/selectable flags from item and all its descendants."""
    for node in _collect_descendants(item):
        node.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        node.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)


def _unlock_item_tree(item: QGraphicsItem) -> None:
    """Restore movable/selectable/geometry flags on item and all its descendants."""
    for node in _collect_descendants(item):
        node.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        node.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        node.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)


class PenechoDraftLayerItem(QGraphicsItem):
    """
    PenEcho-style Unconfirmed Draft Layer.

    Wraps candidate AI responses on the canvas with hover-only Accept/Discard affordances.
    Default appearance is identical to plain canvas content (no coloured box, no labels).
    All sub-items are locked (non-movable, non-selectable) until accepted or discarded.
    """

    # ── Geometry constants ────────────────────────────────────────────────
    _PAD          = 20.0   # padding around inner_item
    _HEADER_H     = 28.0   # reserved above inner_item for hover buttons
    _BTN_R        = 11.0   # button circle radius
    _BTN_HIT_R    = 14.0   # hit-test radius (slightly larger for usability)
    _RESIZE_R     =  6.0   # resize handle radius
    _RESIZE_HIT_R = 12.0   # resize hit-test radius

    # ── Hover colours ─────────────────────────────────────────────────────
    _HOVER_BORDER = QColor(120, 120, 130, 110)  # understated grey outline
    _ACCEPT_CLR   = QColor("#10b981")
    _DISCARD_CLR  = QColor("#ef4444")
    _RESIZE_CLR   = QColor("#94a3b8")
    _BTN_TEXT_CLR = QColor("#ffffff")

    def __init__(self, inner_item: QGraphicsItem, title: str = "AI Draft", parent=None):
        super().__init__(parent)
        self.setZValue(5000)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

        self.inner_item = inner_item
        self.inner_item.setParentItem(self)   # establishes the parent-child link
        self.inner_item.setPos(0, 0)
        self._title = title

        # Lock all descendants so they cannot be dragged out of the container
        # independently while in the pending state.
        _lock_item_tree(self.inner_item)

        self._hovered: bool = False
        self._active_action: Optional[str] = None
        self._drag_start_pos: Optional[QPointF] = None

    # ── Geometry ──────────────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        inner_rect = self.inner_item.boundingRect()
        w = inner_rect.width() + self._PAD * 2
        h = inner_rect.height() + self._PAD * 2 + self._HEADER_H
        return QRectF(-self._PAD, -self._PAD - self._HEADER_H, w, h)

    # ── Button/handle positions (derived from boundingRect) ───────────────

    def _btn_positions(self):
        """Returns (acc_x, acc_y, disc_x, disc_y, res_x, res_y) in item coords."""
        r = self.boundingRect()
        x, y, w, h = r.x(), r.y(), r.width(), r.height()
        acc_x  = x + w - self._BTN_R - 6
        acc_y  = y + self._HEADER_H / 2
        disc_x = acc_x - self._BTN_R * 2 - 8
        disc_y = acc_y
        res_x  = x + w
        res_y  = y + h
        return acc_x, acc_y, disc_x, disc_y, res_x, res_y

    # ── Paint ─────────────────────────────────────────────────────────────

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        if not self._hovered:
            # Default: completely invisible wrapper — inner_item paints itself
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.boundingRect()

        # 1. Subtle hairline rounded outline (no fill)
        outline = QPainterPath()
        outline.addRoundedRect(rect, 10, 10)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(self._HOVER_BORDER, 1.2, Qt.PenStyle.SolidLine))
        painter.drawPath(outline)

        acc_x, acc_y, disc_x, disc_y, res_x, res_y = self._btn_positions()

        # 2. Accept button (✓) — green, top right
        painter.setBrush(QBrush(self._ACCEPT_CLR))
        painter.setPen(QPen(self._BTN_TEXT_CLR, 1.5))
        painter.drawEllipse(QPointF(acc_x, acc_y), self._BTN_R, self._BTN_R)
        painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        painter.drawText(
            QRectF(acc_x - self._BTN_R, acc_y - self._BTN_R, self._BTN_R * 2, self._BTN_R * 2),
            Qt.AlignmentFlag.AlignCenter, "✓"
        )

        # 3. Discard button (✕) — red, adjacent left
        painter.setBrush(QBrush(self._DISCARD_CLR))
        painter.setPen(QPen(self._BTN_TEXT_CLR, 1.5))
        painter.drawEllipse(QPointF(disc_x, disc_y), self._BTN_R, self._BTN_R)
        painter.drawText(
            QRectF(disc_x - self._BTN_R, disc_y - self._BTN_R, self._BTN_R * 2, self._BTN_R * 2),
            Qt.AlignmentFlag.AlignCenter, "✕"
        )

        # 4. Resize handle — small grey dot at bottom-right corner
        painter.setBrush(QBrush(self._RESIZE_CLR))
        painter.setPen(QPen(self._BTN_TEXT_CLR, 1.0))
        painter.drawEllipse(QPointF(res_x - 4, res_y - 4), self._RESIZE_R, self._RESIZE_R)

        painter.restore()

    # ── Hover ─────────────────────────────────────────────────────────────

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    # ── Mouse interaction ─────────────────────────────────────────────────

    def mousePressEvent(self, event):
        pos = event.pos()
        acc_x, acc_y, disc_x, disc_y, res_x, res_y = self._btn_positions()

        # Accept button — only hittable while visible (hover)
        if self._hovered and math.hypot(pos.x() - acc_x, pos.y() - acc_y) <= self._BTN_HIT_R:
            self.accept_draft()
            event.accept()
            return

        # Discard button
        if self._hovered and math.hypot(pos.x() - disc_x, pos.y() - disc_y) <= self._BTN_HIT_R:
            self.discard_draft()
            event.accept()
            return

        # Resize handle
        if self._hovered and math.hypot(pos.x() - (res_x - 4), pos.y() - (res_y - 4)) <= self._RESIZE_HIT_R:
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

    # ── Accept / Discard ──────────────────────────────────────────────────

    def accept_draft(self):
        """
        Confirms the draft: unlocks the inner item tree, detaches it from this wrapper,
        adds it permanently to the scene at current global position, and removes the
        draft overlay entirely — accepted content carries NO residual AI styling and
        is immediately freely movable/editable like any other canvas item.
        """
        scene = self.scene()
        if not scene:
            return

        final_scene_pos = self.scenePos()
        final_scale = self.scale()

        # Restore full interactivity BEFORE reparenting so Qt sees correct flags
        _unlock_item_tree(self.inner_item)

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
        Rejects and deletes the draft candidate.
        Removing self from the scene cascades to ALL parented children — nothing survives.
        There is no way to have a sub-item escape and remain on the canvas after discard.
        """
        scene = self.scene()
        if scene:
            scene.removeItem(self)
            if hasattr(scene, "scene_changed"):
                scene.scene_changed.emit()
