"""
Remote Collaborator Cursor Graphics Item
Renders a collaborator's live pointer arrow and name pill tag on the whiteboard canvas.
"""

from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPolygonF, QFont, QPainterPath
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer


class RemoteCollaboratorCursor(QGraphicsItem):
    """
    Renders a collaborator's live cursor pointer and name badge on the canvas.
    Auto-hides after a period of inactivity.
    """

    def __init__(self, client_id: str, name: str, color_hex: str = "#8b5cf6", parent=None):
        super().__init__(parent)
        self.client_id = client_id
        self.name = name or "Collaborator"
        self.color = QColor(color_hex)
        
        # High Z-value so it floats over canvas items
        self.setZValue(9999)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, False)

        # Inactivity auto-fade timer
        self._fade_timer = QTimer()
        self._fade_timer.setSingleShot(True)
        self._fade_timer.setInterval(3500) # Hide after 3.5s of no movement
        self._fade_timer.timeout.connect(self._on_idle_timeout)

    def set_position(self, x: float, y: float):
        """Updates the cursor position and resets the idle timer."""
        self.setPos(x, y)
        self.setVisible(True)
        self._fade_timer.start()
        self.update()

    def update_info(self, name: str, color_hex: str):
        self.name = name or self.name
        self.color = QColor(color_hex)
        self.update()

    def _on_idle_timeout(self):
        self.setVisible(False)

    def boundingRect(self) -> QRectF:
        # Generous bounding rect covering arrow and name badge
        return QRectF(-4, -4, 180, 50)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Draw pointer arrow
        arrow = QPolygonF([
            QPointF(0, 0),
            QPointF(0, 18),
            QPointF(4.5, 14),
            QPointF(8.5, 21),
            QPointF(11.5, 19.5),
            QPointF(7.5, 13),
            QPointF(13.5, 13),
        ])

        # Drop shadow for arrow
        painter.save()
        painter.translate(1.5, 1.5)
        painter.setBrush(QColor(0, 0, 0, 60))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(arrow)
        painter.restore()

        # Arrow Fill & Border
        painter.setBrush(self.color)
        painter.setPen(QPen(QColor("#ffffff"), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPolygon(arrow)

        # 2. Draw Name Badge Pill Tag
        badge_x = 14
        badge_y = 16
        
        font = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(self.name)
        badge_w = text_w + 16
        badge_h = 20

        badge_rect = QRectF(badge_x, badge_y, badge_w, badge_h)

        # Badge shadow
        painter.save()
        painter.setBrush(QColor(0, 0, 0, 40))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(badge_rect.adjusted(1, 1, 1, 1), 10, 10)
        painter.restore()

        # Badge pill
        painter.setBrush(self.color)
        painter.setPen(QPen(QColor("#ffffff"), 1.0))
        painter.drawRoundedRect(badge_rect, 10, 10)

        # Badge text
        painter.setPen(QColor("#ffffff"))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, self.name)
