"""
Floating Toolbar Widget (Microsoft Whiteboard / Figma Style)
A sleek, pill-shaped, floating toolbar centered over the canvas with core creative & STEM tools.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QGraphicsDropShadowEffect, QFrame
)
from PyQt6.QtCore import Qt, QSize, QPoint, pyqtSignal
from PyQt6.QtGui import QColor
import qtawesome as qta
from .theme_manager import ThemeManager


class FloatingToolbar(QWidget):
    """Floating pill-shaped toolbar that hovers over the canvas."""

    tool_changed = pyqtSignal(str)      # "select", "pen", "highlighter", "eraser", "pan", "shapes", "lasso"
    action_triggered = pyqtSignal(str)  # "undo", "text", "more", "latex"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._active_tool = "select"
        self._drag_pos: QPoint | None = None
        self.user_moved = False

        self._init_ui()
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme(ThemeManager.instance().current_theme)

    # ── UI Construction ───────────────────────────────────────────────────

    def _init_ui(self):
        # Outer layout to wrap the pill container
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Main floating pill container
        self.container = QFrame(self)
        self.container.setObjectName("FloatingToolbarContainer")

        # Soft drop shadow for floating elevation
        shadow = QGraphicsDropShadowEffect(self.container)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 45))
        self.container.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        # ── 1. Undo ──
        self.btn_undo = self._make_btn('ri.arrow-go-back-line', "Undo (Ctrl+Z)", checkable=False)
        self.btn_undo.clicked.connect(lambda: self.action_triggered.emit("undo"))
        layout.addWidget(self.btn_undo)

        self._add_separator(layout)

        # ── 2. Selection & Navigation Tools ──
        self.btn_select = self._make_btn('ri.cursor-line', "Select (V)")
        self.btn_select.setChecked(True)
        self.btn_select.clicked.connect(lambda: self._set_tool("select"))
        layout.addWidget(self.btn_select)

        self.btn_pan = self._make_btn('ri.drag-move-line', "Pan (H)")
        self.btn_pan.clicked.connect(lambda: self._set_tool("pan"))
        layout.addWidget(self.btn_pan)

        # ── 3. Drawing & Marking Tools ──
        self.btn_pen = self._make_btn('ri.pen-nib-line', "Pen (P)")
        self.btn_pen.clicked.connect(lambda: self._set_tool("pen"))
        layout.addWidget(self.btn_pen)

        self.btn_highlighter = self._make_btn('ri.mark-pen-line', "Highlighter (Alt+H)")
        self.btn_highlighter.clicked.connect(lambda: self._set_tool("highlighter"))
        layout.addWidget(self.btn_highlighter)

        self.btn_eraser = self._make_btn('ri.eraser-line', "Eraser (E)")
        self.btn_eraser.clicked.connect(lambda: self._set_tool("eraser"))
        layout.addWidget(self.btn_eraser)

        self.btn_shapes = self._make_btn('ri.shape-line', "Shapes (S)")
        self.btn_shapes.clicked.connect(lambda: self._set_tool("shapes"))
        layout.addWidget(self.btn_shapes)

        self.btn_lasso = self._make_btn('ri.scissors-cut-line', "Lasso Selection (L)")
        self.btn_lasso.clicked.connect(lambda: self._set_tool("lasso"))
        layout.addWidget(self.btn_lasso)

        self._add_separator(layout)

        # ── 4. Annotation & Extension Tools ──
        self.btn_text = self._make_btn('ri.text', "Text (T)", checkable=False)
        self.btn_text.clicked.connect(lambda: self.action_triggered.emit("text"))
        layout.addWidget(self.btn_text)

        self.btn_more = self._make_btn('ri.more-line', "More Options", checkable=False)
        self.btn_more.clicked.connect(lambda: self.action_triggered.emit("more"))
        layout.addWidget(self.btn_more)

        self._add_separator(layout)

        # ── 5. LaTeX Conversion Trigger ──
        self.btn_latex = self._make_btn('ri.file-upload-line', "Convert to LaTeX (Ctrl+E)", checkable=False)
        self.btn_latex.clicked.connect(lambda: self.action_triggered.emit("latex"))
        layout.addWidget(self.btn_latex)

        self._tool_buttons = {
            "select":      self.btn_select,
            "pan":         self.btn_pan,
            "pen":         self.btn_pen,
            "highlighter": self.btn_highlighter,
            "eraser":      self.btn_eraser,
            "shapes":      self.btn_shapes,
            "lasso":       self.btn_lasso,
        }

        outer.addWidget(self.container)
        self.adjustSize()

    # ── Tool Selection & Visual Sync ──────────────────────────────────────

    def _set_tool(self, tool_name: str):
        self._active_tool = tool_name
        c = ThemeManager.instance().get_colors()

        icon_map = {
            "select":      "ri.cursor-line",
            "pan":         "ri.drag-move-line",
            "pen":         "ri.pen-nib-line",
            "highlighter": "ri.mark-pen-line",
            "eraser":      "ri.eraser-line",
            "shapes":      "ri.shape-line",
            "lasso":       "ri.scissors-cut-line",
        }

        for name, btn in self._tool_buttons.items():
            active = (name == tool_name)
            btn.setChecked(active)
            color = c["accent_text"] if active else c["text_secondary"]
            btn.setIcon(qta.icon(icon_map.get(name, "ri.cursor-line"), color=color))

        self.tool_changed.emit(tool_name)

    # ── Mouse Dragging Events ─────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            parent = self.parentWidget()
            if parent:
                new_pos.setX(max(0, min(new_pos.x(), parent.width() - self.width())))
                new_pos.setY(max(0, min(new_pos.y(), parent.height() - self.height())))
            self.move(new_pos)
            self.user_moved = True
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
            event.accept()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _make_btn(self, icon_name: str, tooltip: str, checkable: bool = True) -> QPushButton:
        c = ThemeManager.instance().get_colors()
        btn = QPushButton(qta.icon(icon_name, color=c["text_secondary"]), "", self.container)
        btn.setIconSize(QSize(17, 17))
        btn.setFixedSize(36, 36)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tooltip)
        btn.setCheckable(checkable)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn._icon_name = icon_name
        btn.setStyleSheet(self._tool_btn_qss(c))
        return btn

    def _add_separator(self, layout):
        c = ThemeManager.instance().get_colors()
        sep = QFrame(self.container)
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedHeight(22)
        sep.setStyleSheet(f"color: {c['border_color']}; margin: 0 3px;")
        layout.addWidget(sep)

    def _tool_btn_qss(self, c: dict) -> str:
        return f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {c['panel_card_bg']};
            }}
            QPushButton:checked {{
                background-color: {c['accent']};
            }}
            QPushButton:pressed {{
                background-color: {c['accent_hover']};
            }}
        """

    def _apply_theme(self, theme_name: str = "light"):
        c = ThemeManager.instance().get_colors()
        is_dark = ThemeManager.instance().is_dark()

        bg = "#1a1a1f" if is_dark else "#ffffff"
        border = "#333340" if is_dark else "#d0d0d0"

        self.container.setStyleSheet(f"""
            QFrame#FloatingToolbarContainer {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
        """)

        # Re-apply styling and colors to buttons
        for btn in self.findChildren(QPushButton):
            btn.setStyleSheet(self._tool_btn_qss(c))

        self._set_tool(self._active_tool)