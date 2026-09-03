"""
Main Application Window (Apple Freeform Shell Layout)
Frameless macOS Window Design with Traffic Light Controls, Sidebar (~260px), Top Toolbar, Infinite Canvas, Zoom HUD, Floating Tool Palette, AskBar, Notebooks Panel & PDF Split-Screen Study Mode
"""

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget,
    QListWidgetItem, QPushButton, QLineEdit, QLabel, QFrame,
    QSplitter, QStackedWidget, QFileDialog, QInputDialog, QMessageBox,
    QGraphicsDropShadowEffect, QMenu, QComboBox, QTabWidget, QTabBar, QApplication
)
from PyQt6.QtCore import Qt, QSize, QEvent, QPoint, QPointF, QRectF, QRect, QBuffer, QIODevice, QTimer, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont, QColor, QAction, QPixmap, QShortcut, QKeySequence, QPainter
import base64
import requests
import traceback
import re
import qtawesome as qta
from .kestrel_theme import get_global_qss, MONO_FONT, primary_button_qss, ghost_button_qss, menu_qss

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
from .widgets.pdf_viewer_widget import PdfViewerWidget
from .widgets.folder_tree_widget import FolderTreeWidget
from .views.notebooks_panel import NotebooksPanel
from .views.git_notes_panel import GitNotesPanel
from .views.shared_panel import SharedPanel
from .views.obsidian_graph_panel import ObsidianGraphPanel
from .views.home_view import HomeView
from .views.subjects_list import SubjectsListView
from .views.subject_detail_view import SubjectDetailView
from .views.constants_library_view import ConstantsLibraryView
from .views.placeholder_panel import PlaceholderPanel
from .views.settings_dialog import SettingsDialog
from .views.progress_dialog import ProgressDialog
from .floating_toolbar import FloatingToolbar
from .pen_properties_popup import PenPropertiesPopup
from .shapes_popup import ShapesPopup
from .eraser_popup import EraserPopup
from .theme_manager import ThemeManager
from .widgets.pomodoro_timer import PomodoroTimerWidget
from .widgets.latex_editor_widget import LatexEditorWidget
from .widgets.speedometer_progress_widget import SpeedometerProgressWidget
from .widgets.magic_orb_widget import MagicOrbWidget

from ..backend.math_engine.stem_solver import solve_stem_question
from ..backend.workspace.pdf_rag_manager import PdfRAGManager
from ..backend.video_generation.video_gen_client import request_video_generation
from ..storage.board_model import BoardModel
from ..storage.notebook_storage import NotebookStorage
from ..storage.downloads_manager import DownloadsManager
from ..backend.math_engine.latex_client import request_latex_generation, LatexPollWorker

# ── Autosave Configuration ─────────────────────────────────────────────────────
# Delay (ms) after the last scene change before autosave fires to disk.
# Keeps rapid edits (e.g. mid-drag) from spamming disk writes.
_AUTOSAVE_DELAY_MS = 1000


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

        self.lbl_title = QLabel("KESTREL", self)
        self.lbl_title.setStyleSheet(
            f"font-size: 11px; font-weight: 700; letter-spacing: 2px; "
            f"font-family: {MONO_FONT}; color: #888888; background: transparent;"
        )
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
        self.pdf_rag_mgr = PdfRAGManager()

        self.reference_panel = ReferencePanel()
        self.reference_panel.insert_data_requested.connect(self._on_insert_reference_table)
        self._solver_workers = []

        # ── Autosave State ─────────────────────────────────────────────────────
        # ID of the currently open notebook. None = demo/unsaved canvas.
        self._current_notebook_id: str | None = None
        # Single-shot debounce timer: fires _do_autosave after user pauses editing.
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._do_autosave)
        # Timer to clear the "Saved ✓" status label.
        self._save_status_clear_timer = QTimer(self)
        self._save_status_clear_timer.setSingleShot(True)
        self._save_status_clear_timer.timeout.connect(lambda: self._set_save_status(""))


        self._apply_global_styles()
        self._init_ui()
        self._setup_shortcuts()
        self._update_window_corners()

        # Connect ThemeManager
        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(lambda: self.floating_toolbar.action_triggered.emit("undo"))
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._on_toolbar_save)
        QShortcut(QKeySequence("V"), self).activated.connect(lambda: self.floating_toolbar.btn_select.click())
        QShortcut(QKeySequence("H"), self).activated.connect(lambda: self.floating_toolbar.btn_pan.click())
        QShortcut(QKeySequence("P"), self).activated.connect(lambda: self.floating_toolbar.btn_pen.click())
        QShortcut(QKeySequence("Alt+H"), self).activated.connect(lambda: self.floating_toolbar.btn_highlighter.click())
        QShortcut(QKeySequence("E"), self).activated.connect(lambda: self.floating_toolbar.btn_eraser.click())
        QShortcut(QKeySequence("S"), self).activated.connect(lambda: self.floating_toolbar.btn_shapes.click())
        QShortcut(QKeySequence("L"), self).activated.connect(lambda: self.floating_toolbar.btn_lasso.click())
        QShortcut(QKeySequence("T"), self).activated.connect(lambda: self.floating_toolbar.action_triggered.emit("text"))
        # PenEcho Magic Trigger
        QShortcut(QKeySequence("Ctrl+Space"), self).activated.connect(self._on_magic_orb_triggered)
        # Export
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self._convert_to_latex)

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

        # Main View Stack (Index 0: Canvas / Split View, Index 1: Notebooks View)
        self.main_stack = QStackedWidget(self.canvas_container)

        # Canvas & PDF Split-Screen Wrapper
        canvas_wrapper = QWidget(self.main_stack)
        cw_layout = QVBoxLayout(canvas_wrapper)
        cw_layout.setContentsMargins(0, 0, 0, 0)
        cw_layout.setSpacing(0)
        
        canvas_wrapper.installEventFilter(self)
        self._canvas_wrapper = canvas_wrapper

        self.canvas_tabs = QTabWidget(canvas_wrapper)
        self.canvas_tabs.setTabsClosable(True)
        self.canvas_tabs.setStyleSheet("""
            QTabWidget::pane { border: 0px; }
            QTabBar::tab { padding: 8px 16px; font-weight: 600; background: #f1f5f9; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px;}
            QTabBar::tab:selected { background: #ffffff; color: #7c3aed; border-bottom: 2px solid #7c3aed; }
        """)
        self.canvas_tabs.tabCloseRequested.connect(self._on_canvas_tab_closed)

        # PDF Viewer Widget (will be added to a tab when needed)
        self.pdf_viewer_widget = PdfViewerWidget(self.canvas_tabs)
        self.pdf_viewer_widget.hide() # Hidden initially so it doesn't float over the UI
        self.pdf_viewer_widget.close_requested.connect(self._close_pdf_split_screen)
        self.pdf_viewer_widget.reply_clicked.connect(self._on_pdf_reply_clicked)
        self.pdf_viewer_widget.latex_video_requested.connect(self._on_latex_video_requested)

        # LaTeX Editor & Live Preview Widget (added to tab when LaTeX is generated)
        self.latex_editor_widget = LatexEditorWidget(self.canvas_tabs)
        self.latex_editor_widget.hide()
        self.latex_editor_widget.close_requested.connect(self._close_latex_editor_tab)
        self.latex_editor_widget.pdf_compiled.connect(self._on_pdf_compiled)
        self.last_compiled_pdf_path = None

        # Scene and View
        self.scene = CanvasScene(self)
        self.scene.ink_written_detected.connect(self._on_ink_written_detected)
        self.scene.auto_ai_requested.connect(self._on_auto_ai_requested)
        # Connect scene_changed to the debounced autosave
        self.scene.scene_changed.connect(self._on_scene_changed)
        self.view = CanvasView(self.scene, self)
        self.view.zoom_changed.connect(self._on_zoom_changed)
        
        self.canvas_tabs.addTab(self.view, "✍️ Notebook Canvas")
        # Ensure the canvas tab doesn't show a close button
        self.canvas_tabs.tabBar().setTabButton(0, QTabBar.ButtonPosition.RightSide, None)

        cw_layout.addWidget(self.canvas_tabs)

        # Bottom Floating HUD Overlay (AskBar + Zoom HUD + Floating Tools)
        self.hud_overlay = self._create_hud_overlay()
        cw_layout.addWidget(self.hud_overlay)

        self.floating_toolbar = FloatingToolbar(canvas_wrapper)
        self.floating_toolbar.tool_changed.connect(self._on_floating_tool_changed)
        self.floating_toolbar.action_triggered.connect(self._on_floating_action)
        self.floating_toolbar.show()
        self.floating_toolbar.raise_()

        self.pen_popup = PenPropertiesPopup(canvas_wrapper)
        self.pen_popup.hide()
        self.pen_popup.color_changed.connect(self._on_pen_popup_color_changed)
        self.pen_popup.thickness_changed.connect(self._on_pen_popup_thickness_changed)

        self.shapes_popup = ShapesPopup(canvas_wrapper)
        self.shapes_popup.hide()
        self.shapes_popup.shape_selected.connect(self._on_shapes_popup_selected)

        self.eraser_popup = EraserPopup(canvas_wrapper)
        self.eraser_popup.hide()
        self.eraser_popup.size_changed.connect(self._on_eraser_popup_size_changed)

        # Pomodoro Floating Study Timer Overlay (Parented to central_card for top bar access on all screens)
        self.pomodoro_timer = PomodoroTimerWidget(self.central_card)
        self.pomodoro_timer.hide()
        self.pomodoro_timer.time_updated.connect(self._on_pomodoro_time_updated)

        self._canvas_wrapper = canvas_wrapper
        self.main_stack.addWidget(canvas_wrapper) # Index 0

        self.home_view = HomeView(self.main_stack)
        self.subjects_list_view = SubjectsListView(self.main_stack)
        self.subject_detail_view = SubjectDetailView(self.main_stack)
        self.constants_library_view = ConstantsLibraryView(self.main_stack)
        self.constants_library_view.go_back.connect(self._on_canvas_back_clicked)

        # Connect Navigation Signals
        def _open_blank():
            self.subject_detail_view.current_subject_id = None
            self.main_stack.setCurrentWidget(canvas_wrapper)
            self._set_sidebar_active_button("canvas")
            
        self.home_view.open_blank_notebook.connect(_open_blank)
        def _open_subjects_list():
            self.subjects_list_view.refresh_subjects()
            self.main_stack.setCurrentWidget(self.subjects_list_view)
            self._set_sidebar_active_button("notebooks")

        self.home_view.open_my_subjects.connect(_open_subjects_list)
        
        def _go_home():
            self.main_stack.setCurrentWidget(self.home_view)
            self._set_sidebar_active_button("home")

        self.subjects_list_view.go_back.connect(_go_home)
        self.subjects_list_view.open_subject_detail.connect(self._on_open_subject_detail)

        self.subject_detail_view.go_back.connect(_open_subjects_list)

        self.subject_detail_view.open_notebook.connect(self._on_load_notebook_requested)
        self.subject_detail_view.open_pdf_in_viewer.connect(self._on_subject_pdf_requested)

        self.main_stack.addWidget(self.home_view)
        self.main_stack.addWidget(self.subjects_list_view)
        self.main_stack.addWidget(self.subject_detail_view)
        
        # Make Home the default startup screen instead of the blank canvas
        self.main_stack.setCurrentWidget(self.home_view)
        # ------------------------------------


        # Notebooks View Panel
        self.notebooks_panel = NotebooksPanel(self.main_stack)
        self.notebooks_panel.open_notebook_requested.connect(self._on_load_notebook_requested)
        self.notebooks_panel.create_notebook_requested.connect(self._on_new_notebook_requested)
        self.notebooks_panel.git_vcs_requested.connect(self._on_notebook_git_requested)
        self.notebooks_panel.folder_navigated.connect(self._on_panel_folder_navigated)
        self.main_stack.addWidget(self.notebooks_panel) # Index 1
        
        # Placeholder Panel
        self.placeholder_panel = PlaceholderPanel(self.main_stack)
        self.main_stack.addWidget(self.placeholder_panel) # Index 2

        # Version History View Panel (formerly GitNotesPanel)
        self.git_notes_panel = GitNotesPanel(self.main_stack)
        self.git_notes_panel.version_restored.connect(self._on_version_history_restored)
        self.main_stack.addWidget(self.git_notes_panel) # Index 3

        # Shared Collaboration Hub View Panel
        self.shared_panel = SharedPanel(self.main_stack)
        self.main_stack.addWidget(self.shared_panel) # Index 4

        # Obsidian Knowledge Graph View Panel
        self.obsidian_graph_panel = ObsidianGraphPanel(self.main_stack)
        self.obsidian_graph_panel.open_notebook_requested.connect(self._on_load_notebook_requested)
        self.main_stack.addWidget(self.obsidian_graph_panel) # Index 5

        # Constants Library View Panel
        self.main_stack.addWidget(self.constants_library_view) # Index 6

        cc_layout.addWidget(self.main_stack)
        self.splitter.addWidget(self.canvas_container)

        self.splitter.setSizes([56, 1224])
        card_layout.addWidget(self.splitter)
        self.outer_layout.addWidget(self.central_card)

    def _on_open_subject_detail(self, subject_id: str):
        """Loads the requested subject from the DB and switches the view."""
        self.subject_detail_view.load_subject(subject_id)
        self.main_stack.setCurrentWidget(self.subject_detail_view)

    def _on_subject_pdf_requested(self, file_path: str):
        """Opens a PDF from the subject dashboard inside the whiteboard's PDF viewer tab."""
        print(f"[MainWindow] _on_subject_pdf_requested called with: {file_path}")
        self.main_stack.setCurrentWidget(self._canvas_wrapper)
        
        # Try the full RAG-powered load first
        try:
            self._load_pdf_into_split_screen(file_path)
        except Exception as e:
            print(f"[MainWindow] Full PDF load failed, falling back to viewer-only: {e}")
            # Fallback: just load the viewer widget without RAG
            try:
                success = self.pdf_viewer_widget.load_pdf(file_path)
                if success:
                    fname = os.path.basename(file_path)
                    self._show_or_update_tab(self.pdf_viewer_widget, f"📄 {fname}")
                else:
                    QMessageBox.warning(self, "PDF Error", f"Could not load PDF:\n{file_path}")
            except Exception as e2:
                QMessageBox.warning(self, "PDF Error", f"Could not load PDF:\n{e2}")

    def _on_canvas_back_clicked(self):
        """Routes the user back to the correct screen when leaving the canvas."""
        # If they were looking at a specific subject, take them back to that subject's dashboard
        if hasattr(self, 'subject_detail_view') and self.subject_detail_view.current_subject_id:
            self.main_stack.setCurrentWidget(self.subject_detail_view)
        # Otherwise, they opened a blank scratchpad, so take them Home
        elif hasattr(self, 'home_view'):
            self.main_stack.setCurrentWidget(self.home_view)
        else:
            # Fallback just in case
            self.main_stack.setCurrentIndex(0)


    def _apply_global_styles(self):
        c = ThemeManager.instance().get_colors()
        # Apply the centralized monochrome global QSS then override just the window bg
        base = get_global_qss(c)
        self.setStyleSheet(base + f"""
            QMainWindow {{
                background: transparent;
            }}
        """)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self._update_window_corners()

    def _update_window_corners(self):
        c = ThemeManager.instance().get_colors()
        if self.isMaximized():
            if hasattr(self, 'outer_layout'):
                self.outer_layout.setContentsMargins(0, 0, 0, 0)
            self.central_card.setStyleSheet(f"""
                QWidget#CentralCard {{
                    background-color: {c['bg_card']};
                    border-radius: 0px;
                    border: none;
                }}
                QWidget#MacTitleBar {{
                    background-color: {c['bg_titlebar']};
                    border-top-left-radius: 0px;
                    border-top-right-radius: 0px;
                    border-bottom: 1px solid {c['border_color']};
                }}
            """)
        else:
            if hasattr(self, 'outer_layout'):
                self.outer_layout.setContentsMargins(6, 6, 6, 6)
            self.central_card.setStyleSheet(f"""
                QWidget#CentralCard {{
                    background-color: {c['bg_card']};
                    border-radius: 4px;
                    border: 1px solid {c['border_color']};
                }}
                QWidget#MacTitleBar {{
                    background-color: {c['bg_titlebar']};
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    border-bottom: 1px solid {c['border_color']};
                }}
            """)

    def _on_theme_changed(self, theme_name: str):
        self._apply_global_styles()
        self._update_window_corners()
        if hasattr(self, 'btn_theme_toggle'):
            if theme_name == "dark":
                self.btn_theme_toggle.setText("LIGHT")
            else:
                self.btn_theme_toggle.setText("DARK")

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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'pomodoro_timer') and self.pomodoro_timer.isVisible():
            w = self.central_card.width()
            t_w = self.pomodoro_timer.width()
            self.pomodoro_timer.move(max(20, w - t_w - 24), 52)
            self.pomodoro_timer.raise_()

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
        c = ThemeManager.instance().get_colors()
        ic = c['sidebar_icon']  # inactive icon color
        sb = QWidget(self)
        sb.setFixedWidth(56)
        sb.setObjectName("KestrelSidebar")
        sb.setStyleSheet(f"""
            QWidget#KestrelSidebar {{
                background-color: {c['bg_sidebar']};
            }}
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 6px;
                padding: 6px;
            }}
            QPushButton:hover {{
                background-color: rgba(255,255,255,0.07);
            }}
        """)

        layout = QVBoxLayout(sb)
        layout.setContentsMargins(6, 14, 6, 14)
        layout.setSpacing(4)

        # Nav icon buttons — Remix Icons thin-stroke outline set matching Figma reference exactly
        nav_items = [
            ("ri.grid-line",       "Home",            "home"),
            ("ri.pencil-line",     "Canvas",          "canvas"),
            ("ri.bookmark-line",   "Notebooks",       "notebooks"),
            ("ri.git-branch-line", "Version Control", "vcs"),
            ("ri.share-line",      "Knowledge Graph", "graph"),
            ("ri.star-line",       "Favourites",      "favourites"),
            ("ri.download-line",   "Downloads",       "downloads"),
        ]

        self.sidebar_list = QListWidget()   # keep for _on_sidebar_changed compatibility
        self.sidebar_list.hide()
        self._sidebar_nav_buttons = []
        self._sidebar_btn_map = {}

        for idx, (icon_name, tooltip, nav_key) in enumerate(nav_items):
            btn = QPushButton(qta.icon(icon_name, color=ic), "", sb)
            btn.setFixedSize(40, 40)
            btn.setIconSize(QSize(18, 18))
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn._nav_tooltip = tooltip
            btn._nav_key = nav_key
            btn._icon_name = icon_name
            btn.clicked.connect(lambda checked, b=btn: self._on_sidebar_nav_clicked(b))
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)
            self._sidebar_nav_buttons.append(btn)
            self._sidebar_btn_map[nav_key] = btn

        # Folder Tree (hidden, kept for compatibility)
        self.folder_tree = FolderTreeWidget(self)
        self.folder_tree.folder_selected.connect(self._on_sidebar_folder_selected)
        self.folder_tree.tree_changed.connect(self._on_folder_tree_changed)
        self.folder_tree.setVisible(False)

        layout.addStretch()

        # Reference Database icon at the bottom
        btn_ref = QPushButton(qta.icon('ri.database-2-line', color=ic), "", sb)
        btn_ref.setFixedSize(40, 40)
        btn_ref.setIconSize(QSize(18, 18))
        btn_ref.setToolTip("Reference Database")
        btn_ref.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ref.clicked.connect(self._toggle_reference_panel)
        layout.addWidget(btn_ref, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Highlight the first button (Home) as active
        self._set_sidebar_active_button(self._sidebar_nav_buttons[0])

        return sb

    def _make_toolbar_btn(self, icon, label: str, parent, color=None, tooltip: str = ""):
        """Creates a clean, monochrome icon-only toolbar button."""
        c = ThemeManager.instance().get_colors()
        icon_color = color if color else c['text_secondary']
        btn = QPushButton(qta.icon(icon, color=icon_color), label, parent)
        btn.setIconSize(QSize(15, 15))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 3px;
                padding: 5px 8px;
                font-size: 12px;
                font-weight: 500;
                font-family: {MONO_FONT};
                color: {c['text_primary']};
            }}
            QPushButton:hover {{
                background-color: {c['panel_card_bg']};
            }}
            QPushButton:pressed {{
                background-color: {c['border_color']};
            }}
        """)
        if tooltip:
            btn.setToolTip(tooltip)
        return btn

    def _make_toolbar_separator(self, parent) -> QFrame:
        c = ThemeManager.instance().get_colors()
        sep = QFrame(parent)
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedHeight(18)
        sep.setStyleSheet(f"color: {c['border_color']}; margin: 0 2px;")
        return sep

    def _create_top_toolbar(self) -> QWidget:
        c = ThemeManager.instance().get_colors()
        tb = QWidget(self)
        tb.setFixedHeight(46)
        tb.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        tb.setStyleSheet(f"""
            QWidget {{
                background-color: {c['bg_toolbar']};
                border-bottom: 1px solid {c['border_color']};
            }}
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 2px;
                padding: 5px 9px;
                font-size: 12px;
                font-weight: 500;
                font-family: {MONO_FONT};
                color: {c['text_primary']};
            }}
            QPushButton:hover {{
                background-color: {c['panel_card_bg']};
            }}
            QPushButton:pressed {{
                background-color: {c['border_color']};
            }}
            QLineEdit {{
                font-size: 13px;
                font-weight: 600;
                border: none;
                background: transparent;
                font-family: {MONO_FONT};
                color: {c['text_primary']};
            }}
            QComboBox {{
                border: 1px solid {c['border_color']};
                background: {c['input_bg']};
                font-size: 12px;
                font-weight: 500;
                font-family: {MONO_FONT};
                color: {c['text_primary']};
                padding: 3px 6px;
                border-radius: 2px;
            }}
            QComboBox::drop-down {{ border: none; width: 14px; }}
        """)

        layout = QHBoxLayout(tb)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(4)

        # Back + Title
        btn_back = self._make_toolbar_btn('ri.arrow-left-line', "", tb, None, "Back to Menu")
        btn_back.clicked.connect(self._on_canvas_back_clicked)
        layout.addWidget(btn_back)

        self.title_edit = QLineEdit(self.current_board.title, tb)
        self.title_edit.setFixedWidth(180)
        self.title_edit.editingFinished.connect(self._on_title_changed)
        layout.addWidget(self.title_edit)

        # Insert Image
        btn_img = self._make_toolbar_btn('ri.image-line', "Image", tb, None, "Insert Image")
        btn_img.clicked.connect(self._on_insert_image)
        layout.addWidget(btn_img)

        # Grid Toggle
        self.btn_grid_mode = self._make_toolbar_btn('ri.grid-line', "Blank", tb, None, "Toggle Grid")
        self.btn_grid_mode.clicked.connect(self._toggle_grid_mode)
        layout.addWidget(self.btn_grid_mode)

        # LaTeX Export Controls
        self.latex_combo = QComboBox(tb)
        self.latex_combo.addItems(["Homework", "Assignment", "Research Paper", "Lecture Slides"])
        self.latex_combo.setFixedWidth(110)
        
        self.classroom_action_combo = QComboBox(tb)
        self.classroom_action_combo.addItems(["Solve Question", "Transcribe Notes"])
        self.classroom_action_combo.setFixedWidth(120)

        layout.addWidget(self.latex_combo)
        layout.addWidget(self.classroom_action_combo)

        btn_latex = self._make_toolbar_btn('ri.file-upload-line', "LaTeX", tb, None, "Convert to LaTeX")
        btn_latex.clicked.connect(self._convert_to_latex)
        layout.addWidget(btn_latex)

        layout.addWidget(self._make_toolbar_separator(tb))

        # Study/Classroom Mode
        self.btn_mode_toggle = self._make_toolbar_btn('ri.book-open-line', "Study", tb, None, "Toggle Mode")
        self.btn_mode_toggle.clicked.connect(self._toggle_tutor_mode)
        layout.addWidget(self.btn_mode_toggle)

        # Theme Toggle (Light / Dark Mode) — monochrome bordered pill
        c = ThemeManager.instance().get_colors()
        theme_lbl = "LIGHT" if ThemeManager.instance().is_dark() else "DARK"
        self.btn_theme_toggle = self._make_toolbar_btn(
            'ri.sun-line' if ThemeManager.instance().is_dark() else 'ri.moon-line',
            theme_lbl, tb, None, "Toggle Light/Dark Theme"
        )
        self.btn_theme_toggle.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
                font-family: {MONO_FONT};
                letter-spacing: 0.5px;
                color: {c['text_primary']};
            }}
            QPushButton:hover {{
                background-color: {c['panel_card_bg']};
            }}
        """)
        self.btn_theme_toggle.clicked.connect(self._toggle_theme)
        layout.addWidget(self.btn_theme_toggle)

        # Pomodoro Study Timer Toggle Button
        self.btn_pomodoro_toggle = self._make_toolbar_btn(
            'ri.timer-line', "", tb, None, "Toggle Pomodoro Study Timer"
        )
        self.btn_pomodoro_toggle.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                padding: 4px 8px;
                color: {c['text_primary']};
            }}
            QPushButton:hover {{
                background-color: {c['panel_card_bg']};
            }}
        """)
        self.btn_pomodoro_toggle.clicked.connect(self._toggle_pomodoro_timer)
        layout.addWidget(self.btn_pomodoro_toggle)

        layout.addStretch()

        # ── Save Button + Status Indicator ───────────────────────────────────
        c = ThemeManager.instance().get_colors()
        self.lbl_save_status = QLabel("", tb)
        self.lbl_save_status.setStyleSheet(
            f"font-size: 10px; color: {c['text_secondary']}; font-weight: 600; "
            f"font-family: {MONO_FONT}; letter-spacing: 0.5px; padding: 2px 6px; "
            f"border: 1px solid {c['border_color']}; border-radius: 2px;"
        )
        self.lbl_save_status.setVisible(False)
        layout.addWidget(self.lbl_save_status)

        self.btn_save = self._make_toolbar_btn('ri.save-line', "Save", tb, None, "Save Notebook (Ctrl+S)")
        self.btn_save.setStyleSheet(primary_button_qss(c))
        # Non-Popup Speedometer Live Status Widget
        self.speedometer_widget = SpeedometerProgressWidget(tb)
        layout.addWidget(self.speedometer_widget)

        # In-App View PDF Button (Appears on top right panel after PDF is exported)
        self.btn_view_pdf = self._make_toolbar_btn('ri.file-pdf-line', "View PDF", tb, None, "View Compiled PDF In-App")
        self.btn_view_pdf.clicked.connect(self._open_in_app_pdf_viewer)
        self.btn_view_pdf.setVisible(False)
        layout.addWidget(self.btn_view_pdf)

        layout.addWidget(self.btn_save)

        layout.addWidget(self._make_toolbar_separator(tb))

        # Search / Share / Settings
        btn_search = self._make_toolbar_btn('ri.search-line', "", tb, None, "Search")
        btn_share = self._make_toolbar_btn('ri.share-line', "", tb, None, "Share")
        layout.addWidget(btn_search)
        layout.addWidget(btn_share)

        # Settings
        btn_settings = self._make_toolbar_btn('ri.settings-3-line', "", tb, None, "Settings")
        btn_settings.clicked.connect(self._open_settings)
        layout.addWidget(btn_settings)

        return tb

    def _toggle_tutor_mode(self):
        curr = self.ask_bar.get_mode() if hasattr(self, 'ask_bar') else "study"
        new_mode = "classroom" if curr == "study" else "study"
        if hasattr(self, 'ask_bar'):
            self.ask_bar.set_mode(new_mode)
        self._update_mode_button_text(new_mode)

    def _update_mode_button_text(self, mode: str):
        c = ThemeManager.instance().get_colors()
        if hasattr(self, 'btn_mode_toggle'):
            if mode == "classroom":
                self.btn_mode_toggle.setText("Classroom")
                self.btn_mode_toggle.setIcon(qta.icon('ri.slideshow-line', color=c['text_secondary']))
            else:
                self.btn_mode_toggle.setText("Study")
                self.btn_mode_toggle.setIcon(qta.icon('ri.book-open-line', color=c['text_secondary']))

    def _create_hud_overlay(self) -> QWidget:
        c = ThemeManager.instance().get_colors()
        hud = QWidget(self)
        hud.setFixedHeight(64)
        hud.setStyleSheet("background: transparent;")

        # Single floating bar that holds everything
        outer = QHBoxLayout(hud)
        outer.setContentsMargins(24, 0, 24, 10)

        pill = QWidget(hud)
        pill.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        pill.setStyleSheet(f"""
            QWidget {{
                background-color: {c['bg_toolbar']};
                border: 1px solid {c['border_color']};
                border-radius: 8px;
            }}
            QPushButton {{
                border: none;
                background: transparent;
                border-radius: 2px;
                padding: 5px 8px;
                font-size: 12px;
                font-weight: 600;
                font-family: {MONO_FONT};
                color: {c['text_primary']};
            }}
            QPushButton:hover {{ background-color: {c['panel_card_bg']}; }}
            QLabel {{
                font-size: 12px;
                font-weight: 600;
                font-family: {MONO_FONT};
                color: {c['text_primary']};
                min-width: 36px;
            }}
        """)

        pl = QHBoxLayout(pill)
        pl.setContentsMargins(10, 4, 10, 4)
        pl.setSpacing(2)

        # Zoom controls
        btn_zoom_out = QPushButton("–", pill)
        btn_zoom_out.setFixedWidth(26)
        btn_zoom_out.clicked.connect(lambda: self.view.zoom_by(0.8))
        self.lbl_zoom = QLabel("100%", pill)
        self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_zoom_in = QPushButton("+", pill)
        btn_zoom_in.setFixedWidth(26)
        btn_zoom_in.clicked.connect(lambda: self.view.zoom_by(1.2))

        pl.addWidget(btn_zoom_out)
        pl.addWidget(self.lbl_zoom)
        pl.addWidget(btn_zoom_in)

        # Separator
        sep1 = QFrame(pill)
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setFixedHeight(18)
        sep1.setStyleSheet(f"color: {c['border_color']};")
        pl.addSpacing(4)
        pl.addWidget(sep1)
        pl.addSpacing(4)

        # AskBar
        self.ask_bar = AskBar(pill)
        self.ask_bar.question_submitted.connect(self._on_stem_question_asked)
        self.ask_bar.mode_changed.connect(self._update_mode_button_text)
        self.ask_bar.question_with_context_submitted.connect(self._on_question_with_context_asked)
        self.ask_bar.pdf_requested.connect(self._open_pdf_dialog)
        pl.addWidget(self.ask_bar, stretch=1)

        # ── PenEcho Magic Orb HUD ──
        sep2 = QFrame(pill)
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setFixedHeight(18)
        sep2.setStyleSheet(f"color: {c['border_color']};")
        pl.addSpacing(4)
        pl.addWidget(sep2)
        pl.addSpacing(4)

        self.magic_orb = MagicOrbWidget(pill)
        self.magic_orb.trigger_ai_requested.connect(self._on_magic_orb_triggered)
        self.magic_orb.auto_ai_toggled.connect(self._on_auto_ai_toggled)
        self.magic_orb.delay_changed.connect(self._on_auto_ai_delay_changed)
        pl.addWidget(self.magic_orb)

        outer.addWidget(pill)
        return hud

    def _on_auto_ai_requested(self, query: str, target_pos: QPointF):
        from .penecho_integration.ai_canvas_bridge import AICanvasWorker, create_draft_from_payload
        self.magic_orb.set_state("thinking", "Analyzing...")

        # Collision-free positioning
        clean_pos = self._find_non_overlapping_pos(target_pos, width=400.0, height=200.0)

        worker = AICanvasWorker(query_text=query, target_pos=clean_pos, parent=self)

        def _on_finished(payload_dict, pos, msg):
            draft_item = create_draft_from_payload(payload_dict)
            draft_item.setPos(pos)
            if draft_item.scene() is None:
                self.scene.addItem(draft_item)
            self.magic_orb.set_state("draft", msg)
            if worker in self._solver_workers:
                self._solver_workers.remove(worker)

        def _on_error(err):
            self.magic_orb.set_state("error")
            if worker in self._solver_workers:
                self._solver_workers.remove(worker)

        worker.finished.connect(_on_finished)
        worker.error.connect(_on_error)
        self._solver_workers.append(worker)
        worker.start()

    def _on_magic_orb_triggered(self):
        self.scene.trigger_ai_on_dirty_ink()

    def _on_auto_ai_toggled(self, enabled: bool):
        self.scene.auto_ai_enabled = enabled

    def _on_auto_ai_delay_changed(self, delay: float):
        self.scene.auto_ai_delay_sec = delay

    def _on_pen_popup_color_changed(self, color_hex: str):
        if self.scene.active_tool == "highlighter":
            self.scene.set_highlighter_color(color_hex)
        else:
            self.scene.set_pen_color(color_hex)
            
    def _on_pen_popup_thickness_changed(self, thickness: int):
        self.scene.pen_width = float(thickness)

    def _set_tool(self, tool_name: str):
        self.scene.active_tool = tool_name

    def _on_floating_tool_changed(self, tool: str):
        was_active = (self.scene.active_tool == tool)
        self._set_tool(tool)
        
        if tool in ["pen", "highlighter", "shapes", "eraser"]:
            from PyQt6.QtCore import QPoint
            if tool in ["pen", "highlighter"]:
                btn = self.floating_toolbar.btn_highlighter if tool == "highlighter" else self.floating_toolbar.btn_pen
                popup = self.pen_popup
            elif tool == "shapes":
                btn = self.floating_toolbar.btn_shapes
                popup = self.shapes_popup
            elif tool == "eraser":
                btn = self.floating_toolbar.btn_eraser
                popup = self.eraser_popup

            if tool == "highlighter":
                self.pen_popup.set_active_color(self.scene.highlighter_color)
                self.pen_popup.set_active_thickness(int(self.scene.pen_width))
            elif tool == "pen":
                self.pen_popup.set_active_color(self.scene.pen_color)
                self.pen_popup.set_active_thickness(int(self.scene.pen_width))
            
            if was_active and popup.isVisible():
                popup.hide()
            else:
                self.pen_popup.hide()
                self.shapes_popup.hide()
                self.eraser_popup.hide()

                pos = btn.mapTo(self._canvas_wrapper, QPoint(0, 0))
                popup.adjustSize()
                px = pos.x() - (popup.width() // 2) + (btn.width() // 2)
                py = pos.y() - popup.height() - 10
                
                popup.move(px, py)
                popup.show()
                popup.raise_()
        else:
            self.pen_popup.hide()
            self.shapes_popup.hide()
            self.eraser_popup.hide()

    def _on_shapes_popup_selected(self, shape_id: str):
        self.scene.active_shape_type = shape_id

    def _on_eraser_popup_size_changed(self, size: int):
        self.scene.eraser_size = size

    def _on_floating_action(self, action: str):
        """Called when an action button is clicked in the floating toolbar."""
        if action == "undo":
            pass  # TODO: Undo last action
        elif action == "sticky":
            self._add_sticky_note()
        elif action == "note":
            self._add_handwriting_note()
        elif action == "text":
            self._add_text_box()
        elif action == "table":
            self._add_table()
        elif action == "latex":
            self._convert_to_latex()
        elif action == "more":
            self._show_overflow_menu()
            
    def _show_overflow_menu(self):
        menu = QMenu(self)
        
        # Add actions to menu
        act_save = QAction("Save Board", self)
        act_save.triggered.connect(self._on_toolbar_save)
        menu.addAction(act_save)
        
        act_paste = QAction("Paste (Ctrl+V)", self)
        act_paste.triggered.connect(self._on_toolbar_paste)
        menu.addAction(act_paste)
        
        menu.addSeparator()
        
        act_image = QAction("Insert Image", self)
        act_image.triggered.connect(self._on_insert_image)
        menu.addAction(act_image)
        
        act_sticky = QAction("Sticky Note", self)
        act_sticky.triggered.connect(self._add_sticky_note)
        menu.addAction(act_sticky)
        
        act_table = QAction("Table", self)
        act_table.triggered.connect(self._add_table)
        menu.addAction(act_table)
        
        menu.addSeparator()

        # ── PenEcho Extended Canvas Actions ──
        act_anim = QAction("🎬 Insert Animated Scene (PenEcho)", self)
        act_anim.triggered.connect(self._add_penecho_animation)
        menu.addAction(act_anim)

        act_mixed = QAction("📐 Insert LaTeX / Markdown Card (PenEcho)", self)
        act_mixed.triggered.connect(self._add_penecho_mixed_text)
        menu.addAction(act_mixed)

        act_curve = QAction("🌀 Insert Mathematical Curve (PenEcho)", self)
        act_curve.triggered.connect(self._add_penecho_summon_curve)
        menu.addAction(act_curve)

        act_draw = QAction("🎨 Insert Multi-Primitive Drawing Demo (PenEcho)", self)
        act_draw.triggered.connect(self._add_penecho_drawing_demo)
        menu.addAction(act_draw)

        act_export_png = QAction("🖼️ Export Cropped Canvas PNG", self)
        act_export_png.triggered.connect(self._export_canvas_image)
        menu.addAction(act_export_png)

        menu.addSeparator()
        
        act_grid = QAction("Toggle Grid/Blank", self)
        act_grid.triggered.connect(self._toggle_grid_mode)
        menu.addAction(act_grid)
        
        act_mode = QAction("Toggle Study/Classroom Mode", self)
        act_mode.triggered.connect(self._toggle_tutor_mode)
        menu.addAction(act_mode)
        
        # Show menu above the "more" button
        btn = self.floating_toolbar.btn_more
        pos = btn.mapToGlobal(btn.rect().topLeft())
        pos.setY(pos.y() - menu.sizeHint().height() - 10)
        menu.exec(pos)

    def _add_penecho_animation(self):
        from .penecho_integration import PenechoAnimationItem
        center_pos = self.view.mapToScene(self.view.viewport().rect().center())
        demo_scene = {
            "title": "Planetary Orbit & Wave",
            "w": 380,
            "h": 280,
            "durationMs": 5000,
            "objects": [
                {"id": "sun", "type": "circle", "cx": 190, "cy": 140, "r": 28, "fill": "#f59e0b", "stroke": "#d97706", "lineWidth": 3},
                {"id": "planet", "type": "circle", "cx": 190, "cy": 140, "r": 14, "fill": "#3b82f6", "stroke": "#1d4ed8", "lineWidth": 2},
                {"id": "moon", "type": "circle", "cx": 190, "cy": 140, "r": 6, "fill": "#10b981", "stroke": "#047857", "lineWidth": 1.5},
                {"id": "label", "type": "text", "x": 14, "y": 26, "text": "Gravity Orbit Demo", "fontSize": 14, "fill": "#94a3b8"}
            ],
            "motions": [
                {"type": "spin", "target": "sun", "periodMs": 6000, "clockwise": True},
                {"type": "orbit", "target": "planet", "center": [190, 140], "rx": 110, "ry": 60, "periodMs": 4000, "clockwise": True},
                {"type": "orbit", "target": "moon", "center": "planet", "rx": 28, "ry": 28, "periodMs": 1200, "clockwise": True},
                {"type": "pulse", "target": "sun", "from": 0.9, "to": 1.1, "periodMs": 2500}
            ]
        }
        item = PenechoAnimationItem(demo_scene)
        item.setPos(center_pos)
        self.scene.addItem(item)
        self.scene.scene_changed.emit()

    def _add_penecho_mixed_text(self):
        from .penecho_integration import PenechoMixedTextItem
        center_pos = self.view.mapToScene(self.view.viewport().rect().center())
        text = "### Quantum Harmonic Oscillator\nEnergy levels are quantized:\n$$E_n = \\hbar \\omega \\left(n + \\frac{1}{2}\\right)$$\nwhere $n = 0, 1, 2, \\dots$ and $\\omega = \\sqrt{\\frac{k}{m}}$."
        item = PenechoMixedTextItem(raw_text=text, font_size=15, width=340.0)
        item.setPos(center_pos)
        self.scene.addItem(item)
        self.scene.scene_changed.emit()

    def _add_penecho_summon_curve(self):
        from .penecho_integration import PenechoSummonItem
        center_pos = self.view.mapToScene(self.view.viewport().rect().center())
        item = PenechoSummonItem(curve_type="lemniscate", size=240.0)
        item.setPos(center_pos)
        self.scene.addItem(item)
        self.scene.scene_changed.emit()

    def _add_penecho_drawing_demo(self):
        from .penecho_integration import PenechoDrawItem
        center_pos = self.view.mapToScene(self.view.viewport().rect().center())
        demo_cmd = {
            "origin": [0, 0],
            "types": ["rect", "smooth", "arc", "circle", "line"],
            "items": [
                [0, 0, 180, 120],
                [20, 60, 60, 20, 120, 100, 160, 60],
                [90, 60, 40, 40, 0, 180],
                [90, 60, 12],
                [20, 140, 160, 140]
            ],
            "width": 3.0,
            "tension": 50.0,
            "color": "#2563eb",
            "fill_color": "rgba(59, 130, 246, 0.15)",
            "closed": [0],
            "fill": [0],
            "arrows": [4]
        }
        item = PenechoDrawItem(demo_cmd)
        item.setPos(center_pos)
        self.scene.addItem(item)
        self.scene.scene_changed.emit()

    def _export_canvas_image(self):
        from PyQt6.QtWidgets import QFileDialog
        from .penecho_integration import export_canvas_to_image
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Cropped Canvas Image", "canvas_export.png", "Images (*.png *.jpg)")
        if file_path:
            success = export_canvas_to_image(self.scene, file_path, margin_px=40.0, scale_factor=2.0)
            if success:
                self._set_save_status("Exported PNG ✓")
            else:
                QMessageBox.warning(self, "Export Failed", "Could not export canvas image.")

    def _on_insert_image(self):
        from .items.image_item import ImageItem
        file_path, _ = QFileDialog.getOpenFileName(self, "Insert Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if file_path:
            self.scene.active_tool = "select"
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                item = ImageItem(pixmap)
                # Center it
                item.setPos(self.view.mapToScene(self.view.viewport().rect().center()))
                # Images should stay under ink
                item.setZValue(5)
                self.scene.addItem(item)
                self.scene.scene_changed.emit()

    def _add_text_box(self):
        from .items.text_box_item import TextBoxItem
        self.scene.active_tool = "select"
        item = TextBoxItem(text="Type here...")
        item.setPos(self.view.mapToScene(self.view.viewport().rect().center()))
        self.scene.addItem(item)
        self.scene.scene_changed.emit()

    def eventFilter(self, obj, event):
        if hasattr(self, '_canvas_wrapper') and obj == self._canvas_wrapper and event.type() == QEvent.Type.Resize:
            if hasattr(self, 'floating_toolbar'):
                tb = self.floating_toolbar
                if not tb.user_moved:
                    x = (obj.width() - tb.sizeHint().width()) // 2
                    y = obj.height() - tb.height() - 90  # 90px to clear HUD
                    tb.setGeometry(x, y, tb.sizeHint().width(), tb.height())
        return super().eventFilter(obj, event)

    def _open_pdf_dialog(self):
        """
        Opens QFileDialog to select a PDF file and loads it into Split-Screen RAG mode.
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF for Study Mode", "", "PDF Files (*.pdf);;All Files (*)"
        )
        if file_path:
            self._load_pdf_into_split_screen(file_path)

    def _show_or_update_tab(self, widget, title: str):
        """Adds widget as a tab if not present, or updates its title if already present."""
        idx = self.canvas_tabs.indexOf(widget)
        if idx == -1:
            self.canvas_tabs.addTab(widget, title)
        else:
            self.canvas_tabs.setTabText(idx, title)
        self.canvas_tabs.setCurrentWidget(widget)

    def _load_pdf_into_split_screen(self, file_path: str):
        try:
            success_rag = self.pdf_rag_mgr.load_pdf(file_path)
            success_view = self.pdf_viewer_widget.load_pdf(file_path)

            if success_view:
                fname = os.path.basename(file_path)
                self._show_or_update_tab(self.pdf_viewer_widget, f"📄 {fname}")
                self.ask_bar.set_pdf_mode(True, filename=fname)

                if success_rag:
                    summary = self.pdf_rag_mgr.generate_grounded_summary()
                    center_pos = self.view.mapToScene(self.view.viewport().rect().center())
                    bubble = AnswerBubble(
                        title=f"PDF Summary: {fname[:20]}",
                        full_text=summary,
                        question=f"Summarize document: {fname}"
                    )
                    bubble.setPos(center_pos)
                    self.scene.addItem(bubble)
                else:
                    print(f"[MainWindow] RAG failed for {fname}, but viewer loaded.")
            else:
                QMessageBox.warning(self, "PDF Error", "Could not load the selected PDF document.")
        except Exception as err:
            QMessageBox.warning(self, "PDF Exception", f"Error opening PDF:\n{err}")

    def _on_pdf_reply_clicked(self, selected_text: str, page_num: int, surrounding_context: str):
        """
        Triggered when user taps 'Reply ↰' floating pill button on highlighted PDF passage.
        Links selection snippet & surrounding paragraph context to the AskBar and focuses input field.
        """
        self.ask_bar.set_selection_context(selected_text, page_num, surrounding_context)

    def _on_question_with_context_asked(self, user_question: str, selected_text: str, page_num: int, surrounding_context: str):
        """
        Triggered when user submits a doubt or question in the AskBar with a PDF text selection context attached.
        Generates grounded RAG solution & answer bubble onto the canvas paper.
        """
        if not self.pdf_rag_mgr.is_loaded():
            return

        ai_response = self.pdf_rag_mgr.generate_grounded_answer(
            query=user_question,
            selected_text=selected_text,
            page_num=page_num,
            surrounding_context=surrounding_context
        )

        passage_preview = selected_text[:120].replace('\n', ' ')
        full_text = (
            f"📖 Highlighted Passage [Page {page_num}]:\n\"{passage_preview}...\"\n\n"
            f"💡 Answer & Solution:\n{ai_response}"
        )

        center_pos = self.view.mapToScene(self.view.viewport().rect().center())
        bubble = AnswerBubble(
            title=f"Doubt: {user_question[:25]}",
            full_text=full_text,
            question=user_question
        )
        bubble.setPos(center_pos)
        self.scene.addItem(bubble)

    def _toggle_sidebar(self):
        if self.sidebar.isVisible():
            self.sidebar.hide()
        else:
            self.sidebar.show()

    def _open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def _toggle_reference_panel(self):
        if self.reference_panel.isVisible():
            self.reference_panel.hide()
        else:
            self.reference_panel.show_panel(self)

    def _sync_grid_btn_ui(self, mode: str):
        c = ThemeManager.instance().get_colors()
        col = c['text_secondary']
        if mode == "ruled":
            self.btn_grid_mode.setText("Ruled")
            self.btn_grid_mode.setIcon(qta.icon('ri.menu-line', color=col))
        elif mode == "dotted":
            self.btn_grid_mode.setText("Dotted")
            self.btn_grid_mode.setIcon(qta.icon('ri.more-line', color=col))
        elif mode == "math_ruled":
            self.btn_grid_mode.setText("Math Grid")
            self.btn_grid_mode.setIcon(qta.icon('ri.grid-line', color=col))
        else:
            self.btn_grid_mode.setText("Blank")
            self.btn_grid_mode.setIcon(qta.icon('ri.checkbox-blank-line', color=col))

    def _toggle_grid_mode(self):
        if self.scene.background_mode == "blank":
            self.scene.set_background_mode("ruled")
        elif self.scene.background_mode == "ruled":
            self.scene.set_background_mode("dotted")
        elif self.scene.background_mode == "dotted":
            self.scene.set_background_mode("math_ruled")
        else:
            self.scene.set_background_mode("blank")
        self._sync_grid_btn_ui(self.scene.background_mode)

    def _on_zoom_changed(self, zoom_factor: float):
        self.lbl_zoom.setText(f"{int(zoom_factor * 100)}%")

    def _on_title_changed(self):
        self.current_board.title = self.title_edit.text()

    def _on_sidebar_changed(self, row: int):
        if row == 0:
            self.folder_tree.setVisible(False)
            self.main_stack.setCurrentIndex(0)
        elif row == 1:  # "🗂 Notebooks"
            self._refresh_folder_tree()
            self.folder_tree.setVisible(True)
            self.notebooks_panel.refresh()
            self.main_stack.setCurrentIndex(1)
        elif row == 2:  # "⎇ Git Notes VCS"
            self.git_notes_panel.refresh_all()
            self.main_stack.setCurrentIndex(2)
        elif row == 3:  # "❖ Knowledge Graph"
            self.obsidian_graph_panel.load_graph()
            self.main_stack.setCurrentIndex(4)
        elif row == 4:  # "☌ Shared"
            self.shared_panel.refresh_all()
            self.main_stack.setCurrentIndex(3)
        else:
            self.folder_tree.setVisible(False)
            item_text = self.sidebar_list.item(row).text() if self.sidebar_list.count() > row else ""
            clean_title = re.sub(r'^[^\w\s]+', '', item_text).split('(')[0].strip() if item_text else "Section"
            self.placeholder_panel.set_title(clean_title)
            self.main_stack.setCurrentIndex(2)

    def _set_sidebar_active_button(self, active_btn):
        """Highlights the active nav button with solid white fill & black icon (Figma ref)."""
        if isinstance(active_btn, str):
            active_btn = getattr(self, '_sidebar_btn_map', {}).get(active_btn)

        c = ThemeManager.instance().get_colors()
        for btn in getattr(self, '_sidebar_nav_buttons', []):
            icon_name = getattr(btn, '_icon_name', 'ri.grid-line')
            btn.setIcon(qta.icon(icon_name, color=c['sidebar_icon']))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    border-radius: 2px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.08);
                }
            """)
        if active_btn:
            active_icon_name = getattr(active_btn, '_icon_name', 'ri.grid-line')
            active_btn.setIcon(qta.icon(active_icon_name, color=c['sidebar_active_icon']))
            active_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c['sidebar_active_bg']};
                    border-radius: 2px;
                    border: none;
                }}
            """)

    def _on_sidebar_nav_clicked(self, btn):
        """Handles icon rail sidebar navigation clicks."""
        self._set_sidebar_active_button(btn)
        key = getattr(btn, '_nav_key', getattr(btn, '_nav_tooltip', ''))
        if key in ("home", "Home", "Boards"):
            self.folder_tree.setVisible(False)
            self.main_stack.setCurrentWidget(self.home_view)
        elif key in ("canvas", "Canvas"):
            self.folder_tree.setVisible(False)
            self.main_stack.setCurrentWidget(self._canvas_wrapper)
        elif key in ("notebooks", "Notebooks"):
            self.folder_tree.setVisible(False)
            self.subjects_list_view.refresh_subjects()
            self.main_stack.setCurrentWidget(self.subjects_list_view)
        elif key in ("vcs", "Version Control", "Git VCS", "Version History"):
            self.folder_tree.setVisible(False)
            self.git_notes_panel.refresh_all()
            self.main_stack.setCurrentWidget(self.git_notes_panel)
        elif key in ("graph", "Knowledge Graph"):
            self.folder_tree.setVisible(False)
            self.obsidian_graph_panel.load_graph()
            self.main_stack.setCurrentWidget(self.obsidian_graph_panel)
        elif key in ("favourites", "Favourites"):
            self.folder_tree.setVisible(False)
            self.placeholder_panel.set_title("Favourites")
            self.main_stack.setCurrentWidget(self.placeholder_panel)
        elif key in ("downloads", "Downloads"):
            self.folder_tree.setVisible(False)
            self.placeholder_panel.set_title("Downloads")
            self.main_stack.setCurrentWidget(self.placeholder_panel)
        else:
            self.folder_tree.setVisible(False)
            self.placeholder_panel.set_title(str(key))
            self.main_stack.setCurrentWidget(self.placeholder_panel)

    def _refresh_folder_tree(self):
        from ..storage.notebook_storage import NotebookStorage
        folders = NotebookStorage.get_folder_tree()
        selected_id = self.notebooks_panel._current_folder_id
        self.folder_tree.refresh(folders, selected_id=selected_id)

    def _on_sidebar_folder_selected(self, folder_id: str):
        """User clicked a folder in the sidebar tree — navigate notebooks panel."""
        self.notebooks_panel.navigate_to_folder(folder_id or None)

    def _on_folder_tree_changed(self):
        """Folder tree had a structural change (create/rename/delete) — refresh both."""
        self._refresh_folder_tree()
        self.notebooks_panel.refresh()

    def _on_panel_folder_navigated(self, folder_id):
        """Panel navigated via breadcrumb or folder card — sync sidebar tree highlight."""
        self._refresh_folder_tree()
        self.folder_tree.select_folder(folder_id or "")

    def _on_toolbar_save(self):
        """Manual Save: immediately serializes the live scene and writes to disk.
        No dialog — saves with the current notebook name. Shows brief status feedback.
        """
        if not self._current_notebook_id:
            # No notebook open yet: prompt for name and create one
            current_name = self.current_board.title or "Untitled Notebook"
            name, ok = QInputDialog.getText(self, "Save New Notebook", "Enter Notebook Name:", text=current_name)
            if not (ok and name.strip()):
                return
            try:
                meta = NotebookStorage.create_notebook(name.strip())
                self._current_notebook_id = meta["id"]
                self.current_board.board_id = meta["id"]
                self.current_board.title = meta["name"]
                self.title_edit.setText(meta["name"])
            except Exception as err:
                traceback.print_exc()
                QMessageBox.warning(self, "Save Failed", f"Could not create notebook:\n{err}")
                return

        self._do_autosave(manual=True)

    # ── Autosave Helpers ──────────────────────────────────────────────────────

    def _on_scene_changed(self):
        """Called whenever the canvas is mutated. Resets the debounce timer.
        Only fires a disk write when the user pauses for _AUTOSAVE_DELAY_MS ms.
        """
        if self._current_notebook_id:
            self._autosave_timer.start(_AUTOSAVE_DELAY_MS)

    def _do_autosave(self, manual: bool = False):
        """Performs the actual save: serializes the LIVE scene and writes to disk.
        Always saves to the SAME notebook_id — never creates a duplicate.
        """
        if not self._current_notebook_id:
            return
        try:
            self._set_save_status("Saving...")
            name = self.current_board.title or "Untitled Notebook"
            items_data = self.scene.to_dict_list()
            NotebookStorage.save_notebook(self._current_notebook_id, name, items_data)
            if hasattr(self, 'notebooks_panel'):
                self.notebooks_panel.refresh()
            self._set_save_status("Saved ✓", clear_after_ms=2000)
        except Exception as err:
            traceback.print_exc()
            self._set_save_status("Save failed!")
            if manual:
                QMessageBox.warning(self, "Save Failed", f"Could not save notebook:\n{err}")

    def _set_save_status(self, text: str, clear_after_ms: int = 0):
        """Updates the save status label and optionally schedules it to clear."""
        if not hasattr(self, 'lbl_save_status'):
            return
        if text:
            self.lbl_save_status.setText(text)
            self.lbl_save_status.setVisible(True)
        else:
            self.lbl_save_status.setVisible(False)
        if clear_after_ms > 0:
            self._save_status_clear_timer.start(clear_after_ms)


    def _on_load_notebook_requested(self, notebook_id: str):
        try:
            payload = NotebookStorage.load_notebook(notebook_id)
            self._current_notebook_id = payload.get("board_id", notebook_id)
            self.current_board.board_id = payload.get("board_id", notebook_id)
            self.current_board.title = payload.get("title", "Notebook")
            self.title_edit.setText(self.current_board.title)
            
            self.scene.load_from_dict_list(
                payload.get("items", []),
                video_requested_callback=self._on_generate_video_requested,
                solve_requested_callback=self._on_stem_question_asked
            )
            self._sync_grid_btn_ui(self.scene.background_mode)
            
            self.main_stack.setCurrentWidget(self._canvas_wrapper)
            self._set_sidebar_active_button("canvas")
        except Exception as err:
            QMessageBox.warning(self, "Load Failed", f"Could not load notebook:\n{err}")

    def _on_notebook_git_requested(self, notebook_id: str):
        self.git_notes_panel.open_notebook_vcs(notebook_id)
        self.main_stack.setCurrentWidget(self.git_notes_panel)

    def _on_version_history_restored(self, version_ref: str):
        """Called when an earlier version is safely restored from Version History."""
        try:
            if self._current_notebook_id:
                self._on_load_notebook_requested(self._current_notebook_id)
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                main_board = os.path.join(base_dir, "storage_data", "boards", "board_main.json")
                if os.path.exists(main_board):
                    self.current_board.load_from_json(main_board)
                    self.scene.from_dict_list(self.current_board.to_dict_list())
        except Exception as err:
            print(f"[MainWindow] Post-restore reload warning: {err}")

    def _on_new_notebook_requested(self):
        """Legacy create_notebook_requested signal (now the panel handles new notebooks inline)."""
        self.sidebar_list.setCurrentRow(1)  # Switch to Notebooks panel

    def _on_toolbar_paste(self):
        self.scene.active_tool = "select"
        from ..backend.workspace.link_utils import is_valid_url, fetch_url_metadata
        from ..backend.workspace.summarizer_client import UrlSummarizerWorker

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
                self.scene.scene_changed.emit()
            else:
                bubble = AnswerBubble(title=f"Web Explanation: {meta.get('title', 'Article')[:25]}", full_text="Scraping & generating AI study guide...", question=f"Explain link: {text}")
                bubble.setPos(center_pos)
                self.scene.addItem(bubble)
                self.scene.scene_changed.emit()

                worker = UrlSummarizerWorker(text, title=meta.get("title", ""), parent=self)
                def _on_finished(u, t, summary):
                    bubble.update_solution(f"Explain link: {u}", summary)
                    if worker in self._solver_workers:
                        self._solver_workers.remove(worker)
                worker.finished.connect(_on_finished)
                self._solver_workers.append(worker)
                worker.start()
        else:
            from .items.text_box_item import TextBoxItem
            item = TextBoxItem(text=text)
            item.setPos(center_pos)
            self.scene.addItem(item)
            self.scene.scene_changed.emit()

    def _add_sticky_note(self):
        self.scene.active_tool = "select"
        item = StickyNote(text="New Freeform Note", color_key="yellow")
        item.setPos(self.view.mapToScene(self.view.viewport().rect().center()))
        self.scene.addItem(item)
        self.scene.scene_changed.emit()

    def _add_handwriting_note(self):
        self.scene.active_tool = "select"
        item = HandwritingNote(text="Handwritten notebook section...")
        item.setPos(self.view.mapToScene(self.view.viewport().rect().center()))
        item.widget.video_requested.connect(self._on_generate_video_requested)
        item.widget.solve_requested.connect(self._on_stem_question_asked)
        self.scene.addItem(item)
        self.scene.scene_changed.emit()

    def _add_table(self):
        self.scene.active_tool = "select"
        item = TableItem()
        item.setPos(self.view.mapToScene(self.view.viewport().rect().center()))
        self.scene.addItem(item)
        self.scene.scene_changed.emit()

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

    def _on_latex_video_requested(self, pdf_path: str, page_range: str, emphasis: str, out_type: str):
        
        current_subject = None
        if hasattr(self, 'subject_detail_view') and self.subject_detail_view.current_subject_id:
            current_subject = self.subject_detail_view.current_subject_id     

        job_id = request_video_generation(
            selected_text="Explain this document.", 
            pdf_path=pdf_path,
            page_range=page_range,         
            emphasis_note=emphasis,       
            output_type=out_type,
            subject_id=current_subject or ""
        )
        
        title = "Markdown: Study Notes" if out_type == "notes" else "Manim: Video Lesson"
        center_pos = self.view.mapToScene(self.view.viewport().rect().center())
        v_item = VideoFloatItem(job_id=job_id, title=title, video_url_or_path="")
        v_item.setPos(center_pos.x() + 300, center_pos.y())
        self.scene.addItem(v_item)
        
        self.pdf_viewer_widget.video_generation_started()
        v_item.player_widget.worker.status_updated.connect(self._on_latex_video_progress)


    def _on_latex_video_progress(self, job_id, stage, progress):
        self.pdf_viewer_widget.update_video_progress(stage, progress)

    def _find_non_overlapping_pos(self, initial_pos: QPointF, width: float = 580.0, height: float = 240.0) -> QPointF:
        """Finds a clear spot on the canvas, cascading downward/rightward if overlapping existing content."""
        pos = QPointF(initial_pos.x(), initial_pos.y())
        max_attempts = 12

        for _ in range(max_attempts):
            test_rect = QRectF(pos.x(), pos.y(), width, height)
            items_in_rect = self.scene.items(test_rect)

            has_collision = False
            for it in items_in_rect:
                cname = it.__class__.__name__
                if cname in ["AnswerBubble", "HandwritingNote", "StickyNote", "GraphCard", "PenechoDraftLayerItem", "TableItem", "ImageItem"]:
                    has_collision = True
                    break
                elif hasattr(it, "sceneBoundingRect"):
                    br = it.sceneBoundingRect()
                    if br.width() > 100 and br.height() > 60:
                        has_collision = True
                        break

            if not has_collision:
                return pos

            # Cascade downwards with clean margin
            pos.setY(pos.y() + height + 24.0)
            if pos.y() > 3200:
                pos.setX(pos.x() + width + 30.0)
                pos.setY(initial_pos.y())

        return pos

    def _on_pomodoro_time_updated(self, time_str: str, is_running: bool):
        """Updates the top bar timer button text to act as a compact persistent badge while running."""
        if hasattr(self, 'btn_pomodoro_toggle'):
            if is_running or (hasattr(self, 'pomodoro_timer') and self.pomodoro_timer._remaining_seconds != self.pomodoro_timer._duration_seconds):
                self.btn_pomodoro_toggle.setText(f" {time_str}")
            else:
                self.btn_pomodoro_toggle.setText("")

    def _toggle_pomodoro_timer(self):
        """Toggles the floating Pomodoro study timer widget overlay docked at top right."""
        if not hasattr(self, 'pomodoro_timer'):
            return
        is_vis = self.pomodoro_timer.isVisible()
        if is_vis:
            self.pomodoro_timer.hide()
        else:
            w = self.central_card.width()
            t_w = self.pomodoro_timer.width()
            self.pomodoro_timer.move(max(20, w - t_w - 24), 52)
            self.pomodoro_timer.show()
            self.pomodoro_timer.raise_()

    def _toggle_reference_panel(self):
        """Switches main stack to the full-page Constants Library view."""
        if hasattr(self, 'constants_library_view'):
            self.main_stack.setCurrentWidget(self.constants_library_view)
            if hasattr(self, '_set_sidebar_active_button'):
                self._set_sidebar_active_button("ref")

    def _on_stem_question_asked(self, question: str, target_pos=None, mode: str = None):
        # 1. Grounded RAG if PDF Study Mode is active
        if hasattr(self, 'pdf_rag_mgr') and self.pdf_rag_mgr.is_loaded() and hasattr(self, 'pdf_viewer_widget') and self.pdf_viewer_widget.isVisible():
            ai_response = self.pdf_rag_mgr.generate_grounded_answer(question)
            raw_pos = target_pos or self.view.mapToScene(self.view.viewport().rect().center())
            center_pos = self._find_non_overlapping_pos(raw_pos, width=580.0, height=220.0)
            bubble = AnswerBubble(title="PDF Grounded Answer", full_text=ai_response, question=question)
            bubble.setPos(center_pos)
            self.scene.addItem(bubble)
            return

        if target_pos:
            raw_pos = target_pos
        elif hasattr(self.view, 'last_mouse_scene_pos') and not self.view.last_mouse_scene_pos.isNull():
            raw_pos = self.view.last_mouse_scene_pos
        else:
            raw_pos = self.view.mapToScene(self.view.viewport().rect().center())

        place_pos = self._find_non_overlapping_pos(raw_pos, width=580.0, height=240.0)

        active_mode = mode or (self.ask_bar.get_mode() if hasattr(self, 'ask_bar') else "study")

        if active_mode == "classroom":
            loading_msg = "Classroom Mode: Fetching straight answer..."
            title_text = "Classroom Answer"
            is_direct = True
        else:
            loading_msg = "Study Mode: Generating step-by-step solution..."
            title_text = "Handwritten Solution"
            is_direct = False

        bubble = AnswerBubble(title=title_text, full_text=loading_msg, question=question, is_direct_math=is_direct)
        bubble.setPos(place_pos)
        self.scene.addItem(bubble)

        from ..backend.math_engine.stem_solver import StemSolverWorker
        worker = StemSolverWorker(question, mode=active_mode, parent=self)

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

    def _convert_to_latex(self):
        selected = self.scene.selectedItems()
        if not selected and not self.scene.items():
            QMessageBox.warning(self, "No Content", "There is nothing on the canvas to convert.")
            return

        if selected:
            rect = selected[0].sceneBoundingRect()
            for item in selected[1:]:
                rect = rect.united(item.sceneBoundingRect())
        else:
            rect = self.scene.itemsBoundingRect()

        if rect.isEmpty():
            return

        rect.adjust(-20, -20, 20, 20)

        size = rect.size().toSize()
        if size.width() > 2000 or size.height() > 2000:
            scale_factor = 2000.0 / max(size.width(), size.height())
            size = (rect.size() * scale_factor).toSize()

        from PyQt6.QtCore import QRectF
        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.white)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.scene.render(painter, target=QRectF(pixmap.rect()), source=rect)
        painter.end()

        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")
        image_b64 = buffer.data().toBase64().data().decode()

        template_type = self.latex_combo.currentText()
        current_mode = self.ask_bar.get_mode() if hasattr(self, 'ask_bar') else "study"
        action = self.classroom_action_combo.currentText()

        try:
            job_id = request_latex_generation(image_b64, template_type, current_mode, action)
        except Exception as e:
            QMessageBox.warning(self, "API Connection Error",
                f"Could not connect to the backend server.\n"
                f"Please ensure you are running the backend local server.\n\nError: {e}")
            return

        if hasattr(self, 'speedometer_widget'):
            self.speedometer_widget.start_task(f"Generating {template_type}...")

        self.latex_worker = LatexPollWorker(job_id, self)
        self.latex_worker.status_updated.connect(self._on_latex_status_updated)
        self.latex_worker.latex_ready.connect(self._on_latex_ready)
        self.latex_worker.pdf_ready.connect(self._on_latex_pdf_ready)
        self.latex_worker.pdf_failed.connect(self._on_latex_failed)
        self.latex_worker.start()

        self.ask_bar.input_field.setPlaceholderText(f"Converting to {template_type}...")

    def _toggle_theme(self):
        ThemeManager.instance().toggle_theme()

    def _close_latex_editor_tab(self):
        if self.latex_editor_widget.confirm_close():
            idx = self.canvas_tabs.indexOf(self.latex_editor_widget)
            if idx != -1:
                self.canvas_tabs.removeTab(idx)
            self.canvas_tabs.setCurrentWidget(self.view)

    def _close_pdf_split_screen(self):
        idx = self.canvas_tabs.indexOf(self.pdf_viewer_widget)
        if idx != -1:
            self.canvas_tabs.removeTab(idx)
        self.ask_bar.set_pdf_mode(False)
        self.canvas_tabs.setCurrentWidget(self.view)

    def _on_canvas_tab_closed(self, index: int):
        if index == 0:
            return
        widget = self.canvas_tabs.widget(index)
        if widget == self.latex_editor_widget:
            self._close_latex_editor_tab()
        elif widget == self.pdf_viewer_widget:
            self._close_pdf_split_screen()

    def _on_pdf_compiled(self, pdf_path: str):
        self.last_compiled_pdf_path = pdf_path
        if hasattr(self, 'btn_view_pdf'):
            self.btn_view_pdf.setVisible(True)

    def _open_in_app_pdf_viewer(self):
        if not getattr(self, 'last_compiled_pdf_path', None) or not os.path.exists(self.last_compiled_pdf_path):
            QMessageBox.information(self, "No PDF Available",
                "No compiled PDF file is available to view yet.\nPlease export your LaTeX document as a PDF first.")
            return

        self.pdf_viewer_widget.load_pdf(self.last_compiled_pdf_path)
        fname = os.path.basename(self.last_compiled_pdf_path)
        tab_title = f"📄 PDF: {fname[:16]}..." if len(fname) > 18 else f"📄 PDF: {fname}"
        self._show_or_update_tab(self.pdf_viewer_widget, tab_title)

    def _on_latex_ready(self, job_id, latex_code):
        if hasattr(self, 'speedometer_widget'):
            self.speedometer_widget.finish_success("LaTeX Ready!")
        self.ask_bar.input_field.setPlaceholderText("Ask Kestrel a question or paste a link...")

        notebook_title = self.current_board.title or "LaTeX_Document"
        self.latex_editor_widget.set_latex_code(latex_code, title=f"LaTeX: {notebook_title}")
        self._show_or_update_tab(self.latex_editor_widget, "📝 Editable LaTeX")

    def _on_latex_status_updated(self, job_id, stage, progress):
        if hasattr(self, 'speedometer_widget'):
            self.speedometer_widget.update_progress(stage, progress)
        self.ask_bar.input_field.setPlaceholderText(f"{stage} ({progress}%)")
        
    def _on_latex_pdf_ready(self, job_id, pdf_url, pdf_b64):
        if hasattr(self, 'progress_dialog') and self.progress_dialog.isVisible():
            self.progress_dialog.finish_success()
        self.ask_bar.input_field.setPlaceholderText("Ask Kestrel a question or paste a link...")

        notebook_title = self.current_board.title or "Untitled_Notebook"
        mode = self.ask_bar.get_mode() if hasattr(self, 'ask_bar') else "study"
        action = self.classroom_action_combo.currentText() if hasattr(self, 'classroom_action_combo') else "Action"
        safe_title = "".join(c for c in notebook_title if c.isalnum() or c in " _-").strip()
        filename = f"{safe_title}_{mode}_{action}.pdf".replace(" ", "_")

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        export_dir = os.path.join(base_dir, "storage_data", "latex_exports")
        os.makedirs(export_dir, exist_ok=True)
        save_path = os.path.join(export_dir, filename)

        if pdf_b64:
            with open(save_path, "wb") as f:
                f.write(base64.b64decode(pdf_b64))
        else:
            try:
                r = requests.get(pdf_url)
                with open(save_path, "wb") as f:
                    f.write(r.content)
            except Exception as e:
                QMessageBox.warning(self, "Download Error", f"Failed to download generated PDF:\n{e}")
                return

        self.pdf_viewer_widget.load_latex_pdf(save_path)
        self._show_or_update_tab(self.pdf_viewer_widget, f"📄 {filename}")

    def _on_latex_failed(self, job_id, error_msg):
        if hasattr(self, 'progress_dialog') and self.progress_dialog.isVisible():
            self.progress_dialog.finish_error(error_msg)
        self.ask_bar.input_field.setPlaceholderText("Ask Kestrel a question or paste a link...")
        QMessageBox.warning(self, "LaTeX Error", f"LaTeX generation failed:\n{error_msg}")
