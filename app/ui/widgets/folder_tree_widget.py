"""
Expandable/Collapsible Folder Tree Widget for the left sidebar.
Shows the full hierarchy with depth-indented rows, collapse/expand arrows, and right-click context menus.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QInputDialog, QMessageBox, QMenu, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QCursor


class FolderTreeRow(QFrame):
    """Single row in the sidebar folder tree."""
    clicked = pyqtSignal(str)           # folder_id
    new_subfolder = pyqtSignal(str)     # parent folder_id
    rename_requested = pyqtSignal(str)  # folder_id
    delete_requested = pyqtSignal(str)  # folder_id

    def __init__(self, folder: dict, depth: int = 0, is_expanded: bool = False, parent=None):
        super().__init__(parent)
        self.folder_id = folder["id"]
        self.folder_name = folder["name"]
        self.depth = depth
        self.is_expanded = is_expanded

        self.setObjectName("FolderTreeRow")
        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8 + depth * 16, 0, 8, 0)
        layout.setSpacing(4)

        # Collapse/expand arrow
        self.btn_arrow = QPushButton("▶" if not is_expanded else "▼", self)
        self.btn_arrow.setFixedSize(16, 16)
        self.btn_arrow.setObjectName("BtnArrow")
        self.btn_arrow.clicked.connect(self._toggle)

        # Folder icon + name
        lbl_icon = QLabel("📁", self)
        lbl_icon.setStyleSheet("font-size: 13px; background: transparent; border: none;")

        self.lbl_name = QLabel(self.folder_name, self)
        self.lbl_name.setObjectName("FolderLabel")
        self.lbl_name.setStyleSheet("font-size: 12px; font-weight: 500; color: #1c1c1e; background: transparent; border: none;")

        layout.addWidget(self.btn_arrow)
        layout.addWidget(lbl_icon)
        layout.addWidget(self.lbl_name)
        layout.addStretch()

        self._apply_style(False)

    def _apply_style(self, selected: bool):
        if selected:
            self.setStyleSheet("""
                QFrame#FolderTreeRow {
                    background-color: #007aff;
                    border-radius: 6px;
                }
                QLabel#FolderLabel { color: white; }
                QPushButton#BtnArrow {
                    background: transparent; border: none; color: white; font-size: 9px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#FolderTreeRow {
                    background-color: transparent;
                    border-radius: 6px;
                }
                QFrame#FolderTreeRow:hover {
                    background-color: #e5e5ea;
                }
                QLabel#FolderLabel { color: #1c1c1e; }
                QPushButton#BtnArrow {
                    background: transparent; border: none; color: #8e8e93; font-size: 9px;
                }
            """)

    def set_selected(self, selected: bool):
        self._apply_style(selected)

    def set_expanded(self, expanded: bool):
        self.is_expanded = expanded
        self.btn_arrow.setText("▼" if expanded else "▶")

    def set_has_children(self, has_children: bool):
        self.btn_arrow.setVisible(has_children)

    def _toggle(self):
        self.clicked.emit(self.folder_id)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.folder_id)
        super().mousePressEvent(event)

    def _show_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 8px;
                padding: 4px;
                font-size: 12px;
            }
            QMenu::item { padding: 6px 16px; border-radius: 4px; color: #1c1c1e; }
            QMenu::item:selected { background-color: #007aff; color: white; }
        """)
        act_new = menu.addAction("📁 New Sub-folder")
        act_rename = menu.addAction("✏️ Rename")
        menu.addSeparator()
        act_delete = menu.addAction("🗑️ Delete")

        action = menu.exec(self.mapToGlobal(pos))
        if action == act_new:
            self.new_subfolder.emit(self.folder_id)
        elif action == act_rename:
            self.rename_requested.emit(self.folder_id)
        elif action == act_delete:
            self.delete_requested.emit(self.folder_id)


class FolderTreeWidget(QWidget):
    """
    Expandable sidebar folder tree. Shows all folders in a collapsible hierarchy.
    Emits folder_selected(folder_id) when user clicks a folder.
    """
    folder_selected = pyqtSignal(str)    # folder_id
    tree_changed = pyqtSignal()          # refresh main panel

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded_ids = set()
        self._selected_id = None
        self._rows: dict[str, FolderTreeRow] = {}

        self.setStyleSheet("QWidget { background: transparent; }")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header label
        lbl = QLabel("FOLDERS", self)
        lbl.setStyleSheet("""
            font-size: 10px; font-weight: bold; color: #8e8e93;
            padding: 8px 12px 4px 12px; letter-spacing: 0.5px;
        """)
        outer.addWidget(lbl)

        # Scroll area for tree rows
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setMaximumHeight(300)

        self.tree_container = QWidget()
        self.tree_container.setStyleSheet("background: transparent;")
        self.tree_layout = QVBoxLayout(self.tree_container)
        self.tree_layout.setContentsMargins(4, 0, 4, 4)
        self.tree_layout.setSpacing(2)
        self.tree_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self.tree_container)
        outer.addWidget(scroll)

    def refresh(self, folders: list[dict], selected_id: str = None):
        """
        Rebuilds the tree from a flat folder list using parent_id adjacency.
        """
        self._selected_id = selected_id
        self._rows.clear()

        # Clear existing rows
        while self.tree_layout.count():
            child = self.tree_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not folders:
            lbl = QLabel("  No folders yet", self.tree_container)
            lbl.setStyleSheet("font-size: 11px; color: #c7c7cc; padding: 4px 12px;")
            self.tree_layout.addWidget(lbl)
            return

        # Build children map
        children_map: dict[str, list[dict]] = {}
        for f in folders:
            pid = f.get("parent_id")
            children_map.setdefault(pid, []).append(f)
        # Sort each level by name
        for pid in children_map:
            children_map[pid].sort(key=lambda x: x["name"].lower())

        def _add_rows(parent_id, depth):
            for folder in children_map.get(parent_id, []):
                fid = folder["id"]
                is_expanded = fid in self._expanded_ids
                has_children = bool(children_map.get(fid))

                row = FolderTreeRow(folder, depth=depth, is_expanded=is_expanded, parent=self.tree_container)
                row.set_selected(fid == self._selected_id)
                row.set_has_children(has_children)
                row.clicked.connect(self._on_row_clicked)
                row.new_subfolder.connect(self._on_new_subfolder)
                row.rename_requested.connect(self._on_rename)
                row.delete_requested.connect(self._on_delete)
                self._rows[fid] = row
                self.tree_layout.addWidget(row)

                if is_expanded:
                    _add_rows(fid, depth + 1)

        _add_rows(None, 0)

    def _on_row_clicked(self, folder_id: str):
        # Toggle expand
        if folder_id in self._expanded_ids:
            self._expanded_ids.discard(folder_id)
        else:
            self._expanded_ids.add(folder_id)

        self._selected_id = folder_id
        self.folder_selected.emit(folder_id)

    def select_folder(self, folder_id: str):
        """Programmatically select a folder (called from breadcrumb navigation)."""
        self._selected_id = folder_id
        for fid, row in self._rows.items():
            row.set_selected(fid == folder_id)

    def _on_new_subfolder(self, parent_id: str):
        from ...storage.notebook_storage import NotebookStorage
        name, ok = QInputDialog.getText(self, "New Sub-folder", "Sub-folder name:")
        if ok and name.strip():
            try:
                NotebookStorage.create_folder(name.strip(), parent_id=parent_id)
                self._expanded_ids.add(parent_id)
                self.tree_changed.emit()
            except ValueError as e:
                QMessageBox.warning(self, "Cannot Create Folder", str(e))

    def _on_rename(self, folder_id: str):
        from ...storage.notebook_storage import NotebookStorage
        row = self._rows.get(folder_id)
        current_name = row.folder_name if row else ""
        name, ok = QInputDialog.getText(self, "Rename Folder", "New name:", text=current_name)
        if ok and name.strip():
            NotebookStorage.rename_folder(folder_id, name.strip())
            self.tree_changed.emit()

    def _on_delete(self, folder_id: str):
        from ...storage.notebook_storage import NotebookStorage
        preview = NotebookStorage.get_cascade_preview(folder_id)
        folder_count = len(preview["folder_names"])
        nb_count = len(preview["notebook_names"])

        details = []
        if folder_count:
            details.append(f"• {folder_count} folder(s): {', '.join(preview['folder_names'][:5])}")
        if nb_count:
            details.append(f"• {nb_count} notebook(s): {', '.join(preview['notebook_names'][:5])}")

        msg = "This will permanently delete:\n" + "\n".join(details) if details else "This folder is empty."
        reply = QMessageBox.warning(
            self, "Delete Folder",
            f"Delete folder '{self._rows[folder_id].folder_name}'?\n\n{msg}\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            NotebookStorage.delete_folder_cascade(folder_id)
            self._expanded_ids.discard(folder_id)
            if self._selected_id == folder_id:
                self._selected_id = None
                self.folder_selected.emit("")
            self.tree_changed.emit()
