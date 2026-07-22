"""
Main Application Window (Apple Freeform Shell Layout)
Sidebar (~260px), Top Toolbar, Infinite Canvas, Zoom HUD, Floating Tool Palette, AskBar & Notebooks Panel
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget,
    QListWidgetItem, QPushButton, QLineEdit, QLabel, QFrame,
    QSplitter, QStackedWidget, QFileDialog, QInputDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QSize
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

from ..backend.stem_solver import solve_stem_question
from ..backend.video_gen_client import request_video_generation
from ..storage.board_model import BoardModel
from ..storage.notebook_storage import NotebookStorage
from ..storage.downloads_manager import DownloadsManager

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kestrel")
        self.resize(1280, 800)
        self.setMinimumSize(900, 600)

        self.current_board = BoardModel("Notebook Board 1")
        self.downloads_mgr = DownloadsManager()
        self.reference_panel = ReferencePanel()
        self.reference_panel.insert_data_requested.connect(self._on_insert_reference_table)

        self._apply_global_styles()
        self._init_ui()

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Custom Title Bar Area
        self.title_bar = self._create_title_bar()
        root_layout.addWidget(self.title_bar)

        # 2. Main Content Splitter (Sidebar + Main View Stack)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)

        # Sidebar Panel (~260px wide)
        self.sidebar = self._create_sidebar()
        self.splitter.addWidget(self.sidebar)

        # Canvas & Toolbar Container
        self.canvas_container = QWidget(self)
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
        self.main_stack.addWidget(self.notebooks_panel) # Index 1

        cc_layout.addWidget(self.main_stack)
        self.splitter.addWidget(self.canvas_container)

        self.splitter.setSizes([260, 1020])
        root_layout.addWidget(self.splitter)

        self._populate_demo_canvas()

    def _apply_global_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f2f2f7;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }
            QSplitter::handle {
                background-color: #d1d1d6;
            }
        """)

    def _create_title_bar(self) -> QWidget:
        tb = QWidget(self)
        tb.setFixedHeight(38)
        tb.setStyleSheet("background-color: #e5e5ea; border-bottom: 1px solid #d1d1d6;")
        layout = QHBoxLayout(tb)
        layout.setContentsMargins(12, 0, 12, 0)

        # Traffic Lights
        tl_layout = QHBoxLayout()
        tl_layout.setSpacing(6)
        for color in ["#ff5f56", "#ffbd2e", "#27c93f"]:
            dot = QFrame()
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(f"background-color: {color}; border-radius: 6px;")
            tl_layout.addWidget(dot)
        layout.addLayout(tl_layout)

        layout.addStretch()
        lbl_app = QLabel("Kestrel — Handwritten Freeform Notebook", tb)
        lbl_app.setStyleSheet("font-size: 13px; font-weight: 600; color: #3a3a3c;")
        layout.addWidget(lbl_app)
        layout.addStretch()

        return tb

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

        # Reference Panel Button in Sidebar
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

        # Sidebar toggle
        btn_sb_toggle = QPushButton(qta.icon('fa5s.bars', color='#1c1c1e'), "", tb)
        btn_sb_toggle.clicked.connect(self._toggle_sidebar)
        layout.addWidget(btn_sb_toggle)

        btn_back = QPushButton(qta.icon('fa5s.chevron-left', color='#007aff'), "", tb)
        btn_back.clicked.connect(lambda: self.main_stack.setCurrentIndex(0))
        layout.addWidget(btn_back)

        # Board Title
        self.title_edit = QLineEdit(self.current_board.title, tb)
        self.title_edit.setFixedWidth(200)
        self.title_edit.editingFinished.connect(self._on_title_changed)
        layout.addWidget(self.title_edit)

        layout.addStretch()

        # Pill Icon Cluster
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

        # Grid Mode Toggle Button
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

        # Left: Zoom Control HUD
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

        # Center: AskBar Floating Widget
        self.ask_bar = AskBar(hud)
        self.ask_bar.question_submitted.connect(self._on_stem_question_asked)
        layout.addWidget(self.ask_bar)

        # Right: Floating Drawing Tools (Select, Pen, Highlighter, Eraser)
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
                video_requested_callback=self._on_generate_video_requested
            )
            
            self.main_stack.setCurrentIndex(0)
            self.sidebar_list.setCurrentRow(0)
        except Exception as err:
            QMessageBox.warning(self, "Load Failed", f"Could not load notebook:\n{err}")

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
        from ..backend.summarizer_client import summarize_url

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
                summary = summarize_url(text, title=meta.get("title", ""))
                bubble = AnswerBubble(title=f"Web Explanation: {meta.get('title', 'Article')[:25]}", full_text=summary, question=f"Explain link: {text}")
                bubble.setPos(center_pos)
                self.scene.addItem(bubble)
        else:
            note = HandwritingNote(text=text)
            note.setPos(center_pos)
            note.widget.video_requested.connect(self._on_generate_video_requested)
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

    def _on_stem_question_asked(self, question: str):
        res = solve_stem_question(question)
        solution = res.get("solution", "")
        plot_path = res.get("plot_path", "")

        center_pos = self.view.mapToScene(self.view.viewport().rect().center())
        bubble = AnswerBubble(title="Handwritten Solution", full_text=solution, question=question)
        bubble.setPos(center_pos)
        self.scene.addItem(bubble)

        if plot_path:
            graph_card = GraphCard(title=f"Graph: {question[:25]}", image_path=plot_path)
            graph_card.setPos(center_pos.x() + 450, center_pos.y())
            self.scene.addItem(graph_card)

    def _populate_demo_canvas(self):
        pass
