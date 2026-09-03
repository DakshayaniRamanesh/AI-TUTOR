"""
Version History Panel - Kestrel-native Version History & Checkpoints View
Replaces raw Git-centric terminology with a human-friendly, object-aware interface:
  - Version History (Git history)
  - Save Version (commit)
  - Review Changes (diff)
  - Restore Version (safe, non-destructive restore)
  - Create Copy (branch/fork)
  - Developer Mode toggle for technical Git inspectability
"""

import os
import html
import json
import re
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QTreeWidget, QTreeWidgetItem,
    QTextEdit, QTextBrowser, QPushButton, QComboBox, QLabel, QFrame, QStackedWidget,
    QPlainTextEdit, QCheckBox, QInputDialog, QMessageBox, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem, QGraphicsRectItem,
    QListWidget, QListWidgetItem, QDialog, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QBrush, QPen, QIcon
import qtawesome as qta

from ...backend.version_control.git_notes_manager import GitNotesManager, GitAdapter, GitError
from ...backend.version_control.version_service import (
    VersionService, VersionSnapshot, ObjectChange, ChangeAction, VersionDiff
)
from ..theme_manager import ThemeManager


class VersionHistoryPanel(QWidget):
    """
    Kestrel-native Version History Panel.
    Provides timeline cards, object-level visual diffing, non-destructive restores,
    and a Developer Mode for technical Git operations.
    """

    version_restored = pyqtSignal(str)  # Emitted when a version is restored

    def __init__(self, parent=None):
        super().__init__(parent)
        self.version_service = VersionService()
        self.git_mgr = self.version_service.adapter
        self.active_filename = "physics_quantum_notes.md"
        self.active_notebook_id: Optional[str] = None
        self.developer_mode = False

        self._init_ui()
        self.refresh_all()

    def _init_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Main Horizontal Splitter: Sidebar (280px) + Main Content Area
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #d1d1d6; }")

        # 1. Left Documents & Navigation Sidebar
        self.sidebar_widget = self._create_sidebar()
        self.splitter.addWidget(self.sidebar_widget)

        # 2. Right Workspace Container
        self.workspace_widget = self._create_workspace()
        self.splitter.addWidget(self.workspace_widget)

        self.splitter.setSizes([280, 1000])
        root_layout.addWidget(self.splitter)

        self._apply_theme()

    def _apply_theme(self):
        self.setStyleSheet("""
            QWidget#VersionHistoryRoot {
                background-color: #f2f2f7;
            }
            QLabel {
                color: #1c1c1e;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
                color: #1c1c1e;
            }
            QPushButton:hover {
                background-color: #e5e5ea;
            }
            QPushButton:pressed {
                background-color: #d1d1d6;
            }
            QTreeWidget {
                background-color: #ffffff;
                border: 1px solid #e5e5ea;
                border-radius: 8px;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 6px;
                border-radius: 4px;
            }
            QTreeWidget::item:selected {
                background-color: #007aff;
                color: white;
            }
        """)

    # ── Sidebar ────────────────────────────────────────────────────────────────

    def _create_sidebar(self) -> QWidget:
        sb = QWidget(self)
        sb.setFixedWidth(280)
        sb.setObjectName("VCSidebar")
        layout = QVBoxLayout(sb)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Top Section: Save Version CTA
        self.btn_save_version = QPushButton("Save Version", sb)
        self.btn_save_version.setIcon(qta.icon("fa5s.check-circle", color="#ffffff"))
        self.btn_save_version.setFixedHeight(34)
        self.btn_save_version.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_version.setStyleSheet("""
            QPushButton {
                background-color: #007aff;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border: none;
                border-radius: 8px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        self.btn_save_version.clicked.connect(self._on_save_version_clicked)
        layout.addWidget(self.btn_save_version)

        # Developer Mode Branch Controls (hidden by default)
        self.dev_branch_box = QFrame(sb)
        self.dev_branch_box.setStyleSheet("background-color: #e5e5ea; border-radius: 8px; padding: 4px;")
        db_layout = QHBoxLayout(self.dev_branch_box)
        db_layout.setContentsMargins(6, 4, 6, 4)
        db_layout.setSpacing(6)

        lbl_b_icon = QLabel(self.dev_branch_box)
        lbl_b_icon.setPixmap(qta.icon("fa5s.code-branch", color="#28a745").pixmap(14, 14))
        db_layout.addWidget(lbl_b_icon)

        self.cb_branches = QComboBox(self.dev_branch_box)
        self.cb_branches.currentIndexChanged.connect(self._on_branch_changed)
        db_layout.addWidget(self.cb_branches, 1)

        btn_new_branch = QPushButton("+ Branch", self.dev_branch_box)
        btn_new_branch.clicked.connect(self._on_new_branch_clicked)
        db_layout.addWidget(btn_new_branch)

        layout.addWidget(self.dev_branch_box)
        self.dev_branch_box.setVisible(False)

        # Developer Mode Staging Box (hidden by default)
        self.dev_staging_box = QFrame(sb)
        st_layout = QHBoxLayout(self.dev_staging_box)
        st_layout.setContentsMargins(0, 0, 0, 0)
        btn_stage_all = QPushButton("Stage All", self.dev_staging_box)
        btn_stage_all.clicked.connect(self._on_stage_all)
        btn_unstage_all = QPushButton("Unstage All", self.dev_staging_box)
        btn_unstage_all.clicked.connect(self._on_unstage_all)
        st_layout.addWidget(btn_stage_all)
        st_layout.addWidget(btn_unstage_all)
        layout.addWidget(self.dev_staging_box)
        self.dev_staging_box.setVisible(False)

        # Section Header: Documents & Boards
        lbl_docs = QLabel("DOCUMENTS & BOARDS", sb)
        lbl_docs.setStyleSheet("font-size: 11px; font-weight: bold; color: #8e8e93; letter-spacing: 0.5px;")
        layout.addWidget(lbl_docs)

        # File / Board Tree
        self.tree_vcs = QTreeWidget(sb)
        self.tree_vcs.setHeaderHidden(True)
        self.tree_vcs.itemClicked.connect(self._on_tree_item_clicked)
        layout.addWidget(self.tree_vcs, 1)

        # New Note Button
        btn_new_note = QPushButton("New Note (.md)", sb)
        btn_new_note.setIcon(qta.icon("fa5s.file-alt", color="#007aff"))
        btn_new_note.clicked.connect(self._on_new_note_clicked)
        layout.addWidget(btn_new_note)

        return sb

    # ── Workspace ─────────────────────────────────────────────────────────────

    def _create_workspace(self) -> QWidget:
        ws = QWidget(self)
        layout = QVBoxLayout(ws)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top Navigation & Header Bar
        nav_bar = QWidget(ws)
        nav_bar.setFixedHeight(46)
        nav_bar.setStyleSheet("background-color: #ffffff; border-bottom: 1px solid #e5e5ea;")
        nb_layout = QHBoxLayout(nav_bar)
        nb_layout.setContentsMargins(14, 0, 14, 0)
        nb_layout.setSpacing(8)

        # Tab Segmented Buttons
        self.btn_tab_history = QPushButton("Timeline", nav_bar)
        self.btn_tab_history.setIcon(qta.icon("fa5s.history", color="#6e6e73"))
        self.btn_tab_diff = QPushButton("Review Changes", nav_bar)
        self.btn_tab_diff.setIcon(qta.icon("fa5s.exchange-alt", color="#6e6e73"))
        self.btn_tab_editor = QPushButton("Notes Editor", nav_bar)
        self.btn_tab_editor.setIcon(qta.icon("fa5s.edit", color="#6e6e73"))
        self.btn_tab_graph = QPushButton("Branch Graph", nav_bar)
        self.btn_tab_graph.setIcon(qta.icon("fa5s.project-diagram", color="#6e6e73"))

        self.tab_buttons = [
            self.btn_tab_history,
            self.btn_tab_diff,
            self.btn_tab_editor,
            self.btn_tab_graph
        ]

        for i, btn in enumerate(self.tab_buttons):
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #6e6e73;
                    border: none;
                    font-weight: 600;
                    font-size: 13px;
                    padding: 6px 12px;
                    border-bottom: 2px solid transparent;
                    border-radius: 0px;
                }
                QPushButton:checked {
                    color: #007aff;
                    border-bottom: 2px solid #007aff;
                }
                QPushButton:hover {
                    color: #1c1c1e;
                }
            """)
            btn.clicked.connect(lambda checked, idx=i: self.switch_view_mode(idx))

        nb_layout.addWidget(self.btn_tab_history)
        nb_layout.addWidget(self.btn_tab_diff)
        nb_layout.addWidget(self.btn_tab_editor)
        nb_layout.addWidget(self.btn_tab_graph)
        self.btn_tab_graph.setVisible(False)  # Revealed only in Developer Mode

        nb_layout.addStretch()

        # Active File Label
        self.lbl_active_note = QLabel(self.active_filename, nav_bar)
        self.lbl_active_note.setStyleSheet("color: #1c1c1e; font-weight: 600; font-size: 13px;")
        nb_layout.addWidget(self.lbl_active_note)

        # Developer Mode Checkbox Toggle
        self.chk_dev_mode = QCheckBox("Developer Mode", nav_bar)
        self.chk_dev_mode.setToolTip("Show technical Git branches, commit hashes, and raw diffs")
        self.chk_dev_mode.setStyleSheet("font-size: 11px; font-weight: 500; color: #8e8e93;")
        self.chk_dev_mode.toggled.connect(self._on_dev_mode_toggled)
        nb_layout.addWidget(self.chk_dev_mode)

        layout.addWidget(nav_bar)

        # Stacked Views Container
        self.stack_views = QStackedWidget(ws)

        # View 0: Human-readable Timeline (Primary)
        self.view_history = self._create_timeline_view()
        self.stack_views.addWidget(self.view_history)

        # View 1: Review Changes (Object-Level & Line Diff)
        self.view_diff = self._create_review_changes_view()
        self.stack_views.addWidget(self.view_diff)

        # View 2: Notes Editor & Live Preview
        self.view_editor = self._create_editor_view()
        self.stack_views.addWidget(self.view_editor)

        # View 3: Git DAG Graph (Developer Mode)
        self.view_graph = self._create_graph_view()
        self.stack_views.addWidget(self.view_graph)

        layout.addWidget(self.stack_views)

        # Bottom Status Bar
        status_bar = QWidget(ws)
        status_bar.setFixedHeight(28)
        status_bar.setStyleSheet("background-color: #ffffff; border-top: 1px solid #e5e5ea; font-size: 11px; color: #8e8e93;")
        sb_layout = QHBoxLayout(status_bar)
        sb_layout.setContentsMargins(14, 0, 14, 0)

        self.lbl_status_vcs = QLabel("All changes protected in Version History", status_bar)
        self.lbl_status_vcs.setStyleSheet("color: #28a745; font-weight: 500;")
        sb_layout.addWidget(self.lbl_status_vcs)

        sb_layout.addStretch()
        self.lbl_status_meta = QLabel("", status_bar)
        sb_layout.addWidget(self.lbl_status_meta)

        layout.addWidget(status_bar)

        # Set default tab: Timeline
        self.switch_view_mode(0)

        return ws

    # ── View 0: Timeline View ─────────────────────────────────────────────────

    def _create_timeline_view(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background-color: #f2f2f7;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Scrollable area for version cards
        self.timeline_scroll = QScrollArea(container)
        self.timeline_scroll.setWidgetResizable(True)
        self.timeline_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.timeline_scroll.setStyleSheet("background: transparent;")

        self.timeline_cards_widget = QWidget()
        self.timeline_cards_widget.setStyleSheet("background: transparent;")
        self.timeline_cards_layout = QVBoxLayout(self.timeline_cards_widget)
        self.timeline_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.timeline_cards_layout.setSpacing(10)
        self.timeline_cards_layout.addStretch()

        self.timeline_scroll.setWidget(self.timeline_cards_widget)
        layout.addWidget(self.timeline_scroll)

        return container

    # ── View 1: Review Changes View ───────────────────────────────────────────

    def _create_review_changes_view(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background-color: #ffffff;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header for Changes
        self.lbl_diff_header = QLabel("Review Changes", container)
        self.lbl_diff_header.setStyleSheet("font-size: 15px; font-weight: bold; color: #1c1c1e;")
        layout.addWidget(self.lbl_diff_header)

        # Splitter: Object Cards Summary (Top/Left) + Line Diff View
        self.diff_splitter = QSplitter(Qt.Orientation.Vertical)
        self.diff_splitter.setHandleWidth(1)
        self.diff_splitter.setStyleSheet("QSplitter::handle { background-color: #e5e5ea; }")

        # Object Changes Container
        self.obj_changes_scroll = QScrollArea(container)
        self.obj_changes_scroll.setWidgetResizable(True)
        self.obj_changes_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.obj_changes_widget = QWidget()
        self.obj_changes_layout = QVBoxLayout(self.obj_changes_widget)
        self.obj_changes_layout.setContentsMargins(4, 4, 4, 4)
        self.obj_changes_layout.setSpacing(8)
        self.obj_changes_layout.addStretch()
        self.obj_changes_scroll.setWidget(self.obj_changes_widget)
        self.diff_splitter.addWidget(self.obj_changes_scroll)

        # Text Line Diff Container
        self.diff_text_browser = QTextBrowser(container)
        self.diff_text_browser.setFont(QFont("Consolas", 10))
        self.diff_text_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #f8f9fa;
                border: 1px solid #e5e5ea;
                border-radius: 8px;
                padding: 10px;
                color: #1c1c1e;
            }
        """)
        self.diff_splitter.addWidget(self.diff_text_browser)

        self.diff_splitter.setSizes([200, 400])
        layout.addWidget(self.diff_splitter, 1)

        return container

    # ── View 2: Notes Editor View ─────────────────────────────────────────────

    def _create_editor_view(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        editor_splitter = QSplitter(Qt.Orientation.Horizontal)
        editor_splitter.setHandleWidth(1)

        # Left Editor
        left_box = QWidget()
        lbl_layout = QVBoxLayout(left_box)
        lbl_layout.setContentsMargins(0, 0, 0, 0)
        lbl_editor_title = QLabel("Markdown Source", left_box)
        lbl_editor_title.setStyleSheet("font-weight: 600; font-size: 12px; color: #6e6e73;")
        lbl_layout.addWidget(lbl_editor_title)

        self.txt_editor = QTextEdit(left_box)
        self.txt_editor.setFont(QFont("Consolas", 11))
        self.txt_editor.setStyleSheet("border: 1px solid #e5e5ea; border-radius: 8px; padding: 8px;")
        self.txt_editor.textChanged.connect(self._on_editor_text_changed)
        lbl_layout.addWidget(self.txt_editor)
        editor_splitter.addWidget(left_box)

        # Right Live Preview
        right_box = QWidget()
        rbl_layout = QVBoxLayout(right_box)
        rbl_layout.setContentsMargins(0, 0, 0, 0)
        lbl_preview_title = QLabel("Live Preview", right_box)
        lbl_preview_title.setStyleSheet("font-weight: 600; font-size: 12px; color: #6e6e73;")
        rbl_layout.addWidget(lbl_preview_title)

        self.browser_preview = QTextBrowser(right_box)
        self.browser_preview.setStyleSheet("border: 1px solid #e5e5ea; border-radius: 8px; padding: 12px; background: #ffffff;")
        rbl_layout.addWidget(self.browser_preview)
        editor_splitter.addWidget(right_box)

        editor_splitter.setSizes([500, 500])
        layout.addWidget(editor_splitter)

        return container

    # ── View 3: Git DAG Graph View (Developer Mode) ───────────────────────────

    def _create_graph_view(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)

        self.scene_graph = QGraphicsScene(container)
        self.view_graph_view = QGraphicsView(self.scene_graph, container)
        self.view_graph_view.setRenderHint(self.view_graph_view.renderHints())
        self.view_graph_view.setStyleSheet("background-color: #ffffff; border: 1px solid #e5e5ea; border-radius: 8px;")
        layout.addWidget(self.view_graph_view)

        return container

    # ── Navigation and State Handlers ─────────────────────────────────────────

    def switch_view_mode(self, index: int):
        """Switches the active workspace stack view."""
        for i, btn in enumerate(self.tab_buttons):
            btn.setChecked(i == index)
        self.stack_views.setCurrentIndex(index)

        if index == 0:
            self.render_timeline()
        elif index == 1:
            self.render_review_changes()
        elif index == 2:
            self.load_active_file()
        elif index == 3:
            self.render_dag_graph()

    def _on_dev_mode_toggled(self, checked: bool):
        self.developer_mode = checked
        self.dev_branch_box.setVisible(checked)
        self.dev_staging_box.setVisible(checked)
        self.btn_tab_graph.setVisible(checked)
        self.render_timeline()
        self.render_review_changes()

    def open_notebook_vcs(self, notebook_id: str):
        """Focuses Version History on a specific notebook canvas board."""
        self.active_notebook_id = notebook_id
        target_filename = f"boards/board_{notebook_id}.json"
        
        # Check if this board file exists in the repo
        fpath = os.path.join(self.git_mgr.repo_dir, target_filename)
        if os.path.exists(fpath):
            self.active_filename = target_filename
        else:
            # Fallback to main board
            self.active_filename = "boards/board_main.json"

        self.lbl_active_note.setText(os.path.basename(self.active_filename))
        self.refresh_all()
        self.switch_view_mode(0)

    def refresh_all(self):
        """Refreshes sidebar tree, timeline, and status bar."""
        self.refresh_branches()
        self.refresh_file_tree()
        self.render_timeline()

    def refresh_branches(self):
        self.cb_branches.blockSignals(True)
        self.cb_branches.clear()
        branches = self.git_mgr.get_branches()
        cur = self.git_mgr.get_current_branch()
        for b in branches:
            self.cb_branches.addItem(b, b)
        idx = self.cb_branches.findData(cur)
        if idx >= 0:
            self.cb_branches.setCurrentIndex(idx)
        self.cb_branches.blockSignals(False)

    def refresh_file_tree(self):
        """Renders documents and canvas boards in the left sidebar."""
        self.tree_vcs.clear()
        self.git_mgr.sync_boards_to_repo()
        status_info = self.git_mgr.get_files_status()

        # Canvas Boards Group
        boards_root = QTreeWidgetItem(self.tree_vcs, ["Canvas Boards"])
        boards_root.setIcon(0, qta.icon("fa5s.th-large", color="#7c3aed"))
        boards_root.setExpanded(True)

        # Study Notes Group
        notes_root = QTreeWidgetItem(self.tree_vcs, ["Study Notes"])
        notes_root.setIcon(0, qta.icon("fa5s.book-open", color="#007aff"))
        notes_root.setExpanded(True)

        # Modified files lookup
        uncommitted_files = {it["filename"] for it in status_info.get("unstaged", [])}
        uncommitted_files.update(it["filename"] for it in status_info.get("staged", []))

        for f in status_info.get("all_files", []):
            is_mod = f in uncommitted_files
            display_name = os.path.basename(f)
            if f.endswith(".json"):
                item = QTreeWidgetItem(boards_root, [display_name + (" •" if is_mod else "")])
                item.setIcon(0, qta.icon("fa5s.palette", color="#ff9500" if is_mod else "#6e6e73"))
                item.setData(0, Qt.ItemDataRole.UserRole, f)
            elif f.endswith(".md"):
                item = QTreeWidgetItem(notes_root, [display_name + (" •" if is_mod else "")])
                item.setIcon(0, qta.icon("fa5s.file-alt", color="#ff9500" if is_mod else "#6e6e73"))
                item.setData(0, Qt.ItemDataRole.UserRole, f)

        # Update status bar
        if uncommitted_files:
            self.lbl_status_vcs.setText(f"{len(uncommitted_files)} uncommitted change{'s' if len(uncommitted_files) != 1 else ''}")
            self.lbl_status_vcs.setStyleSheet("color: #ff9500; font-weight: 500;")
        else:
            self.lbl_status_vcs.setText("All changes protected in Version History")
            self.lbl_status_vcs.setStyleSheet("color: #28a745; font-weight: 500;")

    # ── Rendering: Timeline Cards ─────────────────────────────────────────────

    def render_timeline(self):
        """Populates the timeline with clean, human-readable version snapshot cards."""
        # Clear existing cards
        while self.timeline_cards_layout.count() > 1:
            child = self.timeline_cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        snapshots = self.version_service.get_version_history(notebook_id=self.active_notebook_id, limit=50)

        if not snapshots:
            empty_lbl = QLabel("No versions saved yet. Click 'Save Version' above to create your first checkpoint.")
            empty_lbl.setStyleSheet("color: #8e8e93; font-size: 13px; padding: 20px;")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.timeline_cards_layout.insertWidget(0, empty_lbl)
            return

        for snap in snapshots:
            card = self._create_version_card(snap)
            # Insert before stretch
            self.timeline_cards_layout.insertWidget(self.timeline_cards_layout.count() - 1, card)

    def _create_version_card(self, snap: VersionSnapshot) -> QFrame:
        """Constructs a polished, accessible version card."""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e5e5ea;
                border-radius: 10px;
                padding: 12px;
            }
            QFrame:hover {
                border-color: #007aff;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)

        # Top Row: Title + Timestamp + (Optional Dev SHA)
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        lbl_title = QLabel(snap.title)
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1c1c1e;")
        top_row.addWidget(lbl_title)

        if snap.is_backup:
            lbl_backup = QLabel("Safety Backup")
            lbl_backup.setStyleSheet("background-color: #e5e5ea; color: #6e6e73; font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px;")
            top_row.addWidget(lbl_backup)

        top_row.addStretch()

        if self.developer_mode and snap.commit_hash:
            lbl_sha = QLabel(f"[{snap.commit_hash}]")
            lbl_sha.setFont(QFont("Consolas", 10))
            lbl_sha.setStyleSheet("color: #8e8e93;")
            top_row.addWidget(lbl_sha)

        lbl_time = QLabel(snap.relative_time)
        lbl_time.setStyleSheet("font-size: 12px; color: #8e8e93;")
        top_row.addWidget(lbl_time)

        card_layout.addLayout(top_row)

        # Middle: Description
        lbl_desc = QLabel(snap.description)
        lbl_desc.setStyleSheet("font-size: 13px; color: #3a3a3c;")
        lbl_desc.setWordWrap(True)
        card_layout.addWidget(lbl_desc)

        # Bottom Row: Summary Badge + Action Buttons
        bot_row = QHBoxLayout()
        bot_row.setContentsMargins(0, 4, 0, 0)
        bot_row.setSpacing(8)

        lbl_summary = QLabel(snap.changes_summary)
        lbl_summary.setStyleSheet("color: #8e8e93; font-size: 11px;")
        bot_row.addWidget(lbl_summary)

        bot_row.addStretch()

        # Action: Review Changes
        btn_diff = QPushButton("Review Changes", card)
        btn_diff.setIcon(qta.icon("fa5s.exchange-alt", color="#007aff"))
        btn_diff.clicked.connect(lambda checked, s=snap: self._on_card_diff_clicked(s))
        bot_row.addWidget(btn_diff)

        # Action: Create Copy
        btn_copy = QPushButton("Create Copy", card)
        btn_copy.setIcon(qta.icon("fa5s.copy", color="#6e6e73"))
        btn_copy.clicked.connect(lambda checked, s=snap: self._on_card_copy_clicked(s))
        bot_row.addWidget(btn_copy)

        # Action: Restore Version
        btn_restore = QPushButton("Restore Version", card)
        btn_restore.setIcon(qta.icon("fa5s.undo-alt", color="#28a745"))
        btn_restore.clicked.connect(lambda checked, s=snap: self._on_card_restore_clicked(s))
        bot_row.addWidget(btn_restore)

        card_layout.addLayout(bot_row)

        return card

    # ── Rendering: Review Changes ─────────────────────────────────────────────

    def render_review_changes(self, commit_ref: str = "HEAD"):
        """Renders object-level change cards and line diffs."""
        self.lbl_diff_header.setText(f"Review Changes: {os.path.basename(self.active_filename)}")

        diff_info = self.version_service.compare_file_with_head(self.active_filename)

        # 1. Populate Object Change Cards
        while self.obj_changes_layout.count() > 1:
            child = self.obj_changes_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not diff_info.object_changes:
            no_changes = QLabel("No unsaved changes in this document. Everything is saved in Version History.")
            no_changes.setStyleSheet("color: #8e8e93; font-size: 13px; padding: 12px;")
            self.obj_changes_layout.insertWidget(0, no_changes)
        else:
            for obj in diff_info.object_changes:
                row = QFrame()
                row.setStyleSheet("background-color: #f8f9fa; border: 1px solid #e5e5ea; border-radius: 6px; padding: 8px;")
                r_layout = QHBoxLayout(row)
                r_layout.setContentsMargins(8, 6, 8, 6)
                r_layout.setSpacing(10)

                icon_lbl = QLabel(row)
                icon_lbl.setPixmap(qta.icon(obj.icon, color=obj.badge_color).pixmap(16, 16))
                r_layout.addWidget(icon_lbl)

                text_vbox = QVBoxLayout()
                text_vbox.setSpacing(2)
                t_lbl = QLabel(obj.title, row)
                t_lbl.setStyleSheet("font-weight: 600; font-size: 12px; color: #1c1c1e;")
                d_lbl = QLabel(obj.description, row)
                d_lbl.setStyleSheet("font-size: 11px; color: #6e6e73;")
                text_vbox.addWidget(t_lbl)
                text_vbox.addWidget(d_lbl)
                r_layout.addLayout(text_vbox, 1)

                badge = QLabel(obj.action.value.upper(), row)
                badge.setStyleSheet(f"background-color: {obj.badge_color}; color: white; font-weight: bold; font-size: 9px; padding: 2px 6px; border-radius: 4px;")
                r_layout.addWidget(badge)

                self.obj_changes_layout.insertWidget(self.obj_changes_layout.count() - 1, row)

        # 2. Populate Line Diff
        html_lines = []
        for line in diff_info.lines:
            t = line.get("type", "same")
            txt = html.escape(line.get("text", ""))
            if t == "add":
                html_lines.append(f"<div style='background-color:#e6ffec; color:#1a7f37; font-family:Consolas;'>+ {txt}</div>")
            elif t == "del":
                html_lines.append(f"<div style='background-color:#ffebe9; color:#cf222e; font-family:Consolas;'>- {txt}</div>")
            else:
                html_lines.append(f"<div style='color:#57606a; font-family:Consolas;'>  {txt}</div>")

        if not html_lines:
            self.diff_text_browser.setHtml("<div style='color:#8e8e93; font-family:Consolas;'>No line differences.</div>")
        else:
            self.diff_text_browser.setHtml("".join(html_lines))

    # ── Rendering: DAG Graph ──────────────────────────────────────────────────

    def render_dag_graph(self):
        """Renders technical commit graph for Developer Mode."""
        self.scene_graph.clear()
        commits = self.git_mgr.get_commit_history()

        y = 20
        for i, commit in enumerate(commits):
            self.scene_graph.addEllipse(30, y, 16, 16, QPen(QColor("#ffffff")), QBrush(QColor("#007aff" if i == 0 else "#28a745")))
            if i < len(commits) - 1:
                self.scene_graph.addLine(38, y + 16, 38, y + 60, QPen(QColor("#007aff"), 2))

            title = self.scene_graph.addText(f"[{commit['hash']}] {commit['message']}")
            title.setPos(60, y - 2)
            title.setDefaultTextColor(QColor("#1c1c1e"))
            font = title.font()
            font.setBold(True)
            title.setFont(font)

            meta = self.scene_graph.addText(f"Author: {commit['author']} • {commit['date']}")
            meta.setPos(60, y + 16)
            meta.setDefaultTextColor(QColor("#6e6e73"))

            y += 60

    # ── Notes Editor & Preview ────────────────────────────────────────────────

    def load_active_file(self):
        """Loads active note content into editor."""
        self.lbl_active_note.setText(os.path.basename(self.active_filename))
        content = self.git_mgr.get_file_content(self.active_filename)
        self.txt_editor.blockSignals(True)
        self.txt_editor.setPlainText(content)
        self.txt_editor.blockSignals(False)
        self._update_preview(content)

    def _on_editor_text_changed(self):
        content = self.txt_editor.toPlainText()
        self.git_mgr.save_file_content(self.active_filename, content)
        self._update_preview(content)

    def _update_preview(self, markdown_text: str):
        # Basic markdown to HTML conversion for live preview
        escaped = html.escape(markdown_text)
        rendered = re.sub(r'^# (.+)$', r'<h1 style="color:#007aff; font-family:sans-serif;">\1</h1>', escaped, flags=re.MULTILINE)
        rendered = re.sub(r'^## (.+)$', r'<h2 style="color:#1c1c1e; font-family:sans-serif;">\1</h2>', rendered, flags=re.MULTILINE)
        rendered = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', rendered)
        rendered = rendered.replace("\n", "<br>")
        self.browser_preview.setHtml(rendered)

    # ── Event Handlers & User Actions ─────────────────────────────────────────

    def _on_tree_item_clicked(self, item, col):
        fname = item.data(0, Qt.ItemDataRole.UserRole)
        if fname and isinstance(fname, str):
            self.active_filename = fname
            self.lbl_active_note.setText(os.path.basename(fname))
            if self.stack_views.currentIndex() == 1:
                self.render_review_changes()
            elif self.stack_views.currentIndex() == 2:
                self.load_active_file()

    def _on_save_version_clicked(self):
        """Prompts the user for a description and creates a safe version checkpoint."""
        desc, ok = QInputDialog.getText(
            self,
            "Save Version",
            "Describe the work completed in this version:",
            text="Completed study session"
        )
        if not ok:
            return

        try:
            snapshot = self.version_service.save_version(
                description=desc.strip(),
                notebook_id=self.active_notebook_id
            )
            QMessageBox.information(
                self,
                "Version Saved",
                f"{snapshot.title} successfully saved!\n\"{snapshot.description}\""
            )
            self.refresh_all()
        except Exception as e:
            QMessageBox.warning(self, "Save Error", str(e))

    def _on_card_restore_clicked(self, snap: VersionSnapshot):
        """Safely restores a previous version non-destructively."""
        reply = QMessageBox.question(
            self,
            f"Restore {snap.title}",
            f"Are you sure you want to restore {snap.title} (\"{snap.description}\")?\n\n"
            "This operation is safe and non-destructive. Kestrel will automatically create a "
            "backup of your current work before restoring.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            res = self.version_service.restore_version(snap.version_id, create_backup=True)
            QMessageBox.information(
                self,
                "Version Restored",
                f"{snap.title} was successfully restored!\n\n"
                f"A safety backup ({res.get('backup_version', 'backup')}) of your previous state "
                "was automatically saved."
            )
            self.refresh_all()
            self.version_restored.emit(snap.version_id)
        except Exception as e:
            QMessageBox.warning(self, "Restore Error", str(e))

    def _on_card_diff_clicked(self, snap: VersionSnapshot):
        """Switches to Review Changes tab comparing with this snapshot."""
        self.switch_view_mode(1)
        self.render_review_changes(snap.version_id)

    def _on_card_copy_clicked(self, snap: VersionSnapshot):
        """Prompts to create a copy from a specific version snapshot."""
        name, ok = QInputDialog.getText(
            self,
            "Create Copy",
            f"Enter a name for the copy of {snap.title}:",
            text=f"Copy_of_{snap.title.replace(' ', '_')}"
        )
        if ok and name.strip():
            try:
                copy_name = self.version_service.create_copy(snap.version_id, name.strip())
                QMessageBox.information(
                    self,
                    "Copy Created",
                    f"Created copy '{copy_name}' from {snap.title}."
                )
                self.refresh_all()
            except Exception as e:
                QMessageBox.warning(self, "Copy Error", str(e))

    def _on_stage_all(self):
        self.git_mgr.stage_all()
        self.refresh_file_tree()

    def _on_unstage_all(self):
        self.git_mgr.unstage_all()
        self.refresh_file_tree()

    def _on_branch_changed(self, idx):
        bname = self.cb_branches.itemData(idx)
        if bname and bname != self.git_mgr.get_current_branch():
            self.git_mgr.switch_branch(bname)
            self.refresh_all()

    def _on_new_branch_clicked(self):
        name, ok = QInputDialog.getText(self, "New Branch", "Enter branch name:")
        if ok and name.strip():
            if self.git_mgr.create_branch(name.strip()):
                self.git_mgr.switch_branch(name.strip())
                self.refresh_all()

    def _on_new_note_clicked(self):
        name, ok = QInputDialog.getText(self, "New Study Note", "Enter note filename (e.g. biology_cell_cycle.md):")
        if ok and name.strip():
            created = self.git_mgr.create_new_note(name.strip())
            self.active_filename = created
            self.refresh_all()
            self.switch_view_mode(2)


# Backward Compatibility Alias:
GitNotesPanel = VersionHistoryPanel
