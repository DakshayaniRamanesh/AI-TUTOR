"""
Notebooks Management View Panel
Displays folder tree navigation with breadcrumb, folder cards, and notebook cards.
Supports nested folder structure, share dialog, Git VCS history, and Rename/Move/Delete actions.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QMessageBox, QInputDialog, QDialog,
    QListWidget, QListWidgetItem, QDialogButtonBox, QMenu, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QCursor

from ...storage.notebook_storage import NotebookStorage
from ..dialogs.share_notebook_dialog import ShareNotebookDialog


# ─── Move-To Folder Picker Dialog ─────────────────────────────────────────────

class FolderPickerDialog(QDialog):
    """A dialog that shows a flat list of all folders (+ Root) for Move-To selection."""

    def __init__(self, folders: list[dict], exclude_id: str = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Move to Folder")
        self.setMinimumWidth(320)
        self.setMinimumHeight(300)
        self.selected_folder_id = None

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        lbl = QLabel("Choose a destination folder:", self)
        lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #1c1c1e;")
        layout.addWidget(lbl)

        self.list_widget = QListWidget(self)
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #e5e5ea;
                border-radius: 8px;
                font-size: 13px;
            }
            QListWidget::item { padding: 8px; }
            QListWidget::item:selected { background: #007aff; color: white; border-radius: 4px; }
        """)

        # Add Root option
        root_item = QListWidgetItem("📓 Notebooks (Root)")
        root_item.setData(Qt.ItemDataRole.UserRole, None)
        self.list_widget.addItem(root_item)

        # Build indented folder list
        all_folders = {f["id"]: f for f in folders}

        def _add_items(parent_id, depth):
            children = [f for f in folders if f.get("parent_id") == parent_id and f["id"] != exclude_id]
            children.sort(key=lambda x: x["name"].lower())
            for f in children:
                indent = "    " * depth
                item = QListWidgetItem(f"{indent}📁 {f['name']}")
                item.setData(Qt.ItemDataRole.UserRole, f["id"])
                self.list_widget.addItem(item)
                _add_items(f["id"], depth + 1)

        _add_items(None, 0)
        self.list_widget.setCurrentRow(0)
        layout.addWidget(self.list_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self):
        item = self.list_widget.currentItem()
        if item:
            self.selected_folder_id = item.data(Qt.ItemDataRole.UserRole)
        self.accept()


# ─── Folder Card Widget ────────────────────────────────────────────────────────

class FolderCardWidget(QFrame):
    """Card representing a folder inside the main content panel. Double-click to navigate in."""
    open_clicked = pyqtSignal(str)          # folder_id
    rename_requested = pyqtSignal(str)      # folder_id
    move_requested = pyqtSignal(str)        # folder_id
    delete_requested = pyqtSignal(str)      # folder_id

    def __init__(self, folder: dict, item_count: int = 0, parent=None):
        super().__init__(parent)
        self.folder_id = folder["id"]
        self.folder_name = folder["name"]

        self.setObjectName("FolderCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self.setStyleSheet("""
            QFrame#FolderCard {
                background-color: #ffffff;
                border: 1px solid #e5e5ea;
                border-radius: 10px;
            }
            QFrame#FolderCard:hover {
                border-color: #007aff;
                background-color: #f0f7ff;
            }
            QLabel#FolderCardTitle {
                font-size: 14px;
                font-weight: 600;
                color: #1c1c1e;
            }
            QLabel#FolderCardSub {
                font-size: 11px;
                color: #8e8e93;
            }
            QPushButton#BtnMenu {
                background: transparent;
                border: none;
                font-size: 16px;
                color: #8e8e93;
                padding: 4px;
                border-radius: 6px;
            }
            QPushButton#BtnMenu:hover {
                background-color: #e5e5ea;
                color: #1c1c1e;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 12, 10)
        layout.setSpacing(12)

        lbl_icon = QLabel("📁", self)
        lbl_icon.setStyleSheet("font-size: 24px; background: transparent;")

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        lbl_name = QLabel(self.folder_name, self)
        lbl_name.setObjectName("FolderCardTitle")
        lbl_sub = QLabel(f"{item_count} item{'s' if item_count != 1 else ''}", self)
        lbl_sub.setObjectName("FolderCardSub")
        text_box.addWidget(lbl_name)
        text_box.addWidget(lbl_sub)

        btn_menu = QPushButton("⋯", self)
        btn_menu.setObjectName("BtnMenu")
        btn_menu.setFixedSize(28, 28)
        btn_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_menu.clicked.connect(lambda: self._show_context_menu(btn_menu.rect().bottomLeft()))

        layout.addWidget(lbl_icon)
        layout.addLayout(text_box)
        layout.addStretch()
        layout.addWidget(btn_menu)

    def mouseDoubleClickEvent(self, event):
        self.open_clicked.emit(self.folder_id)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #ffffff; border: 1px solid #d1d1d6;
                border-radius: 8px; padding: 4px; font-size: 12px;
            }
            QMenu::item { padding: 7px 16px; border-radius: 4px; color: #1c1c1e; }
            QMenu::item:selected { background-color: #007aff; color: white; }
        """)
        act_open = menu.addAction("📂 Open")
        act_rename = menu.addAction("✏️ Rename")
        act_move = menu.addAction("📋 Move to...")
        menu.addSeparator()
        act_delete = menu.addAction("🗑️ Delete")

        global_pos = self.mapToGlobal(pos)

        action = menu.exec(global_pos)
        if action == act_open:
            self.open_clicked.emit(self.folder_id)
        elif action == act_rename:
            self.rename_requested.emit(self.folder_id)
        elif action == act_move:
            self.move_requested.emit(self.folder_id)
        elif action == act_delete:
            self.delete_requested.emit(self.folder_id)


# ─── Notebook Row Widget ───────────────────────────────────────────────────────

class NotebookRowWidget(QFrame):
    open_clicked = pyqtSignal(str)          # notebook_id
    share_clicked = pyqtSignal(str, str)    # notebook_id, notebook_name
    rename_clicked = pyqtSignal(str, str)   # notebook_id, notebook_name
    git_clicked = pyqtSignal(str, str)      # notebook_id, notebook_name
    delete_clicked = pyqtSignal(str, str)   # notebook_id, notebook_name
    rename_requested = pyqtSignal(str)      # notebook_id
    move_requested = pyqtSignal(str)        # notebook_id

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.notebook_id = data.get("id", "")
        self.notebook_name = data.get("name", "Untitled Notebook")
        self.updated_at = data.get("updated_at", "")

        self.setStyleSheet("""
            QFrame#NotebookRow {
                background-color: #ffffff;
                border: 1px solid #e5e5ea;
                border-radius: 10px;
                padding: 6px;
            }
            QFrame#NotebookRow:hover {
                border-color: #007aff;
                background-color: #f8f9ff;
            }
            QLabel#TitleLabel { font-size: 14px; font-weight: 600; color: #1c1c1e; }
            QLabel#SubLabel { font-size: 11px; color: #8e8e93; }
            QPushButton#BtnOpen {
                background-color: #007aff; color: white; font-weight: 600; font-size: 12px;
                border: none; border-radius: 6px; padding: 6px 14px;
            }
            QPushButton#BtnOpen:hover { background-color: #0056b3; }
            QPushButton#BtnMore, QPushButton#BtnMenu {
                background-color: transparent;
                color: #1c1c1e;
                border: 1px solid #d1d1d6;
                font-weight: bold;
                font-size: 16px;
                padding: 2px 8px;
                border-radius: 6px;
            }
            QPushButton#BtnMore:hover, QPushButton#BtnMenu:hover {
                background-color: #e5e5ea;
            }
        """)

        self.setObjectName("NotebookRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        lbl_icon = QLabel("📓", self)
        lbl_icon.setStyleSheet("font-size: 22px; background: transparent;")

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        lbl_title = QLabel(self.notebook_name, self)
        lbl_title.setObjectName("TitleLabel")
        lbl_sub = QLabel(f"Last saved: {self.updated_at}", self)
        lbl_sub.setObjectName("SubLabel")
        text_box.addWidget(lbl_title)
        text_box.addWidget(lbl_sub)

        btn_open = QPushButton("Open", self)
        btn_open.setObjectName("BtnOpen")
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.clicked.connect(lambda: self.open_clicked.emit(self.notebook_id))

        btn_more = QPushButton("⋮", self)
        btn_more.setObjectName("BtnMore")
        btn_more.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_more.setToolTip("Notebook Actions")
        btn_more.clicked.connect(self._show_context_menu)

        layout.addWidget(lbl_icon)
        layout.addLayout(text_box)
        layout.addStretch()
        layout.addWidget(btn_open)
        layout.addWidget(btn_more)

    def _show_context_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 13px;
                color: #1c1c1e;
            }
            QMenu::item:selected {
                background-color: #007aff;
                color: white;
            }
        """)

        act_share = QAction("☌ Share Notebook (Drive)", menu)
        act_share.triggered.connect(lambda: self.share_clicked.emit(self.notebook_id, self.notebook_name))
        menu.addAction(act_share)

        act_rename = QAction("✏️ Rename", menu)
        act_rename.triggered.connect(lambda: self.rename_requested.emit(self.notebook_id))
        menu.addAction(act_rename)

        act_move = QAction("📋 Move to...", menu)
        act_move.triggered.connect(lambda: self.move_requested.emit(self.notebook_id))
        menu.addAction(act_move)

        act_git = QAction("⎇ Git Version History", menu)
        act_git.triggered.connect(lambda: self.git_clicked.emit(self.notebook_id, self.notebook_name))
        menu.addAction(act_git)

        menu.addSeparator()

        act_del = QAction("🗑️ Delete", menu)
        act_del.triggered.connect(lambda: self.delete_clicked.emit(self.notebook_id, self.notebook_name))
        menu.addAction(act_del)

        btn = self.sender()
        pos = btn.mapToGlobal(btn.rect().bottomLeft()) if btn else QCursor.pos()
        menu.exec(pos)


# ─── Breadcrumb Bar ────────────────────────────────────────────────────────────

class BreadcrumbBar(QFrame):
    """Clickable breadcrumb showing current folder path: Notebooks > Maths > Algebra"""
    crumb_clicked = pyqtSignal(object)  # folder_id (str or None)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QFrame { background: transparent; }")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def set_path(self, path: list[dict]):
        """
        path: [{id: None, name: 'Notebooks'}, {id: 'fld_...', name: 'Maths'}, ...]
        """
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for i, crumb in enumerate(path):
            is_last = i == len(path) - 1
            btn = QPushButton(crumb["name"], self)
            fid = crumb["id"]
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    font-size: 13px;
                    font-weight: {'700' if is_last else '500'};
                    color: {'#1c1c1e' if is_last else '#007aff'};
                    padding: 2px 4px;
                }}
                QPushButton:hover {{
                    {'text-decoration: none;' if is_last else 'text-decoration: underline;'}
                }}
            """)
            if not is_last:
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda checked, id=fid: self.crumb_clicked.emit(id))

            self._layout.addWidget(btn)

            if not is_last:
                sep = QLabel("›", self)
                sep.setStyleSheet("color: #8e8e93; font-size: 14px; padding: 0 2px;")
                self._layout.addWidget(sep)


# ─── Main Notebooks Panel ──────────────────────────────────────────────────────

class NotebooksPanel(QWidget):
    open_notebook_requested = pyqtSignal(str)   # notebook_id
    create_notebook_requested = pyqtSignal()
    git_vcs_requested = pyqtSignal(str)          # notebook_id
    folder_navigated = pyqtSignal(object)        # folder_id (str or None) — for sidebar sync

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_folder_id = None  # None = root

        self.setStyleSheet("""
            QWidget#NotebooksPanelRoot { background-color: #f2f2f7; }
            QLabel#PanelHeaderTitle {
                font-size: 22px; font-weight: 700; color: #1c1c1e;
            }
            QPushButton#BtnNewNotebook {
                background-color: #007aff; color: white; font-size: 13px; font-weight: 600;
                border: none; border-radius: 8px; padding: 8px 16px;
            }
            QPushButton#BtnNewNotebook:hover { background-color: #0056b3; }
            QPushButton#BtnNewFolder {
                background-color: #ffffff; color: #1c1c1e; font-size: 13px; font-weight: 600;
                border: 1px solid #d1d1d6; border-radius: 8px; padding: 8px 16px;
            }
            QPushButton#BtnNewFolder:hover { background-color: #e5e5ea; }
        """)

        self.setObjectName("NotebooksPanelRoot")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(12)

        # ── Header Row ──
        header = QHBoxLayout()
        lbl_header = QLabel("🗂 Saved Notebooks", self)
        lbl_header.setObjectName("PanelHeaderTitle")

        btn_new_folder = QPushButton("📁 New Folder", self)
        btn_new_folder.setObjectName("BtnNewFolder")
        btn_new_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new_folder.clicked.connect(self._create_folder)

        btn_new = QPushButton("➕ New Notebook", self)
        btn_new.setObjectName("BtnNewNotebook")
        btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new.clicked.connect(self._new_notebook_in_current_folder)

        header.addWidget(lbl_header)
        header.addStretch()
        header.addWidget(btn_new_folder)
        header.addSpacing(8)
        header.addWidget(btn_new)
        main_layout.addLayout(header)

        # ── Breadcrumb Bar ──
        self.breadcrumb = BreadcrumbBar(self)
        self.breadcrumb.crumb_clicked.connect(self.navigate_to_folder)
        main_layout.addWidget(self.breadcrumb)

        # ── Scroll Area for Cards ──
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(10)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.list_container)
        main_layout.addWidget(self.scroll_area)

        self.refresh()

    def navigate_to_folder(self, folder_id):
        """Navigate into a folder (folder_id=None = root). Called by breadcrumb and folder card double-click."""
        self._current_folder_id = folder_id or None
        self.folder_navigated.emit(folder_id)
        self.refresh()

    def _open_share_dialog(self, notebook_id: str, name: str):
        dialog = ShareNotebookDialog(notebook_id, name, self)
        dialog.exec()

    def refresh(self):
        """Reload current folder's direct children: sub-folders then notebooks."""
        while self.list_layout.count():
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Update breadcrumb
        path = NotebookStorage.get_breadcrumb_path(self._current_folder_id)
        self.breadcrumb.set_path(path)

        try:
            all_folders = NotebookStorage.get_folder_tree()
            all_notebooks = NotebookStorage.get_index()

            # Direct child folders of current folder
            child_folders = [f for f in all_folders if f.get("parent_id") == self._current_folder_id]
            child_folders.sort(key=lambda x: x["name"].lower())

            # Notebooks in current folder
            child_notebooks = [nb for nb in all_notebooks if nb.get("folder_id") == self._current_folder_id]

            if not child_folders and not child_notebooks:
                self._show_empty()
                return

            # ── Folder Cards ──
            if child_folders:
                lbl_sec = QLabel("Folders", self.list_container)
                lbl_sec.setStyleSheet("font-size: 11px; font-weight: bold; color: #8e8e93; letter-spacing: 0.5px; padding: 4px 0;")
                self.list_layout.addWidget(lbl_sec)

            # Count items per folder
            folder_nb_counts = {}
            for nb in all_notebooks:
                fid = nb.get("folder_id")
                if fid:
                    folder_nb_counts[fid] = folder_nb_counts.get(fid, 0) + 1
            sub_counts = {}
            for f in all_folders:
                pid = f.get("parent_id")
                if pid:
                    sub_counts[pid] = sub_counts.get(pid, 0) + 1

            for folder in child_folders:
                fid = folder["id"]
                total = folder_nb_counts.get(fid, 0) + sub_counts.get(fid, 0)
                card = FolderCardWidget(folder, item_count=total, parent=self.list_container)
                card.open_clicked.connect(self.navigate_to_folder)
                card.rename_requested.connect(self._rename_folder)
                card.move_requested.connect(self._move_folder)
                card.delete_requested.connect(self._delete_folder)
                self.list_layout.addWidget(card)

            # ── Notebook Rows ──
            if child_notebooks:
                lbl_sec2 = QLabel("Notebooks", self.list_container)
                lbl_sec2.setStyleSheet("font-size: 11px; font-weight: bold; color: #8e8e93; letter-spacing: 0.5px; padding: 4px 0;")
                self.list_layout.addWidget(lbl_sec2)

            for nb in child_notebooks:
                row = NotebookRowWidget(nb, self.list_container)
                row.open_clicked.connect(self.open_notebook_requested.emit)
                row.share_clicked.connect(self._open_share_dialog)
                row.git_clicked.connect(lambda nb_id, name: self.git_vcs_requested.emit(nb_id))
                row.delete_clicked.connect(self._confirm_delete_notebook)
                row.rename_requested.connect(self._rename_notebook)
                row.move_requested.connect(self._move_notebook)
                self.list_layout.addWidget(row)

        except Exception as err:
            QMessageBox.warning(self, "Error Loading Notebooks", f"Could not load notebooks:\n{err}")

    def _show_empty(self):
        lbl = QLabel(
            "📭 This folder is empty.\nCreate a sub-folder or click '➕ New Notebook'.",
            self.list_container,
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size: 14px; color: #8e8e93; padding: 40px;")
        self.list_layout.addWidget(lbl)

    # ── Create ──────────────────────────────────────────────────────────────────

    def _new_notebook_in_current_folder(self):
        name, ok = QInputDialog.getText(self, "New Notebook", "Notebook name:", text="Untitled Notebook")
        if ok and name.strip():
            NotebookStorage.create_notebook(name.strip(), folder_id=self._current_folder_id)
            self.refresh()

    def _create_folder(self):
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name.strip():
            try:
                NotebookStorage.create_folder(name.strip(), parent_id=self._current_folder_id)
                self.refresh()
            except ValueError as e:
                QMessageBox.warning(self, "Cannot Create Folder", str(e))

    # ── Rename ──────────────────────────────────────────────────────────────────

    def _rename_folder(self, folder_id: str):
        folders = {f["id"]: f for f in NotebookStorage.get_folders()}
        current = folders.get(folder_id, {}).get("name", "")
        name, ok = QInputDialog.getText(self, "Rename Folder", "New name:", text=current)
        if ok and name.strip():
            NotebookStorage.rename_folder(folder_id, name.strip())
            self.refresh()

    def _rename_notebook(self, notebook_id: str):
        index = {nb["id"]: nb for nb in NotebookStorage.get_index()}
        current = index.get(notebook_id, {}).get("name", "")
        name, ok = QInputDialog.getText(self, "Rename Notebook", "New name:", text=current)
        if ok and name.strip():
            NotebookStorage.rename_notebook(notebook_id, name.strip())
            self.refresh()

    # ── Move ────────────────────────────────────────────────────────────────────

    def _move_notebook(self, notebook_id: str):
        folders = NotebookStorage.get_folder_tree()
        dlg = FolderPickerDialog(folders, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            target = dlg.selected_folder_id
            NotebookStorage.move_notebook(notebook_id, target)
            self.refresh()

    def _move_folder(self, folder_id: str):
        folders = NotebookStorage.get_folder_tree()
        dlg = FolderPickerDialog(folders, exclude_id=folder_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            target = dlg.selected_folder_id
            try:
                NotebookStorage.move_folder(folder_id, target)
                self.refresh()
            except ValueError as e:
                QMessageBox.warning(self, "Cannot Move Folder", str(e))

    # ── Delete ──────────────────────────────────────────────────────────────────

    def _confirm_delete_notebook(self, notebook_id: str, name: str):
        reply = QMessageBox.question(
            self, "Delete Notebook",
            f"Are you sure you want to delete '{name}'?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                NotebookStorage.delete_notebook(notebook_id)
                self.refresh()
            except Exception as err:
                QMessageBox.warning(self, "Delete Failed", f"Failed to delete notebook:\n{err}")

    def _delete_folder(self, folder_id: str):
        preview = NotebookStorage.get_cascade_preview(folder_id)
        folder_names = preview["folder_names"]
        nb_names = preview["notebook_names"]

        details = []
        if len(folder_names) > 1:
            details.append(f"• {len(folder_names)} folder(s): {', '.join(folder_names[:4])}")
        if nb_names:
            details.append(f"• {len(nb_names)} notebook(s): {', '.join(nb_names[:4])}")

        body = "This will permanently delete:\n" + "\n".join(details) if details else "This folder is empty."
        fname = folder_names[0] if folder_names else folder_id

        reply = QMessageBox.warning(
            self, "Delete Folder",
            f"Delete '{fname}'?\n\n{body}\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            NotebookStorage.delete_folder_cascade(folder_id)
            self.refresh()
