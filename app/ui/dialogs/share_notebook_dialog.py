"""
Google Drive Style Share Notebook Dialog (Crisp White Theme)
Sleek modal for managing General Access (Public/Restricted), inviting collaborators by email,
copying share links, previewing Editor-Only view, and inspecting Git Version History.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QListWidget, QListWidgetItem, QFrame, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
import qtawesome as qta

from ...backend.collaboration_manager import CollaborationManager
from ...backend.git_notes_manager import GitNotesManager

class ShareNotebookDialog(QDialog):
    def __init__(self, notebook_id: str, notebook_name: str, parent=None):
        super().__init__(parent)
        self.notebook_id = notebook_id
        self.notebook_name = notebook_name
        self.git_mgr = GitNotesManager()
        self.collab_mgr = CollaborationManager(self.git_mgr)
        self.editor_window = None

        self.setWindowTitle(f"Share '{notebook_name}'")
        self.resize(540, 600)
        self._init_ui()
        self._apply_white_theme()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        # Header Title (Google Drive White Card Style)
        header = QHBoxLayout()
        lbl_icon = QLabel("☌", self)
        lbl_icon.setStyleSheet("font-size: 24px; background: transparent;")
        
        lbl_title = QLabel(f"Share '{self.notebook_name}'", self)
        lbl_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #1c1c1e;")

        header.addWidget(lbl_icon)
        header.addWidget(lbl_title)
        header.addStretch()
        layout.addLayout(header)

        # Section 1: Add People and Groups
        lbl_add = QLabel("Add people and groups:", self)
        lbl_add.setStyleSheet("font-size: 12px; font-weight: bold; color: #6e6e73;")
        layout.addWidget(lbl_add)

        row_add = QHBoxLayout()
        self.txt_email_input = QLineEdit(self)
        self.txt_email_input.setPlaceholderText("Add email (e.g. alex@edu, sam@mit.edu)")

        self.cb_add_role = QComboBox(self)
        self.cb_add_role.addItems(["Editor", "Viewer"])

        btn_add = QPushButton("Invite", self)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setStyleSheet("background-color: #007aff; color: white; font-weight: bold; border-radius: 6px; padding: 8px 16px; border: none;")
        btn_add.clicked.connect(self._on_add_person)

        row_add.addWidget(self.txt_email_input, 1)
        row_add.addWidget(self.cb_add_role)
        row_add.addWidget(btn_add)
        layout.addLayout(row_add)

        # Section 2: People with Access List
        lbl_access_list = QLabel("People with access:", self)
        lbl_access_list.setStyleSheet("font-size: 12px; font-weight: bold; color: #6e6e73;")
        layout.addWidget(lbl_access_list)

        self.list_people = QListWidget(self)
        self.list_people.setFixedHeight(85)

        owner_item = QListWidgetItem("❖ Dakshayani (You)  •  Owner")
        self.list_people.addItem(owner_item)
        layout.addWidget(self.list_people)

        # Section 3: General Access Settings (Google Drive Style)
        lbl_gen = QLabel("General access:", self)
        lbl_gen.setStyleSheet("font-size: 12px; font-weight: bold; color: #6e6e73;")
        layout.addWidget(lbl_gen)

        row_gen = QHBoxLayout()
        self.cb_general_access = QComboBox(self)
        self.cb_general_access.addItem("⊕ Anyone with the link (Public)", "public")
        self.cb_general_access.addItem("☿ Restricted (Only added people)", "restricted")

        row_gen.addWidget(self.cb_general_access, 1)
        layout.addLayout(row_gen)

        # Section 4: Copy Link Box
        row_link = QHBoxLayout()
        self.txt_link_url = QLineEdit(self)
        self.txt_link_url.setReadOnly(True)
        self.txt_link_url.setText(f"https://aitutor.notes/share?id={self.notebook_id}&token=sec_{self.notebook_id[-6:]}")

        btn_copy = QPushButton("⎘ Copy link", self)
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy.setStyleSheet("background-color: #ffffff; border: 1px solid #d1d1d6; border-radius: 6px; padding: 6px 14px; font-weight: bold; color: #007aff;")
        btn_copy.clicked.connect(self._on_copy_link)

        row_link.addWidget(self.txt_link_url, 1)
        row_link.addWidget(btn_copy)
        layout.addLayout(row_link)

        # Section 5: Inline Git Version History Log (Expandable)
        self.btn_toggle_git = QPushButton("⎇ Inspect Git Version History ▼", self)
        self.btn_toggle_git.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_git.setStyleSheet("background-color: #f2f2f7; color: #007aff; border: 1px solid #d1d1d6; border-radius: 6px; font-weight: bold; padding: 7px;")
        self.btn_toggle_git.clicked.connect(self._toggle_git_history)
        layout.addWidget(self.btn_toggle_git)

        self.list_git_history = QListWidget(self)
        self.list_git_history.setFixedHeight(120)
        self.list_git_history.setVisible(False)
        layout.addWidget(self.list_git_history)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #e5e5ea;")
        layout.addWidget(line)

        # Footer Actions
        footer = QHBoxLayout()
        btn_editor_view = QPushButton("⌕ Launch Editor-Only View", self)
        btn_editor_view.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_editor_view.setStyleSheet("background-color: #34c759; color: white; font-weight: bold; border-radius: 6px; padding: 8px 14px; border: none;")
        btn_editor_view.clicked.connect(self._on_launch_editor_view)

        btn_done = QPushButton("Done", self)
        btn_done.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_done.setStyleSheet("background-color: #007aff; color: white; font-weight: bold; border-radius: 6px; padding: 8px 22px; border: none;")
        btn_done.clicked.connect(self.accept)

        footer.addWidget(btn_editor_view)
        footer.addStretch()
        footer.addWidget(btn_done)
        layout.addLayout(footer)

        self._load_git_history()

    def _apply_white_theme(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                color: #1c1c1e;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 6px;
                padding: 8px;
                color: #1c1c1e;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #007aff;
            }
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 6px;
                padding: 8px;
                color: #1c1c1e;
                font-size: 13px;
            }
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 8px;
                color: #1c1c1e;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #f2f2f7;
            }
        """)

    def _on_add_person(self):
        email = self.txt_email_input.text().strip()
        if not email:
            return
        role = self.cb_add_role.currentText()
        item = QListWidgetItem(f"✉ {email}  •  {role}")
        self.list_people.addItem(item)
        self.txt_email_input.clear()
        QMessageBox.information(self, "Invited", f"Added '{email}' as {role}!")

    def _on_copy_link(self):
        QApplication.clipboard().setText(self.txt_link_url.text())
        QMessageBox.information(self, "Copied", "Link copied to clipboard!")

    def _on_launch_editor_view(self):
        from ..views.editor_only_window import EditorOnlyWindow
        self.editor_window = EditorOnlyWindow(
            filename=f"boards/{self.notebook_id}.json",
            initial_content=f'{{"board_id":"{self.notebook_id}", "title":"{self.notebook_name}", "items":[]}}',
            role="editor"
        )
        self.editor_window.show()

    def _toggle_git_history(self):
        visible = not self.list_git_history.isVisible()
        self.list_git_history.setVisible(visible)
        arrow = "▲" if visible else "▼"
        self.btn_toggle_git.setText(f"⎇ Inspect Git Version History {arrow}")

    def _load_git_history(self):
        self.list_git_history.clear()
        commits = self.git_mgr.get_commit_history()

        if not commits:
            self.list_git_history.addItem("No Git commit history found.")
            return

        for c in commits:
            item = QListWidgetItem(f"[{c['hash']}] {c['message']}\nAuthor: {c['author']} • {c['date']}")
            self.list_git_history.addItem(item)
