"""
Main Application Window (Apple Freeform Shell Layout)
Sidebar (~260px), Top Toolbar, Infinite Canvas, Zoom HUD, Floating Tool Palette, AskBar, Notebooks Panel & PDF Split-Screen Study Mode
"""

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget,
    QListWidgetItem, QPushButton, QLineEdit, QLabel, QFrame,
    QSplitter, QStackedWidget, QFileDialog, QInputDialog, QMessageBox,
    QMenu, QComboBox
)
from PyQt6.QtCore import Qt, QSize, QBuffer, QIODevice
from PyQt6.QtGui import QFont, QColor, QAction, QPixmap
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
from .widgets.pdf_viewer_widget import PdfViewerWidget
from .widgets.folder_tree_widget import FolderTreeWidget
from .views.notebooks_panel import NotebooksPanel
from .views.placeholder_panel import PlaceholderPanel
from .views.settings_dialog import SettingsDialog
from .views.progress_dialog import ProgressDialog

from ..backend.stem_solver import solve_stem_question
from ..backend.pdf_rag_manager import PdfRAGManager
from ..backend.video_gen_client import request_video_generation
from ..storage.board_model import BoardModel
from ..storage.notebook_storage import NotebookStorage
from ..storage.downloads_manager import DownloadsManager
from ..backend.latex_client import request_latex_generation, LatexPollWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kestrel")
        self.resize(1280, 800)
        self.setMinimumSize(900, 600)

        self.current_board = BoardModel("Notebook Board 1")
        self.downloads_mgr = DownloadsManager()
        self.pdf_rag_mgr = PdfRAGManager()

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

        # Main View Stack (Index 0: Canvas / Split View, Index 1: Notebooks View)
        self.main_stack = QStackedWidget(self.canvas_container)

        # Canvas & PDF Split-Screen Wrapper
        canvas_wrapper = QWidget(self.main_stack)
        cw_layout = QVBoxLayout(canvas_wrapper)
        cw_layout.setContentsMargins(0, 0, 0, 0)
        cw_layout.setSpacing(0)

        # PDF Splitter (Left: PDF Viewer, Right: Canvas View)
        self.pdf_canvas_splitter = QSplitter(Qt.Orientation.Horizontal, canvas_wrapper)
        self.pdf_canvas_splitter.setHandleWidth(2)

        # PDF Viewer Widget
        self.pdf_viewer_widget = PdfViewerWidget(self.pdf_canvas_splitter)
        self.pdf_viewer_widget.close_requested.connect(self._close_pdf_split_screen)
        self.pdf_viewer_widget.reply_clicked.connect(self._on_pdf_reply_clicked)
        self.pdf_viewer_widget.hide() # Hidden by default until PDF is opened
        self.pdf_canvas_splitter.addWidget(self.pdf_viewer_widget)

        # Scene and View
        self.scene = CanvasScene(self)
        self.view = CanvasView(self.scene, self)
        self.view.zoom_changed.connect(self._on_zoom_changed)
        self.pdf_canvas_splitter.addWidget(self.view)

        cw_layout.addWidget(self.pdf_canvas_splitter)

        # Bottom Floating HUD Overlay (AskBar + Zoom HUD + Floating Tools)
        self.hud_overlay = self._create_hud_overlay()
        cw_layout.addWidget(self.hud_overlay)

        self.main_stack.addWidget(canvas_wrapper) # Index 0

        # Notebooks View Panel
        self.notebooks_panel = NotebooksPanel(self.main_stack)
        self.notebooks_panel.open_notebook_requested.connect(self._on_load_notebook_requested)
        self.notebooks_panel.create_notebook_requested.connect(self._on_new_notebook_requested)
        self.notebooks_panel.folder_navigated.connect(self._on_panel_folder_navigated)
        self.main_stack.addWidget(self.notebooks_panel) # Index 1
        
        # Placeholder Panel
        self.placeholder_panel = PlaceholderPanel(self.main_stack)
        self.main_stack.addWidget(self.placeholder_panel) # Index 2

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
        layout.setSpacing(0)

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

        # Folder Tree Widget (visible only when Notebooks is selected)
        self.folder_tree = FolderTreeWidget(sb)
        self.folder_tree.folder_selected.connect(self._on_sidebar_folder_selected)
        self.folder_tree.tree_changed.connect(self._on_folder_tree_changed)
        self.folder_tree.setVisible(False)
        layout.addWidget(self.folder_tree)

        layout.addStretch()

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

        btn_pdf = QPushButton(qta.icon('fa5s.file-pdf', color='#ff3b30'), "PDF Mode", pill)
        btn_pdf.setStyleSheet("color: #ff3b30; font-weight: bold;")
        btn_pdf.clicked.connect(self._open_pdf_dialog)

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

        # Drawing Tools
        btn_cursor = QPushButton(qta.icon('fa5s.mouse-pointer', color='#1c1c1e'), "Select", pill)
        btn_cursor.clicked.connect(lambda: self._set_tool("select"))

        btn_pen = QPushButton(qta.icon('fa5s.pen-nib', color='#007aff'), "Pen", pill)
        btn_pen.clicked.connect(lambda: self._set_tool("pen"))

        btn_eraser = QPushButton(qta.icon('fa5s.eraser', color='#ff3b30'), "Eraser", pill)
        btn_eraser.clicked.connect(lambda: self._set_tool("eraser"))

        self.btn_grid_mode = QPushButton("📄 Ruled Paper", pill)
        self.btn_grid_mode.setStyleSheet("color: #007aff; font-weight: bold;")
        self.btn_grid_mode.clicked.connect(self._toggle_grid_mode)

        self.latex_combo = QComboBox(pill)
        self.latex_combo.addItems(["Homework", "Assignment", "Research Paper", "Lecture Slides"])
        self.latex_combo.setStyleSheet("""
            QComboBox {
                border: none;
                background: transparent;
                font-size: 12px;
                font-weight: 600;
                color: #1c1c1e;
                padding-left: 10px;
            }
            QComboBox::drop-down { border: none; }
        """)
        
        btn_latex = QPushButton(qta.icon('fa5s.file-code', color='#9c27b0'), "Convert to LaTeX", pill)
        btn_latex.setStyleSheet("color: #9c27b0; font-weight: bold;")
        btn_latex.clicked.connect(self._convert_to_latex)

        pill_layout.addWidget(btn_pdf)
        pill_layout.addWidget(btn_save)
        pill_layout.addWidget(btn_paste)
        pill_layout.addWidget(btn_sticky)
        pill_layout.addWidget(btn_note)
        pill_layout.addWidget(btn_table)
        pill_layout.addWidget(btn_group)
        
        # Add drawing tools separator
        sep0 = QFrame(pill)
        sep0.setFrameShape(QFrame.Shape.VLine)
        sep0.setFrameShadow(QFrame.Shadow.Sunken)
        sep0.setStyleSheet("color: #d1d1d6;")
        pill_layout.addWidget(sep0)
        
        pill_layout.addWidget(btn_cursor)
        pill_layout.addWidget(btn_pen)
        pill_layout.addWidget(btn_eraser)
        
        pill_layout.addWidget(self.btn_grid_mode)
        
        # Add a separator
        sep = QFrame(pill)
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setStyleSheet("color: #d1d1d6;")
        pill_layout.addWidget(sep)
        
        pill_layout.addWidget(self.latex_combo)
        pill_layout.addWidget(btn_latex)

        layout.addWidget(pill)
        layout.addStretch()
        
        btn_settings = QPushButton(qta.icon('fa5s.cog', color='#8e8e93'), "", tb)
        btn_settings.setToolTip("Settings & Diagnostics")
        btn_settings.clicked.connect(self._open_settings)
        layout.addWidget(btn_settings)

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
        self.ask_bar.question_with_context_submitted.connect(self._on_question_with_context_asked)
        self.ask_bar.pdf_requested.connect(self._open_pdf_dialog)
        layout.addWidget(self.ask_bar)

        # Right: Floating Drawing Tools (Select, Pen, Highlighter with Colors, Eraser)
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

        # Highlighter Button with Color Menu
        self.btn_highlighter = QPushButton(qta.icon('fa5s.highlighter', color='#ff9500'), "", tools_hud)
        self.btn_highlighter.setToolTip("Highlighter (Click for Colors)")
        self.btn_highlighter.clicked.connect(self._on_highlighter_clicked)

        btn_eraser = QPushButton(qta.icon('fa5s.eraser', color='#ff3b30'), "", tools_hud)
        btn_eraser.clicked.connect(lambda: self._set_tool("eraser"))

        th_layout.addWidget(btn_cursor)
        th_layout.addWidget(btn_pen)
        th_layout.addWidget(self.btn_highlighter)
        th_layout.addWidget(btn_eraser)

        layout.addWidget(tools_hud)

        return hud

    def _on_highlighter_clicked(self):
        """
        Activates highlighter tool and pops up a color selection menu (Yellow, Green, Blue, Pink).
        """
        self._set_tool("highlighter")
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: 600;
            }
            QMenu::item:selected {
                background-color: #f2f2f7;
            }
        """)

        act_yellow = QAction("🟡 Yellow (#ffe066)", self)
        act_yellow.triggered.connect(lambda: self.scene.set_highlighter_color("#ffe066"))

        act_green = QAction("🟢 Green (#a8e6cf)", self)
        act_green.triggered.connect(lambda: self.scene.set_highlighter_color("#a8e6cf"))

        act_blue = QAction("🔵 Blue (#90caf9)", self)
        act_blue.triggered.connect(lambda: self.scene.set_highlighter_color("#90caf9"))

        act_pink = QAction("🌸 Pink (#ffb7b2)", self)
        act_pink.triggered.connect(lambda: self.scene.set_highlighter_color("#ffb7b2"))

        menu.addAction(act_yellow)
        menu.addAction(act_green)
        menu.addAction(act_blue)
        menu.addAction(act_pink)

        pos = self.btn_highlighter.mapToGlobal(self.btn_highlighter.rect().topLeft())
        menu.exec(pos)

    def _set_tool(self, tool_name: str):
        self.scene.active_tool = tool_name

    def _open_pdf_dialog(self):
        """
        Opens QFileDialog to select a PDF file and loads it into Split-Screen RAG mode.
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF for Study Mode", "", "PDF Files (*.pdf);;All Files (*)"
        )
        if file_path:
            self._load_pdf_into_split_screen(file_path)

    def _load_pdf_into_split_screen(self, file_path: str):
        try:
            success_rag = self.pdf_rag_mgr.load_pdf(file_path)
            success_view = self.pdf_viewer_widget.load_pdf(file_path)

            if success_rag and success_view:
                self.pdf_viewer_widget.show()
                self.pdf_canvas_splitter.setSizes([520, 520])
                
                fname = os.path.basename(file_path)
                self.ask_bar.set_pdf_mode(True, filename=fname)

                # Generate initial Grounded Document Summary directly onto canvas paper
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
                QMessageBox.warning(self, "PDF Error", "Could not load the selected PDF document.")
        except Exception as err:
            QMessageBox.warning(self, "PDF Exception", f"Error opening PDF:\n{err}")

    def _close_pdf_split_screen(self):
        self.pdf_viewer_widget.hide()
        self.ask_bar.set_pdf_mode(False)

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
        if row == 0:
            self.folder_tree.setVisible(False)
            self.main_stack.setCurrentIndex(0)
        elif row == 1: # "📓 Notebooks"
            self._refresh_folder_tree()
            self.folder_tree.setVisible(True)
            self.notebooks_panel.refresh()
            self.main_stack.setCurrentIndex(1)
        else:
            self.folder_tree.setVisible(False)
            item_text = self.sidebar_list.item(row).text()
            import re
            clean_title = re.sub(r'^[^\w\s]+', '', item_text).split('(')[0].strip()
            self.placeholder_panel.set_title(clean_title)
            self.main_stack.setCurrentIndex(2)

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
        """Legacy create_notebook_requested signal (now the panel handles new notebooks inline)."""
        self.sidebar_list.setCurrentRow(1)  # Switch to Notebooks panel

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
        # 1. Grounded RAG if PDF Study Mode is active
        if self.pdf_rag_mgr.is_loaded() and self.pdf_viewer_widget.isVisible():
            ai_response = self.pdf_rag_mgr.generate_grounded_answer(question)
            center_pos = self.view.mapToScene(self.view.viewport().rect().center())
            bubble = AnswerBubble(title="PDF Grounded Answer", full_text=ai_response, question=question)
            bubble.setPos(center_pos)
            self.scene.addItem(bubble)
            return

        # 2. Standard STEM Symbolic Solver
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

    def _convert_to_latex(self):
        items = self.scene.selectedItems()
        if not items:
            items = self.scene.items()
            if not items:
                QMessageBox.warning(self, "No Content", "There is nothing on the canvas to convert.")
                return
        
        if self.scene.selectedItems():
            rect = self.scene.selectedItems()[0].sceneBoundingRect()
            for item in self.scene.selectedItems()[1:]:
                rect = rect.united(item.sceneBoundingRect())
        else:
            rect = self.scene.itemsBoundingRect()

        if rect.isEmpty():
            return
            
        rect.adjust(-20, -20, 20, 20)
        
        # Max scale down if image too large to avoid huge memory/API payload
        size = rect.size().toSize()
        scale_factor = 1.0
        if size.width() > 2000 or size.height() > 2000:
            scale_factor = 2000.0 / max(size.width(), size.height())
            size = (rect.size() * scale_factor).toSize()

        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.white)
        
        import PyQt6.QtGui as QtGui
        import PyQt6.QtCore as QtCore
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        
        # Draw the scene area to the pixmap
        target_rect = QtCore.QRectF(pixmap.rect())
        self.scene.render(painter, target=target_rect, source=rect)
        painter.end()

        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")
        image_b64 = buffer.data().toBase64().data().decode()
        
        template_type = self.latex_combo.currentText()
        
        try:
            job_id = request_latex_generation(image_b64, template_type)
        except Exception as e:
            QMessageBox.warning(self, "API Connection Error", f"Could not connect to the backend server.\nPlease ensure you are running the backend local server (`python backend/local_server.py`).\n\nError: {e}")
            return
        
        self.progress_dialog = ProgressDialog(self, title=f"Generating {template_type}...")
        self.progress_dialog.show()
        
        self.latex_worker = LatexPollWorker(job_id, self)
        self.latex_worker.status_updated.connect(self._on_latex_status_updated)
        self.latex_worker.pdf_ready.connect(self._on_latex_pdf_ready)
        self.latex_worker.pdf_failed.connect(self._on_latex_failed)
        self.latex_worker.start()
        
        self.ask_bar.input_field.setPlaceholderText(f"Converting to {template_type}...")

    def _on_latex_status_updated(self, job_id, stage, progress):
        if hasattr(self, 'progress_dialog') and self.progress_dialog.isVisible():
            self.progress_dialog.update_progress(stage, progress)
        self.ask_bar.input_field.setPlaceholderText(f"{stage} ({progress}%)")
        
    def _on_latex_pdf_ready(self, job_id, pdf_url, pdf_b64):
        if hasattr(self, 'progress_dialog') and self.progress_dialog.isVisible():
            self.progress_dialog.finish_success()
        self.ask_bar.input_field.setPlaceholderText("Ask Kestrel a question or paste a link...")
        import tempfile
        import base64
        
        fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        if pdf_b64:
            with open(temp_path, "wb") as f:
                f.write(base64.b64decode(pdf_b64))
        else:
            import requests
            try:
                r = requests.get(pdf_url)
                with open(temp_path, "wb") as f:
                    f.write(r.content)
            except Exception as e:
                QMessageBox.warning(self, "Download Error", f"Failed to download generated PDF:\n{e}")
                return
                
        self.pdf_viewer_widget.load_latex_pdf(temp_path)
        self.pdf_viewer_widget.show()
        if self.pdf_canvas_splitter.sizes()[0] == 0:
            self.pdf_canvas_splitter.setSizes([520, 520])

    def _on_latex_failed(self, job_id, error_msg):
        if hasattr(self, 'progress_dialog') and self.progress_dialog.isVisible():
            self.progress_dialog.finish_error(error_msg)
        self.ask_bar.input_field.setPlaceholderText("Ask Kestrel a question or paste a link...")
        QMessageBox.warning(self, "LaTeX Error", f"LaTeX generation failed:\n{error_msg}")

    def _populate_demo_canvas(self):
        pass
