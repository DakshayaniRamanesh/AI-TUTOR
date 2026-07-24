from PyQt6.QtWidgets import QGraphicsPixmapItem, QGraphicsItem
from PyQt6.QtGui import QPixmap, QPainter
from PyQt6.QtCore import Qt

class ImageItem(QGraphicsPixmapItem):
    """
    A resizable and movable image item that users can paste onto the canvas.
    """
    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(pixmap, parent)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        # Scale down if it's massive
        if pixmap.width() > 800:
            scale_factor = 800 / pixmap.width()
            self.setScale(scale_factor)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        super().paint(painter, option, widget)
        
        if self.isSelected():
            painter.setPen(Qt.GlobalColor.blue)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.boundingRect())

    def to_dict(self):
        import base64
        from PyQt6.QtCore import QBuffer, QIODevice
        
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        self.pixmap().save(buffer, "PNG")
        b64_data = base64.b64encode(buffer.data().data()).decode('utf-8')
        
        return {
            "type": "ImageItem",
            "x": self.x(),
            "y": self.y(),
            "scale": self.scale(),
            "image_b64": b64_data,
            "z_value": self.zValue()
        }
