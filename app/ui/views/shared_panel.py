"""
Shared Collaboration Panel
Native PyQt6 GUI View for managing Asynchronous Contributions,
Simultaneous Live Session Link Sharing (Public/Restricted access), Editor-Only simulation,
and Git-backed Conflict Resolution.
"""

import html
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QRadioButton, QComboBox, QLineEdit, QGroupBox,
    QStackedWidget, QTextBrowser, QMessageBox, QFrame, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from ...backend.collaboration_manager import CollaborationManager
from ...backend.git_notes_manager import GitNotesManager
from .editor_only_window import EditorOnlyWindow

class SharedPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.git_mgr = GitNotesManager()
        self.collab_mgr = CollaborationManager(self.git_mgr)
        self.editor_window = None
        self.active_contrib = None
        self.active_conflict = None

        self._init_ui()
        self.refresh_all()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # Header Title Bar
        header = QWidget(self)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)

        lbl_title = QLabel("☌ Shared Collaboration Hub", header)
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1c1c1e;")
        h_layout.addWidget(lbl_title)

        h_layout.addStretch()
        root_layout.addWidget(header)

        # Top Tab Switcher
        nav_bar = QWidget(self)
        nb_layout = QHBoxLayout(nav_bar)
        nb_layout.setContentsMargins(0, 0, 0, 0)
        nb_layout.setSpacing(8)

        self.btn_tab_async = QPushButton("⟳ Asynchronous Contributions (Pull Requests)", nav_bar)
        self.btn_tab_simul = QPushButton("⚡ Simultaneous Live Session & Link Sharing", nav_bar)

        for btn in [self.btn_tab_async, self.btn_tab_simul]:
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f2f2f7;
                    color: #6e6e73;
                    border: 1px solid #d1d1d6;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-weight: 600;
                    font-size: 13px;
                }
                QPushButton:checked {
                    background-color: #007aff;
                    color: white;
                    border-color: #007aff;
                }
                QPushButton:hover:!checked {
                    background-color: #e5e5ea;
                }
            """)

        self.btn_tab_async.setChecked(True)
        self.btn_tab_async.clicked.connect(lambda: self.switch_tab(0))
        self.btn_tab_simul.clicked.connect(lambda: self.switch_tab(1))

        nb_layout.addWidget(self.btn_tab_async)
        nb_layout.addWidget(self.btn_tab_simul)
        nb_layout.addStretch()

        root_layout.addWidget(nav_bar)

        # Main Stacked Widget
        self.stack_pages = QStackedWidget(self)

        # Page 0: Asynchronous Contributions
        self.page_async = self._create_async_page()
        self.stack_pages.addWidget(self.page_async)

        # Page 1: Simultaneous Live Session & Links
        self.page_simul = self._create_simul_page()
        self.stack_pages.addWidget(self.page_simul)

        root_layout.addWidget(self.stack_pages, 1)
        self._apply_theme()

    def _create_async_page(self) -> QWidget:
        w = QWidget(self)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background-color: #d1d1d6; }")

        # Left Column: List of Contributor Branches
        left_box = QGroupBox("Incoming Contributions (Pull Requests)", w)
        lbl_layout = QVBoxLayout(left_box)

        self.list_contribs = QListWidget(left_box)
        self.list_contribs.itemClicked.connect(self._on_contrib_item_clicked)
        lbl_layout.addWidget(self.list_contribs)

        btn_refresh_contribs = QPushButton("⟳ Refresh Contributions", left_box)
        btn_refresh_contribs.clicked.connect(self.refresh_contributions)
        lbl_layout.addWidget(btn_refresh_contribs)

        splitter.addWidget(left_box)

        # Right Column: Contribution Review & Diff Panel
        right_box = QGroupBox("Contribution Review & Diff", w)
        rb_layout = QVBoxLayout(right_box)

        self.lbl_contrib_meta = QLabel("Select a contribution to review diffs and merge.", right_box)
        self.lbl_contrib_meta.setStyleSheet("font-size: 13px; font-weight: bold; color: #007aff;")
        rb_layout.addWidget(self.lbl_contrib_meta)

        self.browser_contrib_diff = QTextBrowser(right_box)
        self.browser_contrib_diff.setFont(QFont("Fira Code", 11))
        self.browser_contrib_diff.setStyleSheet("background-color: #ffffff; padding: 12px; border: 1px solid #d1d1d6; border-radius: 6px;")
        rb_layout.addWidget(self.browser_contrib_diff, 1)

        self.btn_merge_contrib = QPushButton("⎇ Merge Contribution into Main", right_box)
        self.btn_merge_contrib.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 6px;
                font-size: 13px;
                border: none;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        self.btn_merge_contrib.setEnabled(False)
        self.btn_merge_contrib.clicked.connect(self._on_merge_contrib_clicked)
        rb_layout.addWidget(self.btn_merge_contrib)

        splitter.addWidget(right_box)

        splitter.setSizes([320, 680])
        layout.addWidget(splitter)
        return w

    def _create_simul_page(self) -> QWidget:
        w = QWidget(self)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)

        # Section 1: Share Link Generator & Access Control
        link_box = QGroupBox("1. Shareable Link Generator (Editor-Only Access)", w)
        lb_layout = QVBoxLayout(link_box)
        lb_layout.setSpacing(8)

        row1 = QWidget(link_box)
        r1_layout = QHBoxLayout(row1)
        r1_layout.setContentsMargins(0, 0, 0, 0)

        r1_layout.addWidget(QLabel("Select Note to Share:"))
        self.cb_notes_to_share = QComboBox(row1)
        r1_layout.addWidget(self.cb_notes_to_share, 1)

        btn_gen_link = QPushButton("⚡ Generate Link", row1)
        btn_gen_link.setStyleSheet("background-color: #007aff; color: white; font-weight: bold;")
        btn_gen_link.clicked.connect(self._on_generate_link_clicked)
        r1_layout.addWidget(btn_gen_link)

        lb_layout.addWidget(row1)

        row2 = QWidget(link_box)
        r2_layout = QHBoxLayout(row2)
        r2_layout.setContentsMargins(0, 0, 0, 0)

        self.txt_share_link = QLineEdit(row2)
        self.txt_share_link.setReadOnly(True)
        self.txt_share_link.setPlaceholderText("Generated share link will appear here...")
        r2_layout.addWidget(self.txt_share_link, 1)

        btn_copy_link = QPushButton("⎘ Copy Link", row2)
        btn_copy_link.clicked.connect(self._on_copy_link_clicked)
        r2_layout.addWidget(btn_copy_link)

        btn_test_editor = QPushButton("⌕ Launch Editor-Only View", row2)
        btn_test_editor.setStyleSheet("background-color: #34c759; color: white; font-weight: bold;")
        btn_test_editor.clicked.connect(self._on_launch_editor_only)
        r2_layout.addWidget(btn_test_editor)

        lb_layout.addWidget(row2)

        # Access Permissions Radio Buttons & Role Settings
        perm_box = QWidget(link_box)
        p_layout = QHBoxLayout(perm_box)
        p_layout.setContentsMargins(0, 0, 0, 0)

        self.rad_public = QRadioButton("⊕ Public (Anyone with link)", perm_box)
        self.rad_public.setChecked(True)
        self.rad_restricted = QRadioButton("☿ Restricted to specified emails", perm_box)

        p_layout.addWidget(self.rad_public)
        p_layout.addWidget(self.rad_restricted)

        p_layout.addStretch()

        p_layout.addWidget(QLabel("Role:"))
        self.cb_role = QComboBox(perm_box)
        self.cb_role.addItems(["✎ Can Edit (Editor-Only)", "⌕ View Only"])
        p_layout.addWidget(self.cb_role)

        lb_layout.addWidget(perm_box)

        row_emails = QWidget(link_box)
        re_layout = QHBoxLayout(row_emails)
        re_layout.setContentsMargins(0, 0, 0, 0)

        re_layout.addWidget(QLabel("Allowed Emails (comma separated):"))
        self.txt_allowed_emails = QLineEdit("alex@edu, sam@mit.edu", row_emails)
        re_layout.addWidget(self.txt_allowed_emails, 1)

        lb_layout.addWidget(row_emails)
        layout.addWidget(link_box)

        # Section 2: Git Conflict Management & Simultaneous Sync
        conflict_box = QGroupBox("2. Git-Backed Simultaneous Conflict Management", w)
        cb_layout = QVBoxLayout(conflict_box)

        lbl_git_info = QLabel("Git continuously records state snapshots during simultaneous editing sessions to handle overlap conflicts automatically.", conflict_box)
        lbl_git_info.setStyleSheet("color: #6e6e73; font-style: italic;")
        cb_layout.addWidget(lbl_git_info)

        btn_trigger_conflict = QPushButton("⚡ Trigger Simulated Concurrent Edit Conflict", conflict_box)
        btn_trigger_conflict.setStyleSheet("background-color: #ff9500; color: white; font-weight: bold; padding: 6px;")
        btn_trigger_conflict.clicked.connect(self._on_trigger_conflict)
        cb_layout.addWidget(btn_trigger_conflict)

        # Conflict Resolution Workspace Card
        self.card_conflict = QWidget(conflict_box)
        cc_layout = QVBoxLayout(self.card_conflict)
        cc_layout.setContentsMargins(10, 10, 10, 10)
        self.card_conflict.setStyleSheet("background-color: #fffbe6; border: 1px solid #ffe58f; border-radius: 8px;")

        self.lbl_conflict_status = QLabel("No conflict detected.", self.card_conflict)
        self.lbl_conflict_status.setStyleSheet("font-weight: bold; color: #b45309;")
        cc_layout.addWidget(self.lbl_conflict_status)

        self.browser_conflict = QTextBrowser(self.card_conflict)
        self.browser_conflict.setFixedHeight(110)
        self.browser_conflict.setFont(QFont("Fira Code", 10))
        cc_layout.addWidget(self.browser_conflict)

        btn_row = QWidget(self.card_conflict)
        br_layout = QHBoxLayout(btn_row)
        br_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_keep_mine = QPushButton("Keep Mine (Current User)", btn_row)
        self.btn_keep_theirs = QPushButton("Keep Theirs (Collaborator Alex)", btn_row)
        self.btn_combine_both = QPushButton("Combine Both Versions", btn_row)

        for btn in [self.btn_keep_mine, self.btn_keep_theirs, self.btn_combine_both]:
            btn.setStyleSheet("background-color: #ffffff; border: 1px solid #d1d1d6; font-weight: bold; padding: 6px;")
            br_layout.addWidget(btn)

        self.btn_keep_mine.clicked.connect(lambda: self._resolve_conflict("mine"))
        self.btn_keep_theirs.clicked.connect(lambda: self._resolve_conflict("theirs"))
        self.btn_combine_both.clicked.connect(lambda: self._resolve_conflict("both"))

        cc_layout.addWidget(btn_row)
        cb_layout.addWidget(self.card_conflict)

        layout.addWidget(conflict_box, 1)
        return w

    def _apply_theme(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                color: #1c1c1e;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #d1d1d6;
                border-radius: 8px;
                margin-top: 6px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #007aff;
            }
            QListWidget {
                border: 1px solid #d1d1d6;
                border-radius: 6px;
                background-color: #ffffff;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f2f2f7;
            }
            QListWidget::item:selected {
                background-color: #007aff;
                color: white;
            }
            QLineEdit, QComboBox {
                border: 1px solid #d1d1d6;
                border-radius: 6px;
                padding: 6px;
                background-color: #ffffff;
            }
        """)

    def switch_tab(self, index: int):
        self.btn_tab_async.setChecked(index == 0)
        self.btn_tab_simul.setChecked(index == 1)
        self.stack_pages.setCurrentIndex(index)

    def refresh_all(self):
        self.refresh_contributions()
        self.refresh_notes_dropdown()

    def refresh_notes_dropdown(self):
        self.cb_notes_to_share.clear()
        files = self.git_mgr.get_files_status()["all_files"]
        for f in files:
            self.cb_notes_to_share.addItem(f"🗎 {f}", f)

    def refresh_contributions(self):
        self.list_contribs.clear()
        contribs = self.collab_mgr.get_incoming_contributions()

        for c in contribs:
            item = QListWidgetItem(f"⎇ {c['title']}\nBranch: {c['branch']} • Target: {c['target_branch']}")
            item.setData(Qt.ItemDataRole.UserRole, c)
            self.list_contribs.addItem(item)

        if contribs:
            self.list_contribs.setCurrentRow(0)
            self._on_contrib_item_clicked(self.list_contribs.currentItem())
        else:
            self.lbl_contrib_meta.setText("No pending contributions.")
            self.browser_contrib_diff.setHtml("<p style='color:#6e6e73;'>No incoming contributions found.</p>")
            self.btn_merge_contrib.setEnabled(False)

    def _on_contrib_item_clicked(self, item):
        if not item: return
        data = item.data(Qt.ItemDataRole.UserRole)
        self.active_contrib = data

        self.lbl_contrib_meta.setText(f"Reviewing Contribution: '{data['branch']}' by {data['author']}")
        self.btn_merge_contrib.setEnabled(True)

        diff = data['diff']
        html_lines = [
            f"<h4>Diff for <b>{diff['filename']}</b> from branch <code>{data['branch']}</code></h4>",
            f"<p><span style='color:#28a745; font-weight:bold;'>+{diff['additions']} additions</span> | <span style='color:#dc3545; font-weight:bold;'>-{diff['deletions']} deletions</span></p>",
            "<table style='width:100%; border-collapse:collapse; font-family:monospace; font-size:12px;'>"
        ]

        for line in diff['lines']:
            ltype = line['type']
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

            html_lines.append(f"<tr style='background-color:{bg}; color:{color};'><td style='width:20px;'>{sym}</td><td>{html.escape(line['text'])}</td></tr>")

        html_lines.append("</table>")
        self.browser_contrib_diff.setHtml("\n".join(html_lines))

    def _on_merge_contrib_clicked(self):
        if not self.active_contrib: return
        branch = self.active_contrib['branch']

        if self.collab_mgr.merge_contribution(branch):
            QMessageBox.information(self, "Merged", f"Successfully merged '{branch}' into main!")
            self.refresh_all()
        else:
            QMessageBox.warning(self, "Merge Error", f"Could not merge '{branch}'.")

    # --- Simultaneous Link & Conflict handlers ---
    def _on_generate_link_clicked(self):
        fname = self.cb_notes_to_share.currentData() or "physics_quantum_notes.md"
        access = "public" if self.rad_public.isChecked() else "restricted"
        emails = [e.strip() for e in self.txt_allowed_emails.text().split(",") if e.strip()]
        role = "editor" if "Edit" in self.cb_role.currentText() else "viewer"

        link_data = self.collab_mgr.create_share_link(fname, access_mode=access, allowed_emails=emails, role=role)
        self.txt_share_link.setText(link_data["url"])
        QMessageBox.information(self, "Link Generated", f"Share Link generated for '{fname}' ({access.title()} access)!")

    def _on_copy_link_clicked(self):
        url = self.txt_share_link.text()
        if url:
            QApplication.clipboard().setText(url)
            QMessageBox.information(self, "Copied", "Share link copied to clipboard!")

    def _on_launch_editor_only(self):
        fname = self.cb_notes_to_share.currentData() or "physics_quantum_notes.md"
        content = self.git_mgr.get_file_content(fname)
        role = "editor" if "Edit" in self.cb_role.currentText() else "viewer"

        self.editor_window = EditorOnlyWindow(filename=fname, initial_content=content, role=role)
        self.editor_window.show()

    def _on_trigger_conflict(self):
        fname = self.cb_notes_to_share.currentData() or "physics_quantum_notes.md"
        conflict = self.collab_mgr.simulate_simultaneous_conflict(fname)
        self.active_conflict = conflict

        self.lbl_conflict_status.setText(f"⚠ SIMULTANEOUS EDIT CONFLICT DETECTED in '{fname}'!")
        
        diff_html = f"""
        <div style='font-family:monospace; font-size:11px;'>
            <p style='color:#b45309; font-weight:bold;'>&lt;&lt;&lt;&lt;&lt;&lt;&lt; Current User (Mine)</p>
            <pre style='background:#fff0f0; padding:6px; color:#cf222e;'>{html.escape(conflict['mine_snippet'])}</pre>
            <p style='color:#007aff; font-weight:bold;'>======= Collaborator (Alex)</p>
            <pre style='background:#f0f8ff; padding:6px; color:#007aff;'>{html.escape(conflict['theirs_snippet'])}</pre>
            <p style='color:#b45309; font-weight:bold;'>&gt;&gt;&gt;&gt;&gt;&gt;&gt;</p>
        </div>
        """
        self.browser_conflict.setHtml(diff_html)

    def _resolve_conflict(self, choice: str):
        if not self.active_conflict:
            QMessageBox.information(self, "No Conflict", "No active conflict to resolve.")
            return

        c = self.active_conflict
        res = self.collab_mgr.resolve_and_commit_conflict(c["filename"], choice, c["mine"], c["theirs"])
        if res:
            self.lbl_conflict_status.setText(f"✓ Conflict resolved ({choice.title()}) and saved to Git commit history!")
            self.lbl_conflict_status.setStyleSheet("color: #28a745; font-weight: bold;")
            self.browser_conflict.setHtml(f"<p style='color:#28a745;'>State cleanly merged & committed into Git.</p>")
            self.active_conflict = None
            self.refresh_all()
