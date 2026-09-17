"""
Version History Panel - Kestrel-native Version History & Checkpoints View
Performance Optimized & Clean Monotone Restyling:
- Instant panel open: lazy loads tab content on demand with no synchronous Git hang
- Fixed sidebar 'Modified · 3 Pages' item layout: explicit row height with clean non-overlapping title + subtext and right-aligned badge
- Clean Snapshot History cards: single outer border, plain bold version title, clean description text (no nested outline boxes), timestamp and 'Restore Version' action
- Incoming Changes tab: collaborator contributions with solid black 'ACCEPT' button (merges on backend) and 'Dismiss' button (rejects on backend)
- What Changed tab: real Git diff view in JetBrains Mono font with clean monotone styling
- Auto-saving status in neutral monotone styling
"""

import os
import html
from typing import Optional, List, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QTreeWidget, QTreeWidgetItem,
    QTextBrowser, QPushButton, QLabel, QFrame, QStackedWidget,
    QLineEdit, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QFont, QColor
import qtawesome as qta

from ...backend.version_control.git_notes_manager import GitNotesManager
from ...backend.version_control.collaboration_manager import CollaborationManager
from ...backend.version_control.version_service import (
    VersionService, VersionSnapshot
)
from ..theme_manager import ThemeManager
from ..kestrel_theme import MONO_FONT, primary_button_qss

MONO_JETBRAINS = '"JetBrains Mono", "Space Mono", ui-monospace, "Consolas", monospace'


class VersionHistoryPanel(QWidget):
    version_restored = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.version_service = VersionService()
        self.git_mgr = self.version_service.adapter
        self.collab_mgr = CollaborationManager(self.git_mgr)
        self.active_filename = "physics_quantum_notes.md"
        self.active_notebook_id: Optional[str] = None
        self._tabs_loaded = set()

        self._init_ui()
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme(ThemeManager.instance().current_theme)

        # Populate sidebar and load initial tab smoothly
        self._populate_sidebar_tree()
        QTimer.singleShot(10, lambda: self.switch_view_mode(0))

    def _init_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Splitter: Left Sidebar (260px) + Main Content Area
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)

        self.sidebar_widget = self._create_sidebar()
        self.splitter.addWidget(self.sidebar_widget)

        self.workspace_widget = self._create_workspace()
        self.splitter.addWidget(self.workspace_widget)

        self.splitter.setSizes([260, 1000])
        root_layout.addWidget(self.splitter)

    def _create_sidebar(self) -> QWidget:
        sb = QWidget(self)
        sb.setFixedWidth(260)
        sb.setObjectName("VCSidebar")
        layout = QVBoxLayout(sb)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── 1. Header Title ──
        self.lbl_sec_hdr = QLabel("VERSION CONTROL", sb)
        layout.addWidget(self.lbl_sec_hdr)

        self.lbl_nb_title = QLabel("My Notebook", sb)
        layout.addWidget(self.lbl_nb_title)

        self.lbl_sync_status = QLabel("● Auto-saving · Synced", sb)
        layout.addWidget(self.lbl_sync_status)

        layout.addSpacing(6)

        # ── 2. Save a Snapshot Box ──
        self.lbl_save_hdr = QLabel("SAVE A SNAPSHOT", sb)
        layout.addWidget(self.lbl_save_hdr)

        self.input_commit_msg = QLineEdit(sb)
        self.input_commit_msg.setPlaceholderText("What did you add or change?")
        self.input_commit_msg.setFixedHeight(34)
        layout.addWidget(self.input_commit_msg)

        self.btn_save_snapshot = QPushButton("SAVE SNAPSHOT", sb)
        self.btn_save_snapshot.setFixedHeight(34)
        self.btn_save_snapshot.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_snapshot.clicked.connect(self._on_save_snapshot_clicked)
        layout.addWidget(self.btn_save_snapshot)

        layout.addSpacing(10)

        # ── 3. Modified Pages Tree ──
        self.lbl_pages_hdr = QLabel("MODIFIED · 3 PAGES", sb)
        layout.addWidget(self.lbl_pages_hdr)

        self.tree_pages = QTreeWidget(sb)
        self.tree_pages.setHeaderHidden(True)
        self.tree_pages.setRootIsDecorated(False)
        self.tree_pages.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tree_pages.itemClicked.connect(self._on_tree_item_clicked)
        layout.addWidget(self.tree_pages, 1)

        return sb

    def _create_workspace(self) -> QWidget:
        ws = QWidget(self)
        layout = QVBoxLayout(ws)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Top Tab Bar ──
        nav_bar = QWidget(ws)
        nav_bar.setFixedHeight(44)
        nav_bar.setObjectName("VCTabBar")
        nb_layout = QHBoxLayout(nav_bar)
        nb_layout.setContentsMargins(20, 0, 20, 0)
        nb_layout.setSpacing(12)

        self.btn_tab_incoming = QPushButton("Incoming Changes", nav_bar)
        self.btn_tab_diff = QPushButton("What Changed", nav_bar)
        self.btn_tab_history = QPushButton("Snapshot History", nav_bar)

        self.tab_buttons = [
            self.btn_tab_incoming,
            self.btn_tab_diff,
            self.btn_tab_history
        ]

        for idx, btn in enumerate(self.tab_buttons):
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=idx: self.switch_view_mode(i))
            nb_layout.addWidget(btn)

        nb_layout.addStretch()
        layout.addWidget(nav_bar)

        # ── Stacked View Pages ──
        self.stack_views = QStackedWidget(ws)

        # View 0: Incoming Changes
        self.view_incoming = self._create_incoming_view()
        self.stack_views.addWidget(self.view_incoming)

        # View 1: What Changed (Diff View)
        self.view_diff = self._create_diff_view()
        self.stack_views.addWidget(self.view_diff)

        # View 2: Snapshot History (Timeline Cards)
        self.view_history = self._create_history_view()
        self.stack_views.addWidget(self.view_history)

        layout.addWidget(self.stack_views)
        return ws

    def _create_incoming_view(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        header_box = QVBoxLayout()
        header_box.setSpacing(4)

        self.lbl_incoming_title = QLabel("Incoming Changes", container)
        header_box.addWidget(self.lbl_incoming_title)

        self.lbl_incoming_sub = QLabel("Contributions from your collaborators waiting for review.", container)
        header_box.addWidget(self.lbl_incoming_sub)

        layout.addLayout(header_box)

        scroll = QScrollArea(container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        self.incoming_cards_widget = QWidget()
        self.incoming_cards_widget.setStyleSheet("background: transparent;")
        self.incoming_cards_layout = QVBoxLayout(self.incoming_cards_widget)
        self.incoming_cards_layout.setContentsMargins(0, 8, 0, 0)
        self.incoming_cards_layout.setSpacing(14)
        self.incoming_cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self.incoming_cards_widget)
        layout.addWidget(scroll)

        return container

    def _create_diff_view(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        self.lbl_diff_title = QLabel("What Changed", container)
        layout.addWidget(self.lbl_diff_title)

        self.diff_browser = QTextBrowser(container)
        self.diff_browser.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(self.diff_browser)

        return container

    def _create_history_view(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        self.lbl_history_title = QLabel("Snapshot History", container)
        layout.addWidget(self.lbl_history_title)

        scroll = QScrollArea(container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        self.history_cards_widget = QWidget()
        self.history_cards_widget.setStyleSheet("background: transparent;")
        self.history_cards_layout = QVBoxLayout(self.history_cards_widget)
        self.history_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.history_cards_layout.setSpacing(12)
        self.history_cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self.history_cards_widget)
        layout.addWidget(scroll)

        return container

    def _apply_theme(self, theme_name: str = "light"):
        c = ThemeManager.instance().get_colors()

        self.setObjectName("VersionHistoryRoot")
        self.setStyleSheet(f"""
            QWidget#VersionHistoryRoot {{
                background-color: {c['bg_app']};
            }}
            QWidget#VCSidebar {{
                background-color: {c['bg_card']};
                border-right: 1px solid {c['border_color']};
            }}
            QWidget#VCTabBar {{
                background-color: {c['bg_card']};
                border-bottom: 1px solid {c['border_color']};
            }}
            QSplitter::handle {{
                background-color: {c['border_color']};
            }}
        """)

        self.lbl_sec_hdr.setStyleSheet(f"font-family: {MONO_JETBRAINS}; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; color: {c['text_secondary']};")
        self.lbl_nb_title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {c['text_primary']};")
        self.lbl_sync_status.setStyleSheet(f"font-family: {MONO_JETBRAINS}; font-size: 11px; color: {c['text_secondary']}; font-weight: 600;")
        self.lbl_save_hdr.setStyleSheet(f"font-family: {MONO_JETBRAINS}; font-size: 10px; font-weight: 700; letter-spacing: 1px; color: {c['text_secondary']};")
        self.lbl_pages_hdr.setStyleSheet(f"font-family: {MONO_JETBRAINS}; font-size: 10px; font-weight: 700; letter-spacing: 1px; color: {c['text_secondary']};")

        self.input_commit_msg.setStyleSheet(f"""
            QLineEdit {{
                background-color: {c['panel_card_bg']};
                border: 1px solid {c['border_color']};
                border-radius: 4px;
                padding: 6px 10px;
                font-family: {MONO_JETBRAINS};
                font-size: 11px;
                color: {c['text_primary']};
            }}
            QLineEdit:focus {{
                border-color: {c['accent']};
            }}
        """)

        self.btn_save_snapshot.setStyleSheet(primary_button_qss(c))

        self.tree_pages.setStyleSheet(f"""
            QTreeWidget {{
                background-color: transparent;
                border: none;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                font-size: 12px;
                color: {c['text_primary']};
            }}
            QTreeWidget::item {{
                padding: 0px;
                border-radius: 4px;
                margin-bottom: 3px;
            }}
            QTreeWidget::item:selected {{
                background-color: {c['panel_card_bg']};
            }}
            QTreeWidget::item:hover:!selected {{
                background-color: {c['panel_card_bg']};
            }}
        """)

        for btn in self.tab_buttons:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {c['text_secondary']};
                    border: none;
                    font-family: {MONO_JETBRAINS};
                    font-weight: 600;
                    font-size: 11px;
                    letter-spacing: 0.5px;
                    padding: 8px 14px;
                    border-bottom: 2px solid transparent;
                    border-radius: 0px;
                }}
                QPushButton:checked {{
                    color: {c['text_primary']};
                    font-weight: 800;
                    border-bottom: 2px solid {c['accent']};
                }}
                QPushButton:hover:!checked {{
                    color: {c['text_primary']};
                }}
            """)

        self.lbl_incoming_title.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {c['text_primary']};")
        self.lbl_incoming_sub.setStyleSheet(f"font-family: {MONO_JETBRAINS}; font-size: 12px; color: {c['text_secondary']};")
        self.lbl_diff_title.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {c['text_primary']};")
        self.lbl_history_title.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {c['text_primary']};")

        self.diff_browser.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border_color']};
                border-radius: 6px;
                padding: 14px;
                font-family: {MONO_JETBRAINS};
                font-size: 12px;
                color: {c['text_primary']};
            }}
        """)

    def switch_view_mode(self, index: int):
        for i, btn in enumerate(self.tab_buttons):
            btn.setChecked(i == index)
        self.stack_views.setCurrentIndex(index)

        if index == 0:
            self._render_incoming_cards()
        elif index == 1:
            self._render_diff_view()
        elif index == 2:
            self._render_history_cards()

    def refresh_all(self):
        self._populate_sidebar_tree()
        self.switch_view_mode(self.stack_views.currentIndex())

    def _populate_sidebar_tree(self):
        self.tree_pages.clear()
        c = ThemeManager.instance().get_colors()

        pages = [
            ("Kinematics Notes", "physics_quantum_notes.md", "You edited this page", "Edited"),
            ("Calculus Reference", "calculus_reference.md", "You updated formulas", "Edited"),
            ("Projectile Motion", "projectile_motion.md", "You added a new page", "New"),
        ]

        for title, fname, subtitle, badge_txt in pages:
            item = QTreeWidgetItem(self.tree_pages)
            item.setSizeHint(0, QSize(228, 48))

            row_widget = QWidget()
            row_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            r_layout = QHBoxLayout(row_widget)
            r_layout.setContentsMargins(6, 4, 6, 4)
            r_layout.setSpacing(8)

            lbl_ic = QLabel(row_widget)
            lbl_ic.setPixmap(qta.icon("ri.file-text-line", color=c['text_secondary']).pixmap(14, 14))
            r_layout.addWidget(lbl_ic)

            text_vbox = QVBoxLayout()
            text_vbox.setContentsMargins(0, 0, 0, 0)
            text_vbox.setSpacing(2)

            t_lbl = QLabel(title, row_widget)
            t_lbl.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {c['text_primary']}; font-family: {MONO_JETBRAINS}; line-height: 1.2;")

            s_lbl = QLabel(subtitle, row_widget)
            s_lbl.setStyleSheet(f"font-size: 10px; color: {c['text_secondary']}; line-height: 1.1;")

            text_vbox.addWidget(t_lbl)
            text_vbox.addWidget(s_lbl)
            r_layout.addLayout(text_vbox, 1)

            badge = QLabel(badge_txt, row_widget)
            badge.setStyleSheet(f"""
                font-family: {MONO_JETBRAINS};
                font-size: 9px;
                font-weight: 700;
                color: {c['text_secondary']};
                background: {c['panel_card_bg']};
                border: 1px solid {c['border_color']};
                border-radius: 3px;
                padding: 1px 5px;
            """)
            r_layout.addWidget(badge)

            self.tree_pages.setItemWidget(item, 0, row_widget)
            item.setData(0, Qt.ItemDataRole.UserRole, fname)

        if self.tree_pages.topLevelItemCount() > 0:
            self.tree_pages.setCurrentItem(self.tree_pages.topLevelItem(0))

    def _render_incoming_cards(self):
        while self.incoming_cards_layout.count() > 0:
            child = self.incoming_cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        c = ThemeManager.instance().get_colors()
        incoming = self.collab_mgr.get_incoming_contributions()

        if not incoming:
            empty_lbl = QLabel("No incoming changes waiting for review.", self.incoming_cards_widget)
            empty_lbl.setStyleSheet(f"font-family: {MONO_JETBRAINS}; color: {c['text_secondary']}; font-size: 12px; margin-top: 20px;")
            self.incoming_cards_layout.addWidget(empty_lbl)
            return

        for contrib in incoming:
            card = QFrame()
            card.setObjectName("IncomingCard")
            card.setStyleSheet(f"""
                QFrame#IncomingCard {{
                    background-color: {c['bg_card']};
                    border: 1px solid {c['border_color']};
                    border-radius: 8px;
                }}
                QFrame#IncomingCard:hover {{
                    border-color: {c['accent']};
                }}
            """)

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(20, 16, 20, 16)
            card_layout.setSpacing(12)

            top_row = QHBoxLayout()
            top_row.setSpacing(10)

            initials = contrib["author"][:2].upper()
            lbl_avatar = QLabel(initials, card)
            lbl_avatar.setFixedSize(30, 30)
            lbl_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_avatar.setStyleSheet(f"""
                background-color: {c['panel_card_bg']};
                color: {c['text_primary']};
                font-family: {MONO_JETBRAINS};
                font-size: 11px;
                font-weight: 700;
                border-radius: 15px;
                border: 1px solid {c['border_color']};
            """)
            top_row.addWidget(lbl_avatar)

            lbl_author_time = QLabel(f"<b>{contrib['author']}</b><br/><span style='color:{c['text_secondary']}; font-size:11px; font-family:{MONO_JETBRAINS};'>Pending Branch: {contrib['branch']}</span>", card)
            lbl_author_time.setStyleSheet(f"font-size: 13px; color: {c['text_primary']};")
            top_row.addWidget(lbl_author_time)
            top_row.addStretch()

            card_layout.addLayout(top_row)

            diff_summary = f"Added {contrib['diff']['additions']} lines, removed {contrib['diff']['deletions']} lines in {contrib['title']}."
            lbl_msg = QLabel(diff_summary, card)
            lbl_msg.setStyleSheet(f"font-size: 13px; color: {c['text_primary']}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;")
            lbl_msg.setWordWrap(True)
            card_layout.addWidget(lbl_msg)

            btn_row = QHBoxLayout()
            btn_row.setSpacing(12)

            btn_accept = QPushButton("ACCEPT", card)
            btn_accept.setFixedHeight(34)
            btn_accept.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_accept.setStyleSheet(primary_button_qss(c))
            btn_accept.clicked.connect(lambda _, b=contrib['branch']: self._accept_backend_contribution(b))
            btn_row.addWidget(btn_accept, 1)

            btn_dismiss = QPushButton("Dismiss", card)
            btn_dismiss.setFixedHeight(34)
            btn_dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_dismiss.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    color: {c['text_secondary']};
                    font-family: {MONO_JETBRAINS};
                    font-size: 12px;
                    font-weight: 600;
                    padding: 6px 14px;
                }}
                QPushButton:hover {{
                    color: {c['text_primary']};
                }}
            """)
            btn_dismiss.clicked.connect(lambda _, b=contrib['branch']: self._dismiss_backend_contribution(b))
            btn_row.addWidget(btn_dismiss)

            card_layout.addLayout(btn_row)
            self.incoming_cards_layout.addWidget(card)

    def _accept_backend_contribution(self, branch: str):
        self.lbl_sync_status.setText("● Merging...")
        self.collab_mgr.merge_contribution(branch)
        self.lbl_sync_status.setText("● Auto-saving · Synced")
        self.refresh_all()

    def _dismiss_backend_contribution(self, branch: str):
        try:
            self.git_mgr._run_git(["branch", "-D", branch])
        except Exception:
            pass
        self.refresh_all()

    def _render_diff_view(self):
        c = ThemeManager.instance().get_colors()
        diff_data = self.git_mgr.get_diff(self.active_filename)
        raw_diff = diff_data.get("raw", "")

        if not raw_diff:
            content = self.git_mgr.get_file_content(self.active_filename)
            lines = [
                f"<div style='color:{c['text_secondary']}; font-family:{MONO_JETBRAINS}; margin-bottom:8px;'>--- a/{self.active_filename}<br/>+++ b/{self.active_filename}</div>",
                f"<div style='color:{c['text_primary']}; font-family:{MONO_JETBRAINS}; padding:2px 0;'>Current file content ({len(content.splitlines())} lines) is in sync with HEAD commit.</div>"
            ]
            self.diff_browser.setHtml("".join(lines))
            return

        formatted_lines = [
            f"<div style='color:{c['text_secondary']}; font-family:{MONO_JETBRAINS}; margin-bottom:8px;'>--- a/{self.active_filename}<br/>+++ b/{self.active_filename}</div>"
        ]

        for line in raw_diff.splitlines():
            esc = html.escape(line)
            if line.startswith("+") and not line.startswith("+++"):
                formatted_lines.append(f"<div style='background-color:{c['panel_card_bg']}; font-weight:700; color:{c['text_primary']}; font-family:{MONO_JETBRAINS}; padding:2px 4px;'>{esc}</div>")
            elif line.startswith("-") and not line.startswith("---"):
                formatted_lines.append(f"<div style='color:{c['text_secondary']}; text-decoration:line-through; font-family:{MONO_JETBRAINS}; padding:2px 4px;'>{esc}</div>")
            else:
                formatted_lines.append(f"<div style='color:{c['text_secondary']}; font-family:{MONO_JETBRAINS}; padding:2px 4px;'>{esc}</div>")

        self.diff_browser.setHtml("".join(formatted_lines))

    def _render_history_cards(self):
        while self.history_cards_layout.count() > 0:
            child = self.history_cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        c = ThemeManager.instance().get_colors()
        snapshots = self.version_service.get_version_history(notebook_id=self.active_notebook_id, limit=50)

        for snap in snapshots:
            # Clean Single Outer Card (No nested outline boxes around title or description)
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {c['bg_card']};
                    border: 1px solid {c['border_color']};
                    border-radius: 8px;
                }}
                QFrame:hover {{
                    border-color: {c['accent']};
                }}
            """)

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 14, 18, 14)
            card_layout.setSpacing(6)

            # Top Row: Clean Bold Version Heading + Monospace Timestamp
            top_row = QHBoxLayout()
            top_row.setContentsMargins(0, 0, 0, 0)

            lbl_title = QLabel(snap.title, card)
            lbl_title.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {c['text_primary']}; background: transparent; border: none;")
            top_row.addWidget(lbl_title)
            top_row.addStretch()

            lbl_time = QLabel(snap.relative_time, card)
            lbl_time.setStyleSheet(f"font-size: 11px; color: {c['text_secondary']}; font-family: {MONO_JETBRAINS}; background: transparent; border: none;")
            top_row.addWidget(lbl_time)
            card_layout.addLayout(top_row)

            # Plain Text Commit Description (no nested box/pill)
            lbl_desc = QLabel(snap.description, card)
            lbl_desc.setWordWrap(True)
            lbl_desc.setStyleSheet(f"font-size: 12px; color: {c['text_secondary']}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: transparent; border: none; margin-top: 2px; margin-bottom: 6px;")
            card_layout.addWidget(lbl_desc)

            # Bottom Row: Restore Version Button Action
            bot_row = QHBoxLayout()
            bot_row.setContentsMargins(0, 0, 0, 0)
            bot_row.addStretch()

            btn_restore = QPushButton("Restore Version", card)
            btn_restore.setIcon(qta.icon("ri.restart-line", color=c['text_secondary']))
            btn_restore.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_restore.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid {c['border_color']};
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-family: {MONO_JETBRAINS};
                    font-size: 11px;
                    font-weight: 600;
                    color: {c['text_primary']};
                }}
                QPushButton:hover {{
                    background-color: {c['panel_card_bg']};
                    border-color: {c['accent']};
                }}
            """)
            btn_restore.clicked.connect(lambda _, s=snap: self._restore_backend_snapshot(s))
            bot_row.addWidget(btn_restore)
            card_layout.addLayout(bot_row)

            self.history_cards_layout.addWidget(card)

    def _restore_backend_snapshot(self, snap: VersionSnapshot):
        self.lbl_sync_status.setText("● Restoring...")
        self.version_service.restore_version(snap.version_id)
        self.version_restored.emit(snap.version_id)
        self.lbl_sync_status.setText("● Auto-saving · Synced")
        self.refresh_all()

    def _on_save_snapshot_clicked(self):
        msg = self.input_commit_msg.text().strip()
        if not msg:
            msg = "Manual Snapshot Checkpoint"
        self.lbl_sync_status.setText("● Saving...")
        self.version_service.create_checkpoint(title=msg, description="User saved version", is_backup=False)
        self.input_commit_msg.clear()
        self.lbl_sync_status.setText("● Auto-saving · Synced")
        self.refresh_all()

    def _on_tree_item_clicked(self, item, col):
        fname = item.data(0, Qt.ItemDataRole.UserRole)
        if fname:
            self.active_filename = fname
            if self.stack_views.currentIndex() == 1:
                self._render_diff_view()


# Backward compatibility alias
GitNotesPanel = VersionHistoryPanel
