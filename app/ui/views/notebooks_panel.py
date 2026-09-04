"""
Notebooks Management View Panel (Monochrome / Technical Aesthetic)
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
import qtawesome as qta

from ...storage.notebook_storage import NotebookStorage
from ..dialogs.share_notebook_dialog import ShareNotebookDialog
from ..theme_manager import ThemeManager
from ..kestrel_theme import MONO_FONT, primary_button_qss, ghost_button_qss, menu_qss


# ─── Move-To Folder Picker Dialog ─────────────────────────────────────────────

class FolderPickerDialog(QDialog):
    """A dialog that shows a flat list of all folders (+ Root) for Move-To selection."""

    def __init__(self, folders: list[dict], exclude_id: str = None, parent=None):
        super().__init__(parent)
        c = ThemeManager.instance().get_colors()
        self.setWindowTitle("Move to Folder")
        self.setMinimumWidth(340)
        self.setMinimumHeight(300)
        self.selected_folder_id = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        lbl = QLabel("CHOOSE DESTINATION FOLDER:", self)
        lbl.setStyleSheet(f"font-size: 11px; font-weight: 700; font-family: {MONO_FONT}; color: {c['text_secondary']}; letter-spacing: 1px;")
        layout.addWidget(lbl)

        self.list_widget = QListWidget(self)
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                font-family: {MONO_FONT};
                font-size: 12px;
                background-color: {c['bg_card']};
                color: {c['text_primary']};
            }}
            QListWidget::item {{ padding: 8px; }}
            QListWidget::item:selected {{ background: {c['accent']}; color: {c['accent_text']}; }}
        """)

        # Add Root option
        root_item = QListWidgetItem(qta.icon('ri.book-2-line', color=c['text_primary']), "Notebooks (Root)")
        root_item.setData(Qt.ItemDataRole.UserRole, None)
        self.list_widget.addItem(root_item)

        # Build indented folder list
        def _add_items(parent_id, depth):
            children = [f for f in folders if f.get("parent_id") == parent_id and f["id"] != exclude_id]
            children.sort(key=lambda x: x["name"].lower())
            for f in children:
                indent = "    " * depth
                item = QListWidgetItem(qta.icon('ri.folder-line', color=c['text_secondary']), f"{indent}{f['name']}")
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
        c = ThemeManager.instance().get_colors()

        self.setObjectName("FolderCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self.setStyleSheet(f"""
            QFrame#FolderCard {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border_color']};
                border-radius: 4px;
            }}
            QFrame#FolderCard:hover {{
                border-color: {c['accent']};
                background-color: {c['panel_card_bg']};
            }}
            QLabel#FolderCardTitle {{
                font-size: 13px;
                font-weight: 700;
                font-family: {MONO_FONT};
                color: {c['text_primary']};
            }}
            QLabel#FolderCardSub {{
                font-size: 11px;
                font-family: {MONO_FONT};
                color: {c['text_secondary']};
            }}
            QPushButton#BtnMenu {{
                background: transparent;
                border: none;
                font-size: 14px;
                color: {c['text_secondary']};
                padding: 2px 6px;
                border-radius: 2px;
            }}
            QPushButton#BtnMenu:hover {{
                background-color: {c['border_color']};
                color: {c['text_primary']};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 12, 10)
        layout.setSpacing(12)

        lbl_icon = QLabel(self)
        lbl_icon.setPixmap(qta.icon('ri.folder-fill', color=c['accent']).pixmap(24, 24))
        lbl_icon.setStyleSheet("background: transparent;")

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
        c = ThemeManager.instance().get_colors()
        menu = QMenu(self)
        menu.setStyleSheet(menu_qss(c))

        act_open = menu.addAction("Open")
        act_rename = menu.addAction("Rename")
        act_move = menu.addAction("Move to...")
        menu.addSeparator()
        act_delete = menu.addAction("Delete")

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
        c = ThemeManager.instance().get_colors()

        self.setStyleSheet(f"""
            QFrame#NotebookRow {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border_color']};
                border-radius: 4px;
                padding: 4px;
            }}
            QFrame#NotebookRow:hover {{
                border-color: {c['accent']};
                background-color: {c['panel_card_bg']};
            }}
            QLabel#TitleLabel {{
                font-size: 13px;
                font-weight: 700;
                font-family: {MONO_FONT};
                color: {c['text_primary']};
            }}
            QLabel#SubLabel {{
                font-size: 11px;
                font-family: {MONO_FONT};
                color: {c['text_secondary']};
            }}
            QPushButton#BtnOpen {{
                background-color: {c['accent']};
                color: {c['accent_text']};
                font-weight: 700;
                font-family: {MONO_FONT};
                font-size: 11px;
                border: 1px solid {c['accent']};
                border-radius: 2px;
                padding: 5px 14px;
                letter-spacing: 0.5px;
            }}
            QPushButton#BtnOpen:hover {{
                background-color: {c['accent_hover']};
            }}
            QPushButton#BtnMore {{
                background-color: transparent;
                color: {c['text_secondary']};
                border: 1px solid {c['border_color']};
                font-weight: bold;
                font-size: 13px;
                padding: 2px 6px;
                border-radius: 2px;
            }}
            QPushButton#BtnMore:hover {{
                border-color: {c['accent']};
                color: {c['text_primary']};
            }}
        """)

        self.setObjectName("NotebookRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        lbl_icon = QLabel(self)
        lbl_icon.setPixmap(qta.icon('ri.book-2-line', color=c['text_primary']).pixmap(20, 20))
        lbl_icon.setStyleSheet("background: transparent;")

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        lbl_title = QLabel(self.notebook_name, self)
        lbl_title.setObjectName("TitleLabel")
        lbl_sub = QLabel(f"Last saved: {self.updated_at}", self)
        lbl_sub.setObjectName("SubLabel")
        text_box.addWidget(lbl_title)
        text_box.addWidget(lbl_sub)

        btn_open = QPushButton("OPEN", self)
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
        c = ThemeManager.instance().get_colors()
        menu = QMenu(self)
        menu.setStyleSheet(menu_qss(c))

        act_share = QAction(qta.icon('ri.share-line'), "Share Notebook (Drive)", menu)
        act_share.triggered.connect(lambda: self.share_clicked.emit(self.notebook_id, self.notebook_name))
        menu.addAction(act_share)

        act_rename = QAction(qta.icon('ri.edit-line'), "Rename", menu)
        act_rename.triggered.connect(lambda: self.rename_requested.emit(self.notebook_id))
        menu.addAction(act_rename)

        act_move = QAction(qta.icon('ri.folder-transfer-line'), "Move to...", menu)
        act_move.triggered.connect(lambda: self.move_requested.emit(self.notebook_id))
        menu.addAction(act_move)

        act_git = QAction(qta.icon('ri.history-line'), "Version History", menu)
        act_git.triggered.connect(lambda: self.git_clicked.emit(self.notebook_id, self.notebook_name))
        menu.addAction(act_git)

        menu.addSeparator()

        act_del = QAction(qta.icon('ri.delete-bin-line'), "Delete", menu)
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
        self._layout.setSpacing(2)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def set_path(self, path: list[dict]):
        c = ThemeManager.instance().get_colors()
        while self._layout.count():
            child = self._layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for i, crumb in enumerate(path):
            is_last = i == len(path) - 1
            btn = QPushButton(crumb["name"].upper(), self)
            fid = crumb["id"]
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    font-family: {MONO_FONT};
                    font-size: 11px;
                    font-weight: {'700' if is_last else '500'};
                    letter-spacing: 0.5px;
                    color: {c['text_primary'] if is_last else c['text_secondary']};
                    padding: 2px 4px;
                }}
                QPushButton:hover {{
                    color: {c['text_primary']};
                }}
            """)
            if not is_last:
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda checked, id=fid: self.crumb_clicked.emit(id))

            self._layout.addWidget(btn)

            if not is_last:
                sep = QLabel(">", self)
                sep.setStyleSheet(f"color: {c['text_secondary']}; font-family: {MONO_FONT}; font-size: 11px; padding: 0 2px;")
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
        self.setObjectName("NotebooksPanelRoot")
        self._setup_ui()
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme(ThemeManager.instance().current_theme)
        self.refresh()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(14)

        # ── Header Row ──
        header = QHBoxLayout()
        self.lbl_header = QLabel("Saved Notebooks", self)
        self.lbl_header.setObjectName("PanelHeaderTitle")

        self.btn_new_folder = QPushButton("+ NEW FOLDER", self)
        self.btn_new_folder.setObjectName("BtnNewFolder")
        self.btn_new_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new_folder.clicked.connect(self._create_folder)

        self.btn_new = QPushButton("+ NEW NOTEBOOK", self)
        self.btn_new.setObjectName("BtnNewNotebook")
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new.clicked.connect(self._new_notebook_in_current_folder)

        header.addWidget(self.lbl_header)
        header.addStretch()
        header.addWidget(self.btn_new_folder)
        header.addSpacing(8)
        header.addWidget(self.btn_new)
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
        self.list_layout.setSpacing(8)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.list_container)
        main_layout.addWidget(self.scroll_area)

    def _apply_theme(self, theme_name: str = "light"):
        c = ThemeManager.instance().get_colors()
        self.setStyleSheet(f"QWidget#NotebooksPanelRoot {{ background-color: {c['bg_app']}; }}")

        self.lbl_header.setStyleSheet(f"""
            font-size: 22px; font-weight: 800; color: {c['text_primary']};
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        """)

        self.btn_new.setStyleSheet(primary_button_qss(c))
        self.btn_new_folder.setStyleSheet(ghost_button_qss(c))

    def navigate_to_folder(self, folder_id):
        """Navigate into a folder (folder_id=None = root). Called by breadcrumb and folder card double-click."""
        self._current_folder_id = folder_id or None
        self.folder_navigated.emit(folder_id)
        self.refresh()

    def _open_share_dialog(self, notebook_id: str, name: str):
        dialog = ShareNotebookDialog(notebook_id=notebook_id, notebook_name=name, parent=self)
        dialog.exec()

    def _open_git_vcs(self, notebook_id: str, name: str):
        self.git_vcs_requested.emit(notebook_id)

    def _new_notebook_in_current_folder(self):
        """Create a new notebook tagged to the current folder and open it."""
        from ...storage.notebook_storage import NotebookStorage
        nb_id = NotebookStorage.create_notebook(
            name="Untitled Notebook",
            folder_id=self._current_folder_id
        )
        self.create_notebook_requested.emit()
        self.open_notebook_requested.emit(nb_id)

    def _create_folder(self):
        name, ok = QInputDialog.getText(
            self, "New Folder", "Enter folder name:",
            text="New Folder"
        )
        if ok and name.strip():
            NotebookStorage.create_folder(name.strip(), parent_id=self._current_folder_id)
            self.refresh()

    def _rename_folder(self, folder_id: str):
        folder = NotebookStorage.get_folder(folder_id)
        current_name = folder["name"] if folder else ""
        name, ok = QInputDialog.getText(
            self, "Rename Folder", "Enter new name:",
            text=current_name
        )
        if ok and name.strip() and name.strip() != current_name:
            NotebookStorage.rename_folder(folder_id, name.strip())
            self.refresh()

    def _move_folder(self, folder_id: str):
        folders = NotebookStorage.get_all_folders()
        dlg = FolderPickerDialog(folders, exclude_id=folder_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            dest_id = dlg.selected_folder_id
            if dest_id == folder_id:
                QMessageBox.warning(self, "Invalid Move", "Cannot move a folder into itself.")
                return
            NotebookStorage.move_folder(folder_id, dest_id)
            self.refresh()

    def _delete_folder(self, folder_id: str):
        reply = QMessageBox.question(
            self, "Delete Folder",
            "Are you sure you want to delete this folder?\nNotebooks inside will be moved to the parent folder.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            NotebookStorage.delete_folder(folder_id)
            self.refresh()

    def _rename_notebook(self, notebook_id: str):
        meta = NotebookStorage.get_notebook(notebook_id)
        current_name = meta.get("name", "") if meta else ""
        name, ok = QInputDialog.getText(
            self, "Rename Notebook", "Enter new name:",
            text=current_name
        )
        if ok and name.strip() and name.strip() != current_name:
            NotebookStorage.rename_notebook(notebook_id, name.strip())
            self.refresh()

    def _move_notebook(self, notebook_id: str):
        folders = NotebookStorage.get_all_folders()
        dlg = FolderPickerDialog(folders, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            NotebookStorage.move_notebook(notebook_id, dlg.selected_folder_id)
            self.refresh()

    def _delete_notebook(self, notebook_id: str, name: str):
        reply = QMessageBox.question(
            self, "Delete Notebook",
            f"Are you sure you want to delete '{name}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            NotebookStorage.delete_notebook(notebook_id)
            self.refresh()

    def refresh(self):
        """Re-renders breadcrumb, folder cards, and notebook cards for current folder."""
        # Update breadcrumb
        path = NotebookStorage.get_breadcrumb_path(self._current_folder_id)
        self.breadcrumb.set_path(path)

        # Clear existing cards
        while self.list_layout.count():
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Load folders in current folder
        folders = [f for f in NotebookStorage.get_folders() if f.get('parent_id') == self._current_folder_id]
        # Load notebooks in current folder
        notebooks = [nb for nb in NotebookStorage.get_index() if nb.get('folder_id') == self._current_folder_id]

        c = ThemeManager.instance().get_colors()

        if not folders and not notebooks:
            empty_lbl = QLabel("This folder is empty. Create a notebook or subfolder above.", self)
            empty_lbl.setStyleSheet(f"font-size: 12px; color: {c['text_secondary']}; font-family: {MONO_FONT}; padding: 30px;")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_layout.addWidget(empty_lbl)
            return

        # Section 1: Folders
        if folders:
            lbl_sec_f = QLabel("FOLDERS", self)
            lbl_sec_f.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {c['text_secondary']}; font-family: {MONO_FONT}; letter-spacing: 1.5px; padding-top: 4px;")
            self.list_layout.addWidget(lbl_sec_f)

            for f in folders:
                # Count items inside this subfolder
                sub_count = len([sf for sf in NotebookStorage.get_folders() if sf.get('parent_id') == f["id"]]) + len([nb for nb in NotebookStorage.get_index() if nb.get('folder_id') == f["id"]])
                card = FolderCardWidget(f, item_count=sub_count, parent=self)
                card.open_clicked.connect(self.navigate_to_folder)
                card.rename_requested.connect(self._rename_folder)
                card.move_requested.connect(self._move_folder)
                card.delete_requested.connect(self._delete_folder)
                self.list_layout.addWidget(card)

        # Section 2: Notebooks
        if notebooks:
            lbl_sec_n = QLabel("NOTEBOOKS", self)
            lbl_sec_n.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {c['text_secondary']}; font-family: {MONO_FONT}; letter-spacing: 1.5px; padding-top: 10px;")
            self.list_layout.addWidget(lbl_sec_n)

            for nb in notebooks:
                row = NotebookRowWidget(nb, parent=self)
                row.open_clicked.connect(self.open_notebook_requested.emit)
                row.share_clicked.connect(self._open_share_dialog)
                row.rename_requested.connect(self._rename_notebook)
                row.move_requested.connect(self._move_notebook)
                row.git_clicked.connect(self._open_git_vcs)
                row.delete_clicked.connect(self._delete_notebook)
                self.list_layout.addWidget(row)
