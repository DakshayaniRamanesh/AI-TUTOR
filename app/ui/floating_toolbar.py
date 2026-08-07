"""
Floating Toolbar Widget (Microsoft Whiteboard Style)
A pill-shaped, centered bottom toolbar with core canvas tools.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QGraphicsDropShadowEffect, QFrame
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QFont
import qtawesome as qta


class FloatingToolbar(QWidget):
    """Floating pill-shaped toolbar that hovers over the canvas bottom-center."""
    
    # Signals emitted when tools are clicked
    tool_changed = pyqtSignal(str)  # "select", "pen", "highlighter", "eraser", "pan"
    action_triggered = pyqtSignal(str)  # "undo", "sticky", "note", "table", "text", "more"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)
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
        from .theme_manager import ThemeManager
        # Main container with pill shape
        self.container = QFrame(self)
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme(ThemeManager.instance().current_theme)
        
        # Drop shadow for floating effect
        shadow = QGraphicsDropShadowEffect(self.container)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 40))
        self.container.setGraphicsEffect(shadow)
        
        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        # ── Tool Buttons ──
        # Undo
        btn_undo = self._make_btn('fa5s.undo', "Undo (Ctrl+Z)")
        btn_undo.clicked.connect(lambda: self.action_triggered.emit("undo"))
        layout.addWidget(btn_undo)

        self._add_separator(layout)

        # Select (cursor)
        self.btn_select = self._make_btn('fa5s.mouse-pointer', "Select (V)")
        self.btn_select.setCheckable(True)
        self.btn_select.setChecked(True)
        self.btn_select.clicked.connect(lambda: self._set_tool("select"))
        layout.addWidget(self.btn_select)

        # Pan (hand)
        self.btn_pan = self._make_btn('fa5s.hand-paper', "Pan (H)")
        self.btn_pan.setCheckable(True)
        self.btn_pan.clicked.connect(lambda: self._set_tool("pan"))
        layout.addWidget(self.btn_pan)

        # Pen
        self.btn_pen = self._make_btn('fa5s.pen', "Pen (P)")
        self.btn_pen.setCheckable(True)
        self.btn_pen.clicked.connect(lambda: self._set_tool("pen"))
        layout.addWidget(self.btn_pen)

        # Highlighter
        self.btn_highlighter = self._make_btn('fa5s.highlighter', "Highlighter (Alt+H)")
        self.btn_highlighter.setCheckable(True)
        self.btn_highlighter.clicked.connect(lambda: self._set_tool("highlighter"))
        layout.addWidget(self.btn_highlighter)

        # Eraser
        self.btn_eraser = self._make_btn('fa5s.eraser', "Eraser (E)")
        self.btn_eraser.setCheckable(True)
        self.btn_eraser.clicked.connect(lambda: self._set_tool("eraser"))
        layout.addWidget(self.btn_eraser)
        
        # Shapes
        self.btn_shapes = self._make_btn('fa5s.shapes', "Shapes (S)")
        self.btn_shapes.setCheckable(True)
        self.btn_shapes.clicked.connect(lambda: self._set_tool("shapes"))
        layout.addWidget(self.btn_shapes)

        self._add_separator(layout)

        # Text
        btn_text = self._make_btn('fa5s.font', "Text (T)")
        btn_text.clicked.connect(lambda: self.action_triggered.emit("text"))
        layout.addWidget(btn_text)

        # More menu (...)
        self.btn_more = self._make_btn('fa5s.ellipsis-h', "More Options")
        self.btn_more.clicked.connect(lambda: self.action_triggered.emit("more"))
        layout.addWidget(self.btn_more)

        self._add_separator(layout)

        # LaTeX Export
        self.btn_latex = self._make_btn('fa5s.file-export', "Convert to LaTeX (Ctrl+E)")
        self.btn_latex.setStyleSheet("""
            QPushButton {
                background: #f3e8ff;
                border: none;
                border-radius: 12px;
                padding: 8px;
            }
            QPushButton:hover { background: #e9d5ff; }
            QPushButton:pressed { background: #d8b4fe; }
        """)
        # Using a custom purple icon for latex button
        self.btn_latex.setIcon(qta.icon('fa5s.file-export', color='#7c3aed'))
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
        }

        # Outer layout to center the container
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch()
        outer.addWidget(self.container)
        outer.addStretch()

    def _make_btn(self, icon_name: str, tooltip: str, color: str = '#475569') -> QPushButton:
        btn = QPushButton(qta.icon(icon_name, color=color), "", self)
        btn.setIconSize(QSize(18, 18))
        btn.setFixedSize(38, 38)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tooltip)
        btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
            }
            QPushButton:checked {
                background-color: #1e293b;
            }
        """)
        return btn

    def _add_separator(self, layout):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedHeight(28)
        sep.setStyleSheet("color: #e2e8f0;")
        layout.addWidget(sep)

    def _set_tool(self, tool_name: str):
        self._active_tool = tool_name
        # Uncheck all, then check the active one
        for name, btn in self._tool_buttons.items():
            btn.setChecked(name == tool_name)
            # Swap icon color: white when active, grey when not
            icon_map = {
                "select": "fa5s.mouse-pointer",
                "pan": "fa5s.hand-paper",
                "pen": "fa5s.pen",
                "highlighter": "fa5s.highlighter",
                "eraser": "fa5s.eraser",
                "shapes": "fa5s.shapes"
            }
            c = "#ffffff" if name == tool_name else "#475569"
            btn.setIcon(qta.icon(icon_map[name], color=c))
        self.tool_changed.emit(tool_name)

    def _apply_theme(self, theme_name: str = "light"):
        from .theme_manager import ThemeManager
        c = ThemeManager.instance().get_colors()
        self.container.setStyleSheet(f"""
            QFrame {{
                background-color: {c['bg_toolbar']};
                border: 1px solid {c['border_color']};
                border-radius: 16px;
            }}
        """)
