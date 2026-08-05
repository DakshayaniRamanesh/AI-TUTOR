"""
Git Notes Panel - Native PyQt6 Source Control View for Notes & All Boards (Light Theme)
Implements Source Control Sidebar, Staging Tree, Markdown & Freeform Canvas Board Editor,
Side-by-Side Line Diff Viewer, Interactive Git DAG Tree Graph, and Commit History.
"""

import os
import html
import json
import re
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QTreeWidget, QTreeWidgetItem,
    QTextEdit, QTextBrowser, QPushButton, QComboBox, QLabel, QFrame, QStackedWidget,
    QPlainTextEdit, QCheckBox, QInputDialog, QMessageBox, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem, QGraphicsRectItem, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QBrush, QPen, QIcon
import qtawesome as qta

from ...backend.version_control.git_notes_manager import GitNotesManager

class GitNotesPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.git_mgr = GitNotesManager()
        self.active_filename = "physics_quantum_notes.md"
        self._init_ui()
        self.refresh_all()

    def _init_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Main Horizontal Splitter (Sidebar ~280px + Workspace)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #d1d1d6; }")

        # 1. Left Source Control Sidebar
        sidebar_widget = self._create_sidebar()
        self.splitter.addWidget(sidebar_widget)

        # 2. Right Workspace Container
        workspace_widget = self._create_workspace()
        self.splitter.addWidget(workspace_widget)

        self.splitter.setSizes([280, 1000])
        root_layout.addWidget(self.splitter)

        self._apply_light_theme()

    def _create_sidebar(self) -> QWidget:
        sb = QWidget(self)
        sb.setFixedWidth(280)
        sb.setObjectName("GitSidebar")
        layout = QVBoxLayout(sb)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Branch Header & Selector
        branch_box = QWidget(sb)
        bb_layout = QHBoxLayout(branch_box)
        bb_layout.setContentsMargins(0, 0, 0, 0)
        
        lbl_branch_icon = QLabel(sb)
        lbl_branch_icon.setPixmap(qta.icon('fa5s.code-branch', color='#28a745').pixmap(14, 14))
        bb_layout.addWidget(lbl_branch_icon)

        self.cb_branches = QComboBox(sb)
        self.cb_branches.currentIndexChanged.connect(self._on_branch_changed)
        bb_layout.addWidget(self.cb_branches, 1)

        btn_new_branch = QPushButton("+ Branch", sb)
        btn_new_branch.clicked.connect(self._on_new_branch_clicked)
        bb_layout.addWidget(btn_new_branch)

        layout.addWidget(branch_box)

        # Section Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #d1d1d6;")
        layout.addWidget(line)

        # Source Control Staging Header
        sc_header = QWidget(sb)
        sch_layout = QHBoxLayout(sc_header)
        sch_layout.setContentsMargins(0, 0, 0, 0)

        lbl_sc_title = QLabel("SOURCE CONTROL", sb)
        lbl_sc_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #6e6e73;")
        sch_layout.addWidget(lbl_sc_title)

        sch_layout.addStretch()

        btn_stage_all = QPushButton("+ Stage All", sb)
        btn_stage_all.clicked.connect(self._on_stage_all)
        sch_layout.addWidget(btn_stage_all)

        btn_unstage_all = QPushButton("- Unstage All", sb)
        btn_unstage_all.clicked.connect(self._on_unstage_all)
        sch_layout.addWidget(btn_unstage_all)

        layout.addWidget(sc_header)

        # Commit Input Box
        self.txt_commit_msg = QPlainTextEdit(sb)
        self.txt_commit_msg.setPlaceholderText("Commit message (Ctrl+Enter to commit)")
        self.txt_commit_msg.setFixedHeight(55)
        layout.addWidget(self.txt_commit_msg)

        commit_opts = QWidget(sb)
        co_layout = QHBoxLayout(commit_opts)
        co_layout.setContentsMargins(0, 0, 0, 0)

        self.chk_amend = QCheckBox("Amend last commit", sb)
        co_layout.addWidget(self.chk_amend)

        layout.addWidget(commit_opts)

        self.btn_commit = QPushButton("✓ Commit", sb)
        self.btn_commit.setStyleSheet("""
            QPushButton {
                background-color: #007aff;
                color: white;
                font-weight: bold;
                padding: 6px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        self.btn_commit.clicked.connect(self._on_commit_clicked)
        layout.addWidget(self.btn_commit)

        # Tree Widget for Staged / Unstaged / Repo Files
        self.tree_vcs = QTreeWidget(sb)
        self.tree_vcs.setHeaderHidden(True)
        self.tree_vcs.itemClicked.connect(self._on_tree_item_clicked)
        layout.addWidget(self.tree_vcs, 1)

        # New Note Button
        btn_new_note = QPushButton("✎ New Note (.md)", sb)
        btn_new_note.clicked.connect(self._on_new_note_clicked)
        layout.addWidget(btn_new_note)

        return sb

    def _create_workspace(self) -> QWidget:
        ws = QWidget(self)
        layout = QVBoxLayout(ws)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top Mode Navigation Bar
        nav_bar = QWidget(ws)
        nav_bar.setFixedHeight(42)
        nav_bar.setStyleSheet("background-color: #f2f2f7; border-bottom: 1px solid #d1d1d6;")
        nb_layout = QHBoxLayout(nav_bar)
        nb_layout.setContentsMargins(12, 0, 12, 0)
        nb_layout.setSpacing(6)

        self.btn_tab_editor = QPushButton("✎ Editor & Live Preview", nav_bar)
        self.btn_tab_diff = QPushButton("⇄ Visual Line Diff", nav_bar)
        self.btn_tab_graph = QPushButton("⎇ Git DAG Graph", nav_bar)
        self.btn_tab_history = QPushButton("⏱ Commit History", nav_bar)

        for btn in [self.btn_tab_editor, self.btn_tab_diff, self.btn_tab_graph, self.btn_tab_history]:
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #6e6e73;
                    border: none;
                    font-weight: 600;
                    padding: 8px 14px;
                    border-bottom: 2px solid transparent;
                }
                QPushButton:checked {
                    color: #007aff;
                    border-bottom: 2px solid #007aff;
                }
                QPushButton:hover {
                    color: #1c1c1e;
                }
            """)

        self.btn_tab_editor.setChecked(True)
        self.btn_tab_editor.clicked.connect(lambda: self.switch_view_mode(0))
        self.btn_tab_diff.clicked.connect(lambda: self.switch_view_mode(1))
        self.btn_tab_graph.clicked.connect(lambda: self.switch_view_mode(2))
        self.btn_tab_history.clicked.connect(lambda: self.switch_view_mode(3))

        nb_layout.addWidget(self.btn_tab_editor)
        nb_layout.addWidget(self.btn_tab_diff)
        nb_layout.addWidget(self.btn_tab_graph)
        nb_layout.addWidget(self.btn_tab_history)
        nb_layout.addStretch()

        self.lbl_active_note = QLabel(self.active_filename, nav_bar)
        self.lbl_active_note.setStyleSheet("color: #007aff; font-weight: bold; font-size: 13px;")
        nb_layout.addWidget(self.lbl_active_note)

        layout.addWidget(nav_bar)

        # Workspace Stacked Widget
        self.stack_views = QStackedWidget(ws)

        # View Mode 0: Editor & Live Preview
        self.view_editor = self._create_editor_view()
        self.stack_views.addWidget(self.view_editor)

        # View Mode 1: Visual Line Diff Viewer
        self.view_diff = self._create_diff_view()
        self.stack_views.addWidget(self.view_diff)

        # View Mode 2: Interactive Git DAG Tree Graph
        self.view_graph = self._create_graph_view()
        self.stack_views.addWidget(self.view_graph)

        # View Mode 3: Commit History List
        self.view_history = self._create_history_view()
        self.stack_views.addWidget(self.view_history)

        layout.addWidget(self.stack_views)

        # Bottom Status Bar
        status_bar = QWidget(ws)
        status_bar.setFixedHeight(26)
        status_bar.setStyleSheet("background-color: #f2f2f7; border-top: 1px solid #d1d1d6; color: #6e6e73; font-size: 11px;")
        sb_layout = QHBoxLayout(status_bar)
        sb_layout.setContentsMargins(12, 0, 12, 0)

        self.lbl_status_git = QLabel("✓ Working tree clean", status_bar)
        self.lbl_status_git.setStyleSheet("color: #28a745; font-weight: 500;")
        sb_layout.addWidget(self.lbl_status_git)

        sb_layout.addStretch()
        self.lbl_status_words = QLabel("0 items", status_bar)
        sb_layout.addWidget(self.lbl_status_words)

        layout.addWidget(status_bar)

        return ws

    def _create_editor_view(self) -> QWidget:
        v = QWidget(self)
        v_layout = QVBoxLayout(v)
        v_layout.setContentsMargins(0, 0, 0, 0)
        v_layout.setSpacing(0)

        # Formatting Toolbar
        toolbar = QWidget(v)
        toolbar.setFixedHeight(36)
        toolbar.setStyleSheet("background-color: #f8f8fa; border-bottom: 1px solid #d1d1d6;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(8, 0, 8, 0)
        tb_layout.setSpacing(4)

        tb_actions = [
            ("Bold", "**", "**"), ("Italic", "*", "*"), ("H1", "# ", ""), ("H2", "## ", ""),
            ("Code", "```python\n", "\n```"), ("Math", "$$\n", "\n$$"),
            ("Checklist", "- [ ] ", ""), ("Table", "\n| A | B |\n| --- | --- |\n| 1 | 2 |\n", "")
        ]

        for title, p, s in tb_actions:
            btn = QPushButton(title, toolbar)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    color: #1c1c1e;
                    border: 1px solid #d1d1d6;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #e5e5ea;
                }
            """)
            btn.clicked.connect(lambda _, prefix=p, suffix=s: self._insert_formatting(prefix, suffix))
            tb_layout.addWidget(btn)

        tb_layout.addStretch()
        v_layout.addWidget(toolbar)

        # Splitter: Markdown Source TextEdit + HTML Live Preview
        split_editor = QSplitter(Qt.Orientation.Horizontal)

        self.txt_source = QTextEdit(v)
        self.txt_source.setFont(QFont("Fira Code", 11))
        self.txt_source.setPlaceholderText("Write your note here in Markdown...")
        self.txt_source.setStyleSheet("background-color: #ffffff; color: #1c1c1e; padding: 12px; border: none;")
        self.txt_source.textChanged.connect(self._on_source_edited)
        split_editor.addWidget(self.txt_source)

        self.browser_preview = QTextBrowser(v)
        self.browser_preview.setStyleSheet("background-color: #fafafa; padding: 16px; border-left: 1px solid #d1d1d6;")
        split_editor.addWidget(self.browser_preview)

        split_editor.setSizes([500, 500])
        v_layout.addWidget(split_editor)

        return v

    def _create_diff_view(self) -> QWidget:
        v = QWidget(self)
        v_layout = QVBoxLayout(v)
        v_layout.setContentsMargins(0, 0, 0, 0)

        self.browser_diff = QTextBrowser(v)
        self.browser_diff.setFont(QFont("Fira Code", 11))
        self.browser_diff.setStyleSheet("background-color: #ffffff; padding: 12px;")
        v_layout.addWidget(self.browser_diff)

        return v

    def _create_graph_view(self) -> QWidget:
        v = QWidget(self)
        v_layout = QVBoxLayout(v)
        v_layout.setContentsMargins(0, 0, 0, 0)

        self.scene_graph = QGraphicsScene(v)
        self.view_graph_canvas = QGraphicsView(self.scene_graph, v)
        self.view_graph_canvas.setStyleSheet("background-color: #f8f9fa; border: none;")
        v_layout.addWidget(self.view_graph_canvas)

        return v

    def _create_history_view(self) -> QWidget:
        v = QWidget(self)
        v_layout = QVBoxLayout(v)
        v_layout.setContentsMargins(12, 12, 12, 12)

        self.list_history = QListWidget(v)
        self.list_history.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 8px;
                color: #1c1c1e;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #e5e5ea;
            }
        """)
        v_layout.addWidget(self.list_history)

        return v

    def _apply_light_theme(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                color: #1c1c1e;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }
            QWidget#GitSidebar {
                background-color: #f8f8fa;
                border-right: 1px solid #d1d1d6;
            }
            QTreeWidget {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 6px;
                color: #1c1c1e;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:selected {
                background-color: #007aff;
                color: white;
            }
            QPlainTextEdit, QTextEdit, QComboBox {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 6px;
                color: #1c1c1e;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 6px;
                color: #1c1c1e;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #e5e5ea;
            }
        """)

    def switch_view_mode(self, index: int):
        self.btn_tab_editor.setChecked(index == 0)
        self.btn_tab_diff.setChecked(index == 1)
        self.btn_tab_graph.setChecked(index == 2)
        self.btn_tab_history.setChecked(index == 3)

        self.stack_views.setCurrentIndex(index)

        if index == 1:
            self.render_diff_view()
        elif index == 2:
            self.render_git_graph()
        elif index == 3:
            self.render_commit_history()

    # --- Actions & Logic ---
    def open_notebook_vcs(self, notebook_id: str):
        """Switches to the requested notebook board file or notes file in Git VCS."""
        self.refresh_all()
        status = self.git_mgr.get_files_status()

        target_file = None
        for f in status['all_files']:
            if notebook_id in f:
                target_file = f
                break

        if not target_file:
            board_files = [f for f in status['all_files'] if f.endswith(".json")]
            target_file = board_files[0] if board_files else "physics_quantum_notes.md"

        self.active_filename = target_file
        self.load_active_file()
        self.switch_view_mode(2) # Open Git DAG Graph view

    def refresh_all(self):
        self.git_mgr.sync_boards_to_repo()
        self.refresh_branches()
        self.refresh_file_tree()
        self.load_active_file()

    def refresh_branches(self):
        self.cb_branches.blockSignals(True)
        self.cb_branches.clear()

        branches = self.git_mgr.get_branches()
        current = self.git_mgr.get_current_branch()

        for b in branches:
            self.cb_branches.addItem(f"⎇ {b}", b)

        idx = self.cb_branches.findData(current)
        if idx >= 0:
            self.cb_branches.setCurrentIndex(idx)
        self.cb_branches.blockSignals(False)

    def refresh_file_tree(self):
        self.tree_vcs.clear()
        status = self.git_mgr.get_files_status()

        # 1. Staged Changes
        staged_group = QTreeWidgetItem(self.tree_vcs, [f"⤓ Staged Changes ({len(status['staged'])})"])
        staged_group.setExpanded(True)
        for f in status['staged']:
            icon = "❖" if f['filename'].endswith(".json") else "🗎"
            item = QTreeWidgetItem(staged_group, [f"  {icon} {f['filename']}"])
            item.setData(0, Qt.ItemDataRole.UserRole, ("staged", f['filename']))
            item.setForeground(0, QBrush(QColor("#28a745")))

        # 2. Unstaged Changes
        unstaged_group = QTreeWidgetItem(self.tree_vcs, [f"✎ Unstaged Changes ({len(status['unstaged'])})"])
        unstaged_group.setExpanded(True)
        for f in status['unstaged']:
            icon = "❖" if f['filename'].endswith(".json") else "🗎"
            item = QTreeWidgetItem(unstaged_group, [f"  [{f['status']}] {icon} {f['filename']}"])
            item.setData(0, Qt.ItemDataRole.UserRole, ("unstaged", f['filename']))
            item.setForeground(0, QBrush(QColor("#d97706" if f['status'] == "M" else "#6e6e73")))

        # 3. Notes (.md) vs Freeform Canvas Boards (.json)
        md_files = [f for f in status['all_files'] if f.endswith(".md")]
        board_files = [f for f in status['all_files'] if f.endswith(".json")]

        md_group = QTreeWidgetItem(self.tree_vcs, [f"✎ Markdown Notes ({len(md_files)})"])
        md_group.setExpanded(True)
        for fname in md_files:
            item = QTreeWidgetItem(md_group, [f"  🗎 {fname}"])
            item.setData(0, Qt.ItemDataRole.UserRole, ("file", fname))

        board_group = QTreeWidgetItem(self.tree_vcs, [f"❖ Freeform Canvas Boards ({len(board_files)})"])
        board_group.setExpanded(True)
        for fname in board_files:
            item = QTreeWidgetItem(board_group, [f"  ❖ {fname}"])
            item.setData(0, Qt.ItemDataRole.UserRole, ("file", fname))

        # Update status labels
        total_changes = len(status['staged']) + len(status['unstaged'])
        if total_changes > 0:
            self.lbl_status_git.setText(f"● {total_changes} uncommitted changes")
            self.lbl_status_git.setStyleSheet("color: #d97706; font-weight: bold;")
        else:
            self.lbl_status_git.setText("✓ Working tree clean")
            self.lbl_status_git.setStyleSheet("color: #28a745;")

    def load_active_file(self):
        content = self.git_mgr.get_file_content(self.active_filename)
        self.txt_source.blockSignals(True)
        self.txt_source.setText(content)
        self.txt_source.blockSignals(False)

        self.lbl_active_note.setText(self.active_filename)
        self.render_markdown_preview(content)

    def _on_source_edited(self):
        text = self.txt_source.toPlainText()
        self.git_mgr.save_file_content(self.active_filename, text)
        self.render_markdown_preview(text)
        self.refresh_file_tree()

    def render_markdown_preview(self, text: str):
        if self.active_filename.endswith(".json"):
            # Board JSON summary view
            try:
                payload = json.loads(text)
                title = payload.get("title", "Freeform Board")
                items = payload.get("items", [])
                
                html_out = [
                    f"<h1 style='color:#007aff;'>🎨 Freeform Canvas Board: {html.escape(title)}</h1>",
                    f"<p style='color:#6e6e73;'><b>Board ID:</b> {payload.get('board_id','')} &nbsp;|&nbsp; <b>Total Workspace Items:</b> {len(items)}</p>",
                    "<hr style='border:none; border-top:1px solid #d1d1d6;'>",
                    "<h3>Workspace Items Summary:</h3><ul>"
                ]

                for item in items:
                    itype = item.get("type", "item").replace("_", " ").title()
                    itext = item.get("text") or item.get("title") or item.get("question") or ""
                    html_out.append(f"<li><b>{itype}</b>: <span>{html.escape(str(itext)[:80])}</span></li>")

                html_out.append("</ul>")
                self.browser_preview.setHtml("\n".join(html_out))
                self.lbl_status_words.setText(f"{len(items)} items")
                return
            except Exception:
                pass

        # Standard Markdown preview
        html_content = self._markdown_to_html(text)
        self.browser_preview.setHtml(f"""
            <html>
            <head>
            <style>
                body {{ font-family: -apple-system, sans-serif; color: #1c1c1e; line-height: 1.6; background-color: #fafafa; }}
                h1 {{ color: #000000; border-bottom: 1px solid #d1d1d6; padding-bottom: 6px; }}
                h2 {{ color: #007aff; margin-top: 16px; }}
                code {{ background-color: #e5e5ea; color: #d9381e; padding: 2px 6px; border-radius: 4px; font-family: monospace; }}
                pre {{ background-color: #f2f2f7; border: 1px solid #d1d1d6; padding: 12px; border-radius: 6px; font-family: monospace; color: #1c1c1e; }}
                blockquote {{ border-left: 4px solid #007aff; padding-left: 12px; color: #6e6e73; font-style: italic; }}
                .math {{ color: #b45309; font-family: math, serif; font-weight: bold; background-color: rgba(217,119,6,0.1); padding: 2px 4px; border-radius: 3px; }}
            </style>
            </head>
            <body>{html_content}</body>
            </html>
        """)

        words = len(re.findall(r'\w+', text))
        self.lbl_status_words.setText(f"{words} words")

    def _markdown_to_html(self, text: str) -> str:
        lines = text.split("\n")
        out = []
        in_code = False

        for line in lines:
            escaped = html.escape(line)

            if escaped.startswith("```"):
                if in_code:
                    out.append("</pre>")
                    in_code = False
                else:
                    out.append("<pre><code>")
                    in_code = True
                continue

            if in_code:
                out.append(escaped)
                continue

            if escaped.startswith("# "):
                out.append(f"<h1>{escaped[2:]}</h1>")
            elif escaped.startswith("## "):
                out.append(f"<h2>{escaped[3:]}</h2>")
            elif escaped.startswith("### "):
                out.append(f"<h3>{escaped[4:]}</h3>")
            elif escaped.startswith("- [ ] "):
                out.append(f"<p><input type='checkbox' disabled> {escaped[6:]}</p>")
            elif escaped.startswith("- [x] "):
                out.append(f"<p><input type='checkbox' checked disabled> {escaped[6:]}</p>")
            elif escaped.startswith("- "):
                out.append(f"<ul><li>{escaped[2:]}</li></ul>")
            elif escaped.strip():
                fmt = re.sub(r'\$([^\$]+)\$', r'<span class="math">\1</span>', escaped)
                out.append(f"<p>{fmt}</p>")

        return "\n".join(out)

    def _insert_formatting(self, prefix: str, suffix: str):
        cursor = self.txt_source.textCursor()
        selected = cursor.selectedText() or "text"
        cursor.insertText(f"{prefix}{selected}{suffix}")
        self.txt_source.setFocus()

    def render_diff_view(self):
        diff_data = self.git_mgr.get_diff(self.active_filename)
        html_lines = [
            f"<h3 style='color:#1c1c1e;'>Diff comparison for <b>{self.active_filename}</b> against HEAD</h3>",
            f"<p><span style='color:#1a7f37; font-weight:bold;'>+{diff_data['additions']} additions</span> | <span style='color:#cf222e; font-weight:bold;'>-{diff_data['deletions']} deletions</span></p>",
            "<table style='width:100%; border-collapse:collapse; font-family:monospace; font-size:13px;'>"
        ]

        for line in diff_data["lines"]:
            ltype = line["type"]
            bg = "#ffffff"
            color = "#1c1c1e"
            sym = "&nbsp;"

            if ltype == "add":
                bg = "#e6ffec"
                color = "#1a7f37"
                sym = "+"
            elif ltype == "del":
                bg = "#ffebe9"
                color = "#cf222e"
                sym = "-"

            html_lines.append(f"""
                <tr style='background-color:{bg}; color:{color};'>
                    <td style='width:40px; text-align:right; color:#8c959f; border-right:1px solid #d1d1d6; padding:2px 6px;'>{line['old_num']}</td>
                    <td style='width:40px; text-align:right; color:#8c959f; border-right:1px solid #d1d1d6; padding:2px 6px;'>{line['new_num']}</td>
                    <td style='width:20px; text-align:center; font-weight:bold;'>{sym}</td>
                    <td style='padding:2px 8px; white-space:pre-wrap;'>{html.escape(line['text'])}</td>
                </tr>
            """)

        html_lines.append("</table>")
        self.browser_diff.setHtml("\n".join(html_lines))

    def render_git_graph(self):
        self.scene_graph.clear()
        commits = self.git_mgr.get_commit_history()

        y = 30
        for i, commit in enumerate(commits):
            ellipse = self.scene_graph.addEllipse(30, y, 16, 16, QPen(QColor("#ffffff")), QBrush(QColor("#007aff" if i == 0 else "#28a745")))
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

    def render_commit_history(self):
        self.list_history.clear()
        commits = self.git_mgr.get_commit_history()

        for c in commits:
            item = QListWidgetItem(f"[{c['hash']}] {c['message']}\nAuthor: {c['author']} • {c['date']}")
            self.list_history.addItem(item)

    # --- Tree Event Handlers ---
    def _on_tree_item_clicked(self, item, col):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and isinstance(data, tuple):
            mode, fname = data
            self.active_filename = fname
            self.load_active_file()

    def _on_stage_all(self):
        self.git_mgr.stage_all()
        self.refresh_file_tree()

    def _on_unstage_all(self):
        self.git_mgr.unstage_all()
        self.refresh_file_tree()

    def _on_commit_clicked(self):
        msg = self.txt_commit_msg.toPlainText().strip()
        if not msg:
            QMessageBox.warning(self, "Commit Failed", "Please enter a commit message.")
            return

        try:
            status = self.git_mgr.get_files_status()
            if not status['staged'] and status['unstaged']:
                self.git_mgr.stage_all()

            res = self.git_mgr.commit(msg, self.chk_amend.isChecked())
            self.txt_commit_msg.clear()
            self.chk_amend.setChecked(False)
            QMessageBox.information(self, "Committed", f"Changes committed successfully!\n{res}")
            self.refresh_all()
        except Exception as e:
            QMessageBox.warning(self, "Commit Error", str(e))

    def _on_branch_changed(self, idx):
        bname = self.cb_branches.itemData(idx)
        if bname and bname != self.git_mgr.get_current_branch():
            self.git_mgr.switch_branch(bname)
            self.refresh_all()

    def _on_new_branch_clicked(self):
        name, ok = QInputDialog.getText(self, "New Git Branch", "Enter branch name:")
        if ok and name.strip():
            if self.git_mgr.create_branch(name.strip()):
                self.git_mgr.switch_branch(name.strip())
                self.refresh_all()

    def _on_new_note_clicked(self):
        name, ok = QInputDialog.getText(self, "New Markdown Note", "Enter note filename:")
        if ok and name.strip():
            created = self.git_mgr.create_new_note(name.strip())
            self.active_filename = created
            self.refresh_all()
