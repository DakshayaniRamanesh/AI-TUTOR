"""
Notebooks Management View Panel — Displays list of saved notebooks with load, 3-dots share menu, rename, and delete actions
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QMessageBox, QMenu, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from ...storage.notebook_storage import NotebookStorage
from ..dialogs.share_notebook_dialog import ShareNotebookDialog

class NotebookRowWidget(QFrame):
    open_clicked = pyqtSignal(str)   # notebook_id
    share_clicked = pyqtSignal(str, str) # notebook_id, notebook_name
    rename_clicked = pyqtSignal(str, str) # notebook_id, notebook_name
    git_clicked = pyqtSignal(str, str)   # notebook_id, notebook_name
    delete_clicked = pyqtSignal(str, str) # notebook_id, notebook_name

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
            QLabel#TitleLabel {
                font-size: 14px;
                font-weight: 600;
                color: #1c1c1e;
            }
            QLabel#SubLabel {
                font-size: 11px;
                color: #8e8e93;
            }
            QPushButton#BtnOpen {
                background-color: #007aff;
                color: white;
                font-weight: 600;
                font-size: 12px;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton#BtnOpen:hover {
                background-color: #0056b3;
            }
            QPushButton#BtnMore {
                background-color: transparent;
                color: #1c1c1e;
                border: 1px solid #d1d1d6;
                font-weight: bold;
                font-size: 16px;
                padding: 2px 8px;
                border-radius: 6px;
            }
            QPushButton#BtnMore:hover {
                background-color: #e5e5ea;
            }
        """)

        self.setObjectName("NotebookRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # Icon + Text
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

        layout.addWidget(lbl_icon)
        layout.addLayout(text_box)
        layout.addStretch()

        # Action Buttons
        btn_open = QPushButton("Open", self)
        btn_open.setObjectName("BtnOpen")
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.clicked.connect(lambda: self.open_clicked.emit(self.notebook_id))

        btn_more = QPushButton("⋮", self)
        btn_more.setObjectName("BtnMore")
        btn_more.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_more.setToolTip("Notebook Actions (Share, Rename, Git, Delete)")
        btn_more.clicked.connect(self._show_context_menu)

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

        act_share = QAction("🔗 Share Notebook (Google Drive style)", menu)
        act_share.triggered.connect(lambda: self.share_clicked.emit(self.notebook_id, self.notebook_name))
        menu.addAction(act_share)

        act_rename = QAction("✏️ Rename Notebook", menu)
        act_rename.triggered.connect(lambda: self.rename_clicked.emit(self.notebook_id, self.notebook_name))
        menu.addAction(act_rename)

        act_git = QAction("🔀 Git Version History", menu)
        act_git.triggered.connect(lambda: self.git_clicked.emit(self.notebook_id, self.notebook_name))
        menu.addAction(act_git)

        menu.addSeparator()

        act_del = QAction("🗑️ Delete Notebook", menu)
        act_del.triggered.connect(lambda: self.delete_clicked.emit(self.notebook_id, self.notebook_name))
        menu.addAction(act_del)

        btn = self.sender()
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

class NotebooksPanel(QWidget):
    open_notebook_requested = pyqtSignal(str)   # notebook_id
    create_notebook_requested = pyqtSignal()
    git_vcs_requested = pyqtSignal(str)          # notebook_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QWidget#NotebooksPanelRoot {
                background-color: #f2f2f7;
            }
            QLabel#PanelHeaderTitle {
                font-size: 22px;
                font-weight: 700;
                color: #1c1c1e;
            }
            QPushButton#BtnNewNotebook {
                background-color: #007aff;
                color: white;
                font-size: 13px;
                font-weight: 600;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
            }
            QPushButton#BtnNewNotebook:hover {
                background-color: #0056b3;
            }
        """)

        self.setObjectName("NotebooksPanelRoot")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # Header Bar
        header = QHBoxLayout()
        lbl_header = QLabel("📓 Saved Notebooks", self)
        lbl_header.setObjectName("PanelHeaderTitle")

        btn_new = QPushButton("➕ New Notebook", self)
        btn_new.setObjectName("BtnNewNotebook")
        btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new.clicked.connect(self.create_notebook_requested.emit)

        header.addWidget(lbl_header)
        header.addStretch()
        header.addWidget(btn_new)

        main_layout.addLayout(header)

        # Scroll Area for Notebook Cards
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

        # Initial Refresh
        self.refresh()

    def refresh(self):
        """
        Reloads index and populates rows in list view.
        """
        while self.list_layout.count():
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        try:
            notebooks = NotebookStorage.get_index()
            if not notebooks:
                empty_box = QVBoxLayout()
                empty_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
                
                lbl_empty = QLabel("📓 No saved notebooks yet.\nClick 'New Notebook' or click '💾 Save' on the top toolbar.", self)
                lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl_empty.setStyleSheet("font-size: 14px; color: #8e8e93; padding: 40px;")
                empty_box.addWidget(lbl_empty)
                
                empty_widget = QWidget()
                empty_widget.setLayout(empty_box)
                self.list_layout.addWidget(empty_widget)
            else:
                for nb in notebooks:
                    row = NotebookRowWidget(nb, self)
                    row.open_clicked.connect(self.open_notebook_requested.emit)
                    row.share_clicked.connect(self._open_share_dialog)
                    row.rename_clicked.connect(self._rename_notebook)
                    row.git_clicked.connect(lambda nb_id, name: self.git_vcs_requested.emit(nb_id))
                    row.delete_clicked.connect(self._confirm_delete)
                    self.list_layout.addWidget(row)
        except Exception as err:
            QMessageBox.warning(self, "Error Loading Notebooks", f"Could not load saved notebooks index:\n{err}")

    def _open_share_dialog(self, notebook_id: str, name: str):
        dialog = ShareNotebookDialog(notebook_id, name, self)
        dialog.exec()

    def _rename_notebook(self, notebook_id: str, current_name: str):
        new_name, ok = QInputDialog.getText(self, "Rename Notebook", "Enter new notebook title:", text=current_name)
        if ok and new_name.strip():
            try:
                payload = NotebookStorage.load_notebook(notebook_id)
                NotebookStorage.save_notebook(notebook_id, new_name.strip(), payload.get("items", []))
                self.refresh()
            except Exception as err:
                QMessageBox.warning(self, "Rename Failed", f"Could not rename notebook:\n{err}")

    def _confirm_delete(self, notebook_id: str, name: str):
        reply = QMessageBox.question(
            self,
            "Delete Notebook",
            f"Are you sure you want to delete '{name}'?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                NotebookStorage.delete_notebook(notebook_id)
                self.refresh()
            except Exception as err:
                QMessageBox.warning(self, "Delete Failed", f"Failed to delete notebook:\n{err}")
