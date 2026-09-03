"""
Floating Toolbar Widget (Technical / Monochrome Aesthetic)
A sharp-bordered, centered bottom toolbar with core canvas tools.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QGraphicsDropShadowEffect, QFrame
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QColor
import qtawesome as qta
from .theme_manager import ThemeManager


class FloatingToolbar(QWidget):
    """Floating sharp-bordered toolbar that hovers over the canvas bottom-center."""
    
    # Signals emitted when tools are clicked
    tool_changed = pyqtSignal(str)  # "select", "pen", "highlighter", "eraser", "pan"
    action_triggered = pyqtSignal(str)  # "undo", "sticky", "note", "table", "text", "more"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._active_tool = "select"
        self._drag_pos = None
        self.user_moved = False
        self._init_ui()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()
            self.user_moved = True
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
            event.accept()

    def _init_ui(self):
        c = ThemeManager.instance().get_colors()
        
        # Main container with sharp / minimal 4px border radius
        self.container = QFrame(self)
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme(ThemeManager.instance().current_theme)
        
        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        # ── Tool Buttons (Remix Icons outline set) ──
        # Undo
        btn_undo = self._make_btn('ri.arrow-go-back-line', "Undo (Ctrl+Z)")
        btn_undo.clicked.connect(lambda: self.action_triggered.emit("undo"))
        layout.addWidget(btn_undo)

        self._add_separator(layout)

        # Select (cursor)
        self.btn_select = self._make_btn('ri.cursor-line', "Select (V)")
        self.btn_select.setCheckable(True)
        self.btn_select.setChecked(True)
        self.btn_select.clicked.connect(lambda: self._set_tool("select"))
        layout.addWidget(self.btn_select)

        # Pan (hand)
        self.btn_pan = self._make_btn('ri.drag-move-line', "Pan (H)")
        self.btn_pan.setCheckable(True)
        self.btn_pan.clicked.connect(lambda: self._set_tool("pan"))
        layout.addWidget(self.btn_pan)

        # Pen
        self.btn_pen = self._make_btn('ri.pen-nib-line', "Pen (P)")
        self.btn_pen.setCheckable(True)
        self.btn_pen.clicked.connect(lambda: self._set_tool("pen"))
        layout.addWidget(self.btn_pen)

        # Highlighter
        self.btn_highlighter = self._make_btn('ri.mark-pen-line', "Highlighter (Alt+H)")
        self.btn_highlighter.setCheckable(True)
        self.btn_highlighter.clicked.connect(lambda: self._set_tool("highlighter"))
        layout.addWidget(self.btn_highlighter)

        # Eraser
        self.btn_eraser = self._make_btn('ri.eraser-line', "Eraser (E)")
        self.btn_eraser.setCheckable(True)
        self.btn_eraser.clicked.connect(lambda: self._set_tool("eraser"))
        layout.addWidget(self.btn_eraser)
        
        # Shapes
        self.btn_shapes = self._make_btn('ri.shape-line', "Shapes (S)")
        self.btn_shapes.setCheckable(True)
        self.btn_shapes.clicked.connect(lambda: self._set_tool("shapes"))
        layout.addWidget(self.btn_shapes)

        # Lasso Selection (Penecho)
        self.btn_lasso = self._make_btn('ri.scissors-cut-line', "Lasso Selection (L)")
        self.btn_lasso.setCheckable(True)
        self.btn_lasso.clicked.connect(lambda: self._set_tool("lasso"))
        layout.addWidget(self.btn_lasso)

        self._add_separator(layout)

        # Text
        btn_text = self._make_btn('ri.text', "Text (T)")
        btn_text.clicked.connect(lambda: self.action_triggered.emit("text"))
        layout.addWidget(btn_text)

        # More menu (...)
        self.btn_more = self._make_btn('ri.more-line', "More Options")
        self.btn_more.clicked.connect(lambda: self.action_triggered.emit("more"))
        layout.addWidget(self.btn_more)

        self._add_separator(layout)

        # LaTeX Export
        self.btn_latex = self._make_btn('ri.file-upload-line', "Convert to LaTeX (Ctrl+E)")
        self.btn_latex.clicked.connect(lambda: self.action_triggered.emit("latex"))
        layout.addWidget(self.btn_latex)

        # Store all tool buttons for toggling
        self._tool_buttons = {
            "select": self.btn_select,
            "pan": self.btn_pan,
            "pen": self.btn_pen,
            "highlighter": self.btn_highlighter,
            "eraser": self.btn_eraser,
            "shapes": self.btn_shapes,
            "lasso": self.btn_lasso,
        }

        # Outer layout to center the container
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch()
        outer.addWidget(self.container)
        outer.addStretch()

        # Set default active icon state
        self._set_tool("select")

    def _make_btn(self, icon_name: str, tooltip: str) -> QPushButton:
        c = ThemeManager.instance().get_colors()
        btn = QPushButton(qta.icon(icon_name, color=c['text_secondary']), "", self)
        btn.setIconSize(QSize(17, 17))
        btn.setFixedSize(34, 34)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tooltip)
        btn._icon_name = icon_name
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 2px;
            }}
            QPushButton:hover {{
                background-color: {c['panel_card_bg']};
            }}
            QPushButton:checked {{
                background-color: {c['accent']};
            }}
        """)
        return btn

    def _add_separator(self, layout):
        c = ThemeManager.instance().get_colors()
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedHeight(20)
        sep.setStyleSheet(f"color: {c['border_color']}; margin: 0 2px;")
        layout.addWidget(sep)

    def _set_tool(self, tool_name: str):
        self._active_tool = tool_name
        if not hasattr(self, '_tool_buttons'):
            return
        c = ThemeManager.instance().get_colors()
        icon_map = {
            "select": "ri.cursor-line",
            "pan": "ri.drag-move-line",
            "pen": "ri.pen-nib-line",
            "highlighter": "ri.mark-pen-line",
            "eraser": "ri.eraser-line",
            "shapes": "ri.shape-line",
            "lasso": "ri.scissors-cut-line"
        }
        for name, btn in self._tool_buttons.items():
            is_active = (name == tool_name)
            btn.setChecked(is_active)
            col = c['accent_text'] if is_active else c['text_secondary']
            btn.setIcon(qta.icon(icon_map.get(name, 'ri.cursor-line'), color=col))
        self.tool_changed.emit(tool_name)

    def _apply_theme(self, theme_name: str = "light"):
        c = ThemeManager.instance().get_colors()
        if hasattr(self, 'container'):
            self.container.setStyleSheet(f"""
                QFrame {{
                    background-color: {c['bg_toolbar']};
                    border: 1px solid {c['border_color']};
                    border-radius: 4px;
                }}
            """)
        # Refresh buttons styles
        for name, btn in getattr(self, '_tool_buttons', {}).items():
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-radius: 2px;
                }}
                QPushButton:hover {{
                    background-color: {c['panel_card_bg']};
                }}
                QPushButton:checked {{
                    background-color: {c['accent']};
                }}
            """)
        if hasattr(self, '_active_tool') and hasattr(self, '_tool_buttons'):
            self._set_tool(self._active_tool)
