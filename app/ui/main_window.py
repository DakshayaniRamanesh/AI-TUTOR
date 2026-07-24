"""
Main Application Window (Apple Freeform Shell Layout)
Frameless macOS Window Design with Traffic Light Controls (Close, Minimize, Maximize),
Dynamic Rounded Corners (14px Windowed, 0px Maximized), Title Bar Dragging, and 8-Direction Resizing.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget,
    QListWidgetItem, QPushButton, QLineEdit, QLabel, QFrame,
    QSplitter, QStackedWidget, QFileDialog, QInputDialog, QMessageBox,
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QSize, QEvent, QPoint
from PyQt6.QtGui import QFont, QColor
import qtawesome as qta

from .canvas_scene import CanvasScene
from .canvas_view import CanvasView
from .items.sticky_note import StickyNote
from .items.handwriting_note import HandwritingNote
from .items.table_item import TableItem
from .items.card_item import CardItem
from .items.map_pin_card import MapPinCard
from .items.group_selection import GroupSelection
from .items.video_float_item import VideoFloatItem
from .items.answer_bubble import AnswerBubble
from .items.graph_card import GraphCard

from .widgets.ask_bar import AskBar
from .widgets.reference_panel import ReferencePanel
from .views.notebooks_panel import NotebooksPanel
from .views.git_notes_panel import GitNotesPanel
from .views.shared_panel import SharedPanel

from ..backend.stem_solver import solve_stem_question
from ..backend.video_gen_client import request_video_generation
from ..storage.board_model import BoardModel
from ..storage.notebook_storage import NotebookStorage
from ..storage.downloads_manager import DownloadsManager


class MacTitleBar(QWidget):
    """Custom macOS-Inspired Title Bar with Traffic Light Window Controls & Seamless Blending."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setObjectName("MacTitleBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(8)

        # macOS Traffic Light Buttons Container
        tl_box = QWidget(self)
        tl_box.setStyleSheet("background: transparent;")
        tl_layout = QHBoxLayout(tl_box)
        tl_layout.setContentsMargins(0, 0, 0, 0)
        tl_layout.setSpacing(8)

        # 🔴 Red - Close
        self.btn_close = QPushButton("×", tl_box)
        self.btn_close.setFixedSize(13, 13)
        self.btn_close.setToolTip("Close Application")
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #ff5f56;
                border: 1px solid #e0443e;
                border-radius: 6px;
                color: transparent;
                font-size: 11px;
                font-weight: bold;
                padding: 0px;
                line-height: 11px;
            }
            QPushButton:hover {
                color: #4a0000;
            }
            QPushButton:pressed {
                background-color: #bf433d;
            }
        """)
        self.btn_close.clicked.connect(self._on_close_clicked)

        # 🟡 Yellow - Minimize
        self.btn_min = QPushButton("–", tl_box)
        self.btn_min.setFixedSize(13, 13)
        self.btn_min.setToolTip("Minimize Window")
        self.btn_min.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_min.setStyleSheet("""
            QPushButton {
                background-color: #ffbd2e;
                border: 1px solid #dea123;
                border-radius: 6px;
                color: transparent;
                font-size: 11px;
                font-weight: bold;
                padding: 0px;
                line-height: 11px;
            }
            QPushButton:hover {
                color: #5c4300;
            }
            QPushButton:pressed {
                background-color: #bf8e22;
            }
        """)
        self.btn_min.clicked.connect(self._on_min_clicked)

        # 🟢 Green - Maximize / Restore
        self.btn_max = QPushButton("⤢", tl_box)
        self.btn_max.setFixedSize(13, 13)
        self.btn_max.setToolTip("Maximize / Restore Window")
        self.btn_max.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_max.setStyleSheet("""
            QPushButton {
                background-color: #27c93f;
                border: 1px solid #1aab29;
                border-radius: 6px;
                color: transparent;
                font-size: 9px;
                font-weight: bold;
                padding: 0px;
                line-height: 11px;
            }
            QPushButton:hover {
                color: #004d00;
            }
            QPushButton:pressed {
                background-color: #1d9930;
            }
        """)
        self.btn_max.clicked.connect(self._on_max_clicked)

        tl_layout.addWidget(self.btn_close)
        tl_layout.addWidget(self.btn_min)
        tl_layout.addWidget(self.btn_max)

        layout.addWidget(tl_box)
        layout.addStretch()

        self.lbl_title = QLabel("Kestrel — Handwritten Freeform Notebook", self)
        self.lbl_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #3a3a3c; background: transparent;")
        layout.addWidget(self.lbl_title)

        layout.addStretch()

    def _on_close_clicked(self):
        self.window().close()

    def _on_min_clicked(self):
        self.window().showMinimized()

    def _on_max_clicked(self):
        w = self.window()
        if w.isMaximized():
            w.showNormal()
        else:
            w.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle:
                handle.startSystemMove()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_max_clicked()


class MainWindow(QMainWindow):
    RESIZE_MARGIN = 8

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kestrel")
        self.resize(1280, 800)
        self.setMinimumSize(900, 600)

        # 1. Set Frameless Window Flags & Translucent Background
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowMinMaxButtonsHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self.current_board = BoardModel("Notebook Board 1")
        self.downloads_mgr = DownloadsManager()
        self.reference_panel = ReferencePanel()
        self.reference_panel.insert_data_requested.connect(self._on_insert_reference_table)
        self._solver_workers = []

        self._apply_global_styles()
        self._init_ui()
        self._update_window_corners()

    def _init_ui(self):
        # Outer Translucent Container
        outer_widget = QWidget(self)
        self.setCentralWidget(outer_widget)
        self.outer_layout = QVBoxLayout(outer_widget)
        self.outer_layout.setContentsMargins(6, 6, 6, 6)
        self.outer_layout.setSpacing(0)

        # Central Card (Handles rounded corners & drop shadow in windowed mode)
        self.central_card = QWidget(outer_widget)
        self.central_card.setObjectName("CentralCard")

        shadow = QGraphicsDropShadowEffect(self.central_card)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 55))
        shadow.setOffset(0, 3)
        self.central_card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.central_card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # 1. macOS Custom Title Bar
        self.title_bar = MacTitleBar(self.central_card)
        card_layout.addWidget(self.title_bar)

        # 2. Main Content Splitter (Sidebar + Main View Stack)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)

        # Sidebar Panel (~260px wide)
        self.sidebar = self._create_sidebar()
        self.splitter.addWidget(self.sidebar)

        # Canvas & Toolbar Container
        self.canvas_container = QWidget(self.central_card)
        cc_layout = QVBoxLayout(self.canvas_container)
        cc_layout.setContentsMargins(0, 0, 0, 0)
        cc_layout.setSpacing(0)

        # Top Toolbar
        self.toolbar = self._create_top_toolbar()
        cc_layout.addWidget(self.toolbar)

        # Main View Stack (Index 0: Canvas View, Index 1: Notebooks View)
        self.main_stack = QStackedWidget(self.canvas_container)

        # Canvas View Wrapper
        canvas_wrapper = QWidget(self.main_stack)
        cw_layout = QVBoxLayout(canvas_wrapper)
        cw_layout.setContentsMargins(0, 0, 0, 0)
        cw_layout.setSpacing(0)

        # Scene and View
        self.scene = CanvasScene(self)
        self.scene.ink_written_detected.connect(self._on_ink_written_detected)
        self.view = CanvasView(self.scene, self)
        self.view.zoom_changed.connect(self._on_zoom_changed)
        cw_layout.addWidget(self.view)

        # Bottom Floating HUD Overlay (AskBar + Zoom HUD + Floating Tools)
        self.hud_overlay = self._create_hud_overlay()
        cw_layout.addWidget(self.hud_overlay)

        self.main_stack.addWidget(canvas_wrapper) # Index 0

        # Notebooks View Panel
        self.notebooks_panel = NotebooksPanel(self.main_stack)
        self.notebooks_panel.open_notebook_requested.connect(self._on_load_notebook_requested)
        self.notebooks_panel.create_notebook_requested.connect(self._on_new_notebook_requested)
        self.notebooks_panel.git_vcs_requested.connect(self._on_notebook_git_requested)
        self.main_stack.addWidget(self.notebooks_panel) # Index 1

        # Git Notes VCS View Panel
        self.git_notes_panel = GitNotesPanel(self.main_stack)
        self.main_stack.addWidget(self.git_notes_panel) # Index 2

        # Shared Collaboration Hub View Panel
        self.shared_panel = SharedPanel(self.main_stack)
        self.main_stack.addWidget(self.shared_panel) # Index 3

        cc_layout.addWidget(self.main_stack)
        self.splitter.addWidget(self.canvas_container)

        self.splitter.setSizes([260, 1020])
        card_layout.addWidget(self.splitter)
        self.outer_layout.addWidget(self.central_card)

        self._populate_demo_canvas()

    def _apply_global_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background: transparent;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }
            QSplitter::handle {
                background-color: #d1d1d6;
            }
        """)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self._update_window_corners()

    def _update_window_corners(self):
        if self.isMaximized():
            if hasattr(self, 'outer_layout'):
                self.outer_layout.setContentsMargins(0, 0, 0, 0)
            self.central_card.setStyleSheet("""
                QWidget#CentralCard {
                    background-color: #f8f8fa;
                    border-radius: 0px;
                    border: none;
                }
                QWidget#MacTitleBar {
                    background-color: #f2f2f7;
                    border-top-left-radius: 0px;
                    border-top-right-radius: 0px;
                    border-bottom: 1px solid #d1d1d6;
                }
            """)
        else:
            if hasattr(self, 'outer_layout'):
                self.outer_layout.setContentsMargins(6, 6, 6, 6)
            self.central_card.setStyleSheet("""
                QWidget#CentralCard {
                    background-color: #f8f8fa;
                    border-radius: 12px;
                    border: 1px solid #d1d1d6;
                }
                QWidget#MacTitleBar {
                    background-color: #f2f2f7;
                    border-top-left-radius: 12px;
                    border-top-right-radius: 12px;
                    border-bottom: 1px solid #d1d1d6;
                }
            """)

    # --- 8-Direction Resizing Engine ---
    def _get_resize_edges(self, pos: QPoint):
        if self.isMaximized():
            return None
        margin = self.RESIZE_MARGIN
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()

        left = x <= margin
        right = x >= w - margin
        top = y <= margin
        bottom = y >= h - margin

        if top and left: return Qt.Edge.TopEdge | Qt.Edge.LeftEdge
        if top and right: return Qt.Edge.TopEdge | Qt.Edge.RightEdge
        if bottom and left: return Qt.Edge.BottomEdge | Qt.Edge.LeftEdge
        if bottom and right: return Qt.Edge.BottomEdge | Qt.Edge.RightEdge
        if left: return Qt.Edge.LeftEdge
        if right: return Qt.Edge.RightEdge
        if top: return Qt.Edge.TopEdge
        if bottom: return Qt.Edge.BottomEdge
        return None

    def mouseMoveEvent(self, event):
        edges = self._get_resize_edges(event.position().toPoint())
        if edges:
            if (edges & Qt.Edge.LeftEdge and edges & Qt.Edge.TopEdge) or (edges & Qt.Edge.RightEdge and edges & Qt.Edge.BottomEdge):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif (edges & Qt.Edge.RightEdge and edges & Qt.Edge.TopEdge) or (edges & Qt.Edge.LeftEdge and edges & Qt.Edge.BottomEdge):
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge):
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge):
                self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            edges = self._get_resize_edges(event.position().toPoint())
            if edges:
                handle = self.windowHandle()
                if handle:
                    handle.startSystemResize(edges)
        super().mousePressEvent(event)

    def _create_sidebar(self) -> QWidget:
        sb = QWidget(self)
        sb.setStyleSheet("""
            QWidget {
                background-color: #f8f8fa;
                border-right: 1px solid #d1d1d6;
            }
            QListWidget {
                border: none;
                background: transparent;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 10px 14px;
                border-radius: 8px;
                margin: 2px 6px;
                color: #1c1c1e;
            }
            QListWidget::item:selected {
                background-color: #007aff;
                color: white;
                font-weight: 600;
            }
            QLabel#SidebarTitle {
                font-size: 11px;
                font-weight: bold;
                color: #8e8e93;
                padding-left: 12px;
                padding-top: 10px;
            }
        """)

        layout = QVBoxLayout(sb)
        layout.setContentsMargins(4, 8, 4, 8)

        lbl_sec = QLabel("NAVIGATION", sb)
        lbl_sec.setObjectName("SidebarTitle")
        layout.addWidget(lbl_sec)

        self.sidebar_list = QListWidget(sb)
        items = [
            "📋 All Boards",
            "📓 Notebooks",
            "🔀 Git Notes VCS",
            "🕒 Recents",
            "👥 Shared",
            "⭐ Favourites",
            f"💾 Downloads ({len(self.downloads_mgr.get_all())})"
        ]
        for name in items:
            item = QListWidgetItem(name)
            self.sidebar_list.addItem(item)

        self.sidebar_list.setCurrentRow(0)
        self.sidebar_list.currentRowChanged.connect(self._on_sidebar_changed)
        layout.addWidget(self.sidebar_list)

        btn_ref = QPushButton("📚 Reference Database", sb)
        btn_ref.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 8px;
                padding: 8px;
                font-weight: 600;
                color: #007aff;
            }
            QPushButton:hover {
                background-color: #e5e5ea;
            }
        """)
        btn_ref.clicked.connect(self._toggle_reference_panel)
        layout.addWidget(btn_ref)

        return sb

    def _create_top_toolbar(self) -> QWidget:
        tb = QWidget(self)
        tb.setFixedHeight(48)
        tb.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border-bottom: 1px solid #d1d1d6;
            }
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 6px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #f2f2f7;
            }
            QLineEdit {
                font-size: 14px;
                font-weight: bold;
                border: none;
                color: #1c1c1e;
            }
        """)

        layout = QHBoxLayout(tb)
        layout.setContentsMargins(12, 4, 12, 4)

        btn_sb_toggle = QPushButton(qta.icon('fa5s.bars', color='#1c1c1e'), "", tb)
        btn_sb_toggle.clicked.connect(self._toggle_sidebar)
        layout.addWidget(btn_sb_toggle)

        btn_back = QPushButton(qta.icon('fa5s.chevron-left', color='#007aff'), "", tb)
        btn_back.clicked.connect(lambda: self.main_stack.setCurrentIndex(0))
        layout.addWidget(btn_back)

        self.title_edit = QLineEdit(self.current_board.title, tb)
        self.title_edit.setFixedWidth(200)
        self.title_edit.editingFinished.connect(self._on_title_changed)
        layout.addWidget(self.title_edit)

        layout.addStretch()

        pill = QWidget(tb)
        pill.setStyleSheet("""
            QWidget {
                background-color: #f2f2f7;
                border-radius: 10px;
            }
            QPushButton {
                padding: 6px 10px;
                font-weight: 600;
                font-size: 12px;
                color: #1c1c1e;
            }
        """)
        pill_layout = QHBoxLayout(pill)
        pill_layout.setContentsMargins(4, 2, 4, 2)
        pill_layout.setSpacing(2)

        btn_save = QPushButton(qta.icon('fa5s.save', color='#007aff'), "Save", pill)
        btn_save.setStyleSheet("color: #007aff; font-weight: bold;")
        btn_save.clicked.connect(self._on_toolbar_save)

        btn_paste = QPushButton(qta.icon('fa5s.paste', color='#007aff'), "Paste", pill)
        btn_paste.clicked.connect(self._on_toolbar_paste)

        btn_sticky = QPushButton(qta.icon('fa5s.sticky-note', color='#f57f17'), "Sticky", pill)
        btn_sticky.clicked.connect(self._add_sticky_note)

        btn_note = QPushButton(qta.icon('fa5s.pen', color='#007aff'), "Note", pill)
        btn_note.clicked.connect(self._add_handwriting_note)

        btn_table = QPushButton(qta.icon('fa5s.table', color='#388e3c'), "Table", pill)
        btn_table.clicked.connect(self._add_table)

        btn_group = QPushButton(qta.icon('fa5s.layer-group', color='#7b1fa2'), "Group", pill)
        btn_group.clicked.connect(self._add_group)

        self.btn_grid_mode = QPushButton("📄 Ruled Paper", pill)
        self.btn_grid_mode.setStyleSheet("color: #007aff; font-weight: bold;")
        self.btn_grid_mode.clicked.connect(self._toggle_grid_mode)

        pill_layout.addWidget(btn_save)
        pill_layout.addWidget(btn_paste)
        pill_layout.addWidget(btn_sticky)
        pill_layout.addWidget(btn_note)
        pill_layout.addWidget(btn_table)
        pill_layout.addWidget(btn_group)
        pill_layout.addWidget(self.btn_grid_mode)

        layout.addWidget(pill)
        layout.addStretch()

        return tb

    def _create_hud_overlay(self) -> QWidget:
        hud = QWidget(self)
        hud.setFixedHeight(60)
        hud.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(hud)
        layout.setContentsMargins(16, 0, 16, 10)

        zoom_hud = QWidget(hud)
        zoom_hud.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 0.9);
                border: 1px solid #d1d1d6;
                border-radius: 16px;
            }
            QPushButton {
                border: none;
                background: transparent;
                font-size: 14px;
                font-weight: bold;
                padding: 4px 8px;
            }
            QLabel {
                font-size: 12px;
                font-weight: 600;
                color: #1c1c1e;
            }
        """)
        zh_layout = QHBoxLayout(zoom_hud)
        zh_layout.setContentsMargins(6, 4, 6, 4)
        zh_layout.setSpacing(4)

        btn_zoom_out = QPushButton("–", zoom_hud)
        btn_zoom_out.clicked.connect(lambda: self.view.zoom_by(0.8))

        self.lbl_zoom = QLabel("100%", zoom_hud)

        btn_zoom_in = QPushButton("+", zoom_hud)
        btn_zoom_in.clicked.connect(lambda: self.view.zoom_by(1.2))

        zh_layout.addWidget(btn_zoom_out)
        zh_layout.addWidget(self.lbl_zoom)
        zh_layout.addWidget(btn_zoom_in)

        layout.addWidget(zoom_hud)

        self.ask_bar = AskBar(hud)
        self.ask_bar.question_submitted.connect(self._on_stem_question_asked)
        layout.addWidget(self.ask_bar)

        tools_hud = QWidget(hud)
        tools_hud.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 0.9);
                border: 1px solid #d1d1d6;
                border-radius: 16px;
            }
            QPushButton {
                border: none;
                border-radius: 12px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #e5e5ea;
            }
        """)
        th_layout = QHBoxLayout(tools_hud)
        th_layout.setContentsMargins(6, 4, 6, 4)
        th_layout.setSpacing(4)

        btn_cursor = QPushButton(qta.icon('fa5s.mouse-pointer', color='#007aff'), "", tools_hud)
        btn_cursor.clicked.connect(lambda: self._set_tool("select"))

        btn_pen = QPushButton(qta.icon('fa5s.pen-nib', color='#1c1c1e'), "", tools_hud)
        btn_pen.clicked.connect(lambda: self._set_tool("pen"))

        btn_highlighter = QPushButton(qta.icon('fa5s.highlighter', color='#ff9500'), "", tools_hud)
        btn_highlighter.clicked.connect(lambda: self._set_tool("highlighter"))

        btn_eraser = QPushButton(qta.icon('fa5s.eraser', color='#ff3b30'), "", tools_hud)
        btn_eraser.clicked.connect(lambda: self._set_tool("eraser"))

        th_layout.addWidget(btn_cursor)
        th_layout.addWidget(btn_pen)
        th_layout.addWidget(btn_highlighter)
        th_layout.addWidget(btn_eraser)

        layout.addWidget(tools_hud)

        return hud

    def _set_tool(self, tool_name: str):
        self.scene.active_tool = tool_name

    def _toggle_sidebar(self):
        if self.sidebar.isVisible():
            self.sidebar.hide()
        else:
            self.sidebar.show()

    def _toggle_reference_panel(self):
        if self.reference_panel.isVisible():
            self.reference_panel.hide()
        else:
            self.reference_panel.show_panel(self)

    def _toggle_grid_mode(self):
        if self.scene.background_mode == "ruled":
            self.scene.set_background_mode("dotted")
            self.btn_grid_mode.setText("░ Dotted Grid")
        else:
            self.scene.set_background_mode("ruled")
            self.btn_grid_mode.setText("📄 Ruled Paper")

    def _on_zoom_changed(self, zoom_factor: float):
        self.lbl_zoom.setText(f"{int(zoom_factor * 100)}%")

    def _on_title_changed(self):
        self.current_board.title = self.title_edit.text()

    def _on_sidebar_changed(self, row: int):
        if row == 1: # "📓 Notebooks"
            self.notebooks_panel.refresh()
            self.main_stack.setCurrentIndex(1)
        elif row == 2: # "🔀 Git Notes VCS"
            self.git_notes_panel.refresh_all()
            self.main_stack.setCurrentIndex(2)
        elif row == 4: # "👥 Shared"
            self.shared_panel.refresh_all()
            self.main_stack.setCurrentIndex(3)
        else:
            self.main_stack.setCurrentIndex(0)

    def _on_toolbar_save(self):
        current_name = self.current_board.title or "Untitled Notebook"
        name, ok = QInputDialog.getText(self, "Save Notebook", "Enter Notebook Name:", text=current_name)
        if ok and name.strip():
            try:
                name_clean = name.strip()
                items_data = self.scene.to_dict_list()
                NotebookStorage.save_notebook(self.current_board.board_id, name_clean, items_data)
                self.current_board.title = name_clean
                self.title_edit.setText(name_clean)
                QMessageBox.information(self, "Saved", f"Notebook '{name_clean}' saved successfully!")
                self.notebooks_panel.refresh()
            except Exception as err:
                QMessageBox.warning(self, "Save Failed", f"Could not save notebook:\n{err}")

    def _on_load_notebook_requested(self, notebook_id: str):
        try:
            payload = NotebookStorage.load_notebook(notebook_id)
            self.current_board.board_id = payload.get("board_id", notebook_id)
            self.current_board.title = payload.get("title", "Notebook")
            self.title_edit.setText(self.current_board.title)
            
            self.scene.load_from_dict_list(
                payload.get("items", []),
                video_requested_callback=self._on_generate_video_requested,
                solve_requested_callback=self._on_stem_question_asked
            )
            
            self.main_stack.setCurrentIndex(0)
            self.sidebar_list.setCurrentRow(0)
        except Exception as err:
            QMessageBox.warning(self, "Load Failed", f"Could not load notebook:\n{err}")

    def _on_notebook_git_requested(self, notebook_id: str):
        self.sidebar_list.setCurrentRow(2) # "🔀 Git Notes VCS"
        self.git_notes_panel.open_notebook_vcs(notebook_id)
        self.main_stack.setCurrentIndex(2)

    def _on_new_notebook_requested(self):
        name, ok = QInputDialog.getText(self, "New Notebook", "Enter Notebook Name:", text="Untitled Notebook")
        if ok and name.strip():
            try:
                meta = NotebookStorage.create_notebook(name.strip())
                self.current_board.board_id = meta["id"]
                self.current_board.title = meta["name"]
                self.title_edit.setText(meta["name"])
                
                self.scene.clear_all()
                
                self.main_stack.setCurrentIndex(0)
                self.sidebar_list.setCurrentRow(0)
                self.notebooks_panel.refresh()
            except Exception as err:
                QMessageBox.warning(self, "Create Failed", f"Could not create notebook:\n{err}")

    def _on_toolbar_paste(self):
        self.scene.active_tool = "select"
        from PyQt6.QtWidgets import QApplication
        from ..backend.link_utils import is_valid_url, fetch_url_metadata
        from ..backend.summarizer_client import UrlSummarizerWorker

        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()

        if not text:
            return

        center_pos = self.view.mapToScene(self.view.viewport().rect().center())

        if is_valid_url(text):
            meta = fetch_url_metadata(text)
            if meta.get("is_video"):
                v_item = VideoFloatItem(title=meta.get("title", "Video"), video_url_or_path=text)
                v_item.setPos(center_pos)
                self.scene.addItem(v_item)
            else:
                bubble = AnswerBubble(title=f"Web Explanation: {meta.get('title', 'Article')[:25]}", full_text="Scraping & generating AI study guide...", question=f"Explain link: {text}")
                bubble.setPos(center_pos)
                self.scene.addItem(bubble)

                worker = UrlSummarizerWorker(text, title=meta.get("title", ""), parent=self)
                def _on_finished(u, t, summary):
                    bubble.update_solution(f"Explain link: {u}", summary)
                    if worker in self._solver_workers:
                        self._solver_workers.remove(worker)
                worker.finished.connect(_on_finished)
                self._solver_workers.append(worker)
                worker.start()
        else:
            note = HandwritingNote(text=text)
            note.setPos(center_pos)
            note.widget.video_requested.connect(self._on_generate_video_requested)
            note.widget.solve_requested.connect(self._on_stem_question_asked)
            self.scene.addItem(note)

    def _add_sticky_note(self):
        self.scene.active_tool = "select"
        item = StickyNote(text="New Freeform Note", color_key="yellow")
        item.setPos(self.view.mapToScene(self.view.viewport().rect().center()))
        self.scene.addItem(item)

    def _add_handwriting_note(self):
        self.scene.active_tool = "select"
        item = HandwritingNote(text="Handwritten notebook section...")
        item.setPos(self.view.mapToScene(self.view.viewport().rect().center()))
        item.widget.video_requested.connect(self._on_generate_video_requested)
        item.widget.solve_requested.connect(self._on_stem_question_asked)
        self.scene.addItem(item)

    def _add_table(self):
        self.scene.active_tool = "select"
        item = TableItem()
        item.setPos(self.view.mapToScene(self.view.viewport().rect().center()))
        self.scene.addItem(item)

    def _add_group(self):
        self.scene.active_tool = "select"
        item = GroupSelection(title="Grouped Notes & Reviews")
        item.setPos(self.view.mapToScene(self.view.viewport().rect().center()))
        self.scene.addItem(item)

    def _on_insert_reference_table(self, data: dict):
        self.scene.active_tool = "select"
        item = TableItem(headers=data["headers"], rows=data["rows"])
        item.setPos(self.view.mapToScene(self.view.viewport().rect().center()))
        self.scene.addItem(item)
        self.reference_panel.hide()

    def _on_generate_video_requested(self, selected_text: str):
        job_id = request_video_generation(selected_text)
        center_pos = self.view.mapToScene(self.view.viewport().rect().center())
        v_item = VideoFloatItem(job_id=job_id, title=f"Manim: {selected_text[:18]}...", video_url_or_path="")
        v_item.setPos(center_pos.x() + 300, center_pos.y())
        self.scene.addItem(v_item)

    def _on_ink_written_detected(self, text: str, pos):
        clean_t = text.strip()
        if clean_t.endswith("?") or clean_t.endswith("=") or "=" in clean_t:
            self._on_stem_question_asked(text, target_pos=pos)
        else:
            bubble = AnswerBubble(title="Canvas Text", full_text=text, question="")
            bubble.setPos(pos)
            self.scene.addItem(bubble)

    def _on_stem_question_asked(self, question: str, target_pos=None):
        if target_pos:
            place_pos = target_pos
        else:
            place_pos = self.view.mapToScene(self.view.viewport().rect().center())

        loading_msg = "Kestrel AI Tutor is generating step-by-step solution..."
        bubble = AnswerBubble(title="Handwritten Solution", full_text=loading_msg, question=question)
        bubble.setPos(place_pos)
        self.scene.addItem(bubble)

        from ..backend.stem_solver import StemSolverWorker
        worker = StemSolverWorker(question, self)

        def _on_finished(q: str, res: dict):
            bubble.update_solution(q, res)

            plot_path = res.get("plot_path", "")
            if plot_path:
                graph_card = GraphCard(title=f"Graph: {q[:25]}", image_path=plot_path)
                graph_card.setPos(place_pos.x() + 450, place_pos.y())
                self.scene.addItem(graph_card)

            if worker in self._solver_workers:
                self._solver_workers.remove(worker)

        worker.finished.connect(_on_finished)
        self._solver_workers.append(worker)
        worker.start()

    def _populate_demo_canvas(self):
        pass
