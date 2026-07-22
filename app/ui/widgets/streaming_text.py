"""
Typewriter / Incremental Text Streaming Widget and Handwritten Font Loader
Dynamically updates parent QGraphicsProxyWidget geometry to prevent any boundary clipping
"""

import os
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import QTimer, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QFontDatabase

HANDWRITTEN_FONT_FAMILY = "Caveat"

def get_handwritten_font(point_size: int = 16, bold: bool = False) -> QFont:
    """
    Returns the bundled handwritten font if available, or a fallback script font.
    """
    font_path = os.path.abspath("app/data/fonts/Caveat.ttf")
    if os.path.exists(font_path):
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                font = QFont(families[0], point_size)
                font.setBold(bold)
                return font
                
    # Fallback script font
    font = QFont("Comic Sans MS", point_size)
    font.setStyleHint(QFont.StyleHint.Cursive)
    font.setBold(bold)
    return font

class TypewriterLabel(QLabel):
    """
    Streaming text label that reveals content incrementally (one character/line at a time).
    Never auto-clears. Dynamically expands parent container and QGraphicsProxyWidget geometry.
    """
    stream_finished = pyqtSignal()

    def __init__(self, full_text: str = "", speed_ms: int = 20, parent=None):
        super().__init__(parent)
        self.full_text = full_text
        self.current_index = 0
        self.speed_ms = speed_ms
        self.setFont(get_handwritten_font(22))
        self.setStyleSheet("color: #0b2545; background: transparent; padding: 4px;")
        self.setWordWrap(True)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)

    def start_streaming(self, text: str = None, speed_ms: int = None):
        if text is not None:
            self.full_text = text
        if speed_ms is not None:
            self.speed_ms = speed_ms
        self.current_index = 0
        self.setText("")
        if self.full_text:
            self.timer.start(self.speed_ms)
        else:
            self.stream_finished.emit()

    def _on_tick(self):
        if self.current_index < len(self.full_text):
            # Reveal 1 to 3 characters at a time for smooth feel
            chunk_size = min(3, len(self.full_text) - self.current_index)
            self.current_index += chunk_size
            self.setText(self.full_text[:self.current_index])
            self.adjustSize()
            
            parent = self.parentWidget()
            if parent:
                parent.adjustSize()
                if hasattr(parent, "update_proxy_geometry"):
                    parent.update_proxy_geometry()
        else:
            self.timer.stop()
            self.stream_finished.emit()
