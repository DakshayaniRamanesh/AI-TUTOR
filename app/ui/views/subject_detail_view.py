import os
import sys
import shutil
import math
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QListWidget, QListWidgetItem, QSplitter, QFileDialog, QMessageBox,
    QTabWidget, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, 
    QGraphicsTextItem, QInputDialog, QFrame, QMenu, QAbstractItemView, QGraphicsRectItem, QDialog, QDialogButtonBox
)
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QIcon, QAction
from PyQt6.QtCore import pyqtSignal, Qt, QSize

# Import our DB operations
from app.storage.database_ops import (
    get_subject_details, add_material, delete_subject,
    delete_notebook_record, delete_material, delete_video
)
# Import the REAL notebook storage system that the canvas actually uses
from app.storage.notebook_storage import NotebookStorage


# ────────────────────────────────────────────────────────────────────────────
# Knowledge Graph Widget
# ────────────────────────────────────────────────────────────────────────────

class KnowledgeGraphWidget(QGraphicsView):
    """Draws a beautiful circular node map natively using PyQt graphics."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setStyleSheet("background-color: #1a1a2e; border: none; border-radius: 8px;")
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.active_node = None
        self.last_nodes, self.last_edges = [], []
        
        from PyQt6.QtWidgets import QPushButton
        self.btn_back = QPushButton("← Back to Main Graph", self)
        self.btn_back.setStyleSheet("""
            QPushButton {
                background-color: #3d5af1;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4361ee;
            }
        """)
        self.btn_back.move(20, 20)
        self.btn_back.hide()
        self.btn_back.clicked.connect(self.go_back_to_main)
        
    def go_back_to_main(self):
        self.active_node = None
        self.btn_back.hide()
        self.render_graph(self.last_nodes, self.last_edges)

    def render_graph(self, nodes, edges):
        self._scene.clear()
        self.last_nodes, self.last_edges = nodes, edges
        
        if not nodes:
            placeholder = self._scene.addText(
                "No concepts extracted yet.\n"
                "Upload a PDF and generate notes/video to populate the graph."
            )
            placeholder.setDefaultTextColor(QColor("#8888aa"))
            placeholder.setFont(QFont("Segoe UI", 12))
            return

        # --- Step 4 & 5: Calculate Centrality and Sizes ---
        # 1. Count how many connections (edges) each node has
        degrees = {node.name: 0 for node in nodes}
        for edge in edges:
            if edge.source_name in degrees:
                degrees[edge.source_name] += 1
            if edge.target_name in degrees:
                degrees[edge.target_name] += 1
                
        # 2. Sort nodes so the most connected one is first (the Hub)
        sorted_nodes = sorted(nodes, key=lambda n: degrees.get(n.name, 0), reverse=True)

        # --- PROGRESSIVE DISCLOSURE FILTERING ---
        if hasattr(self, 'active_node') and self.active_node:
            # DRILL-DOWN MODE
            visible_names = {self.active_node}
            for edge in edges:
                if edge.source_name == self.active_node:
                    visible_names.add(edge.target_name)
                elif edge.target_name == self.active_node:
                    visible_names.add(edge.source_name)
                    
            # Filter down
            sorted_nodes = [n for n in sorted_nodes if n.name in visible_names]
            # Force the active node to be at index 0 so it becomes the center Hub!
            sorted_nodes.sort(key=lambda n: 0 if n.name == self.active_node else 1)
        else:
            # MAIN VIEW MODE
            visible_names = {n.name for n in sorted_nodes[:8]}
            sorted_nodes = [n for n in sorted_nodes if n.name in visible_names]
        edges = [e for e in edges if e.source_name in visible_names and e.target_name in visible_names]
        nodes = [n for n in nodes if n.name in visible_names]

        node_positions = {}
        self.node_radii = {} # Store radii so we can use them when drawing
        
        # Center of our universe
        center_x, center_y = 400, 400 
        
        for i, node in enumerate(sorted_nodes):
            name = node.name
            deg = degrees.get(name, 0)
            
            # 3. Dynamic Sizing: Base size is 14, grows by 4 for every connection (Max 40)
            r = 14 + (deg * 4)
            self.node_radii[name] = min(r, 40)
            
            # 4. Hub-and-Spoke Layout
            if i == 0:
                # The absolute most important concept sits dead center
                node_positions[name] = (center_x, center_y)
            else:
                # Place nodes in two clean, alternating rings to prevent overlap
                distance = 220 if i % 2 == 1 else 320 
                angle = i * ((2 * math.pi) / (len(nodes) - 1 if len(nodes) > 1 else 1))
                x = center_x + distance * math.cos(angle)
                y = center_y + distance * math.sin(angle)
                node_positions[name] = (x, y)
                
            # Stash the description (summary) for Step 8!
            if not hasattr(self, 'node_summaries'):
                self.node_summaries = {}
            self.node_summaries[name] = node.description

        # Consolidate duplicate edges between the same nodes to prevent overlaps
        consolidated_edges = {}
        for edge in edges:
            if edge.source_name in node_positions and edge.target_name in node_positions:
                key = tuple(sorted([edge.source_name, edge.target_name]))
                if key not in consolidated_edges:
                    consolidated_edges[key] = {
                        "source": edge.source_name,
                        "target": edge.target_name,
                        "labels": []
                    }
                if edge.relationship_desc and edge.relationship_desc not in consolidated_edges[key]["labels"]:
                    consolidated_edges[key]["labels"].append(edge.relationship_desc)

        for edge_data in consolidated_edges.values():
            x1, y1 = node_positions[edge_data["source"]]
            x2, y2 = node_positions[edge_data["target"]]
            
            # 1. Draw the line (Z=0, very bottom)
            pen = QPen(QColor("#3d5af1"), 1.2, Qt.PenStyle.SolidLine)
            pen.setCosmetic(True)
            line = self._scene.addLine(x1, y1, x2, y2, pen)
            line.setZValue(0)
            
            # 2. Draw the relationship label
            if edge_data["labels"]:
                desc = " | ".join(edge_data["labels"])
                # Place label exactly in the middle
                mid_x = (x1 + x2) / 2
                mid_y = (y1 + y2) / 2
                
                # Create text item (Z=2)
                lbl = QGraphicsTextItem(desc)
                lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Medium))
                lbl.setDefaultTextColor(QColor("#a8b2d1"))
                lbl.setZValue(2)
                
                # Center the text exactly on the midpoint
                boundingRect = lbl.boundingRect()
                lbl_x = mid_x - (boundingRect.width() / 2)
                lbl_y = mid_y - (boundingRect.height() / 2)
                
                # Background rect for readability (Z=1, hides the line underneath)
                bg = QGraphicsRectItem(lbl_x, lbl_y, boundingRect.width(), boundingRect.height())
                bg.setBrush(QBrush(QColor("#1a1a2e")))
                bg.setPen(QPen(Qt.PenStyle.NoPen))
                bg.setZValue(1)
                self._scene.addItem(bg)
                
                lbl.setPos(lbl_x, lbl_y)
                self._scene.addItem(lbl)

        for name, (x, y) in node_positions.items():
            r = self.node_radii.get(name,14)
            ellipse = QGraphicsEllipseItem(x - r, y - r, r * 2, r * 2)
            ellipse.setBrush(QBrush(QColor("#4361ee")))
            ellipse.setPen(QPen(QColor("#7b8cff"), 2))
            ellipse.setData(0, name)
            ellipse.setZValue(3)  # Nodes above edges and labels
            self._scene.addItem(ellipse)

            text = QGraphicsTextItem(name)
            text.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
            text.setDefaultTextColor(QColor("#c8d6e5"))
            
            # Center the text horizontally, place below the circle
            text_rect = text.boundingRect()
            text.setPos(x - (text_rect.width() / 2), y + r + 4)
            
            text.setZValue(4)  # Node text on very top
            self._scene.addItem(text)

        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(-40, -40, 40, 40))

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if item and item.data(0):
            node_name = item.data(0)
            
            # --- STEP 8: Show Summary Popup ---
            if hasattr(self, 'node_summaries') and self.node_summaries.get(node_name):
                from PyQt6.QtWidgets import QToolTip
                from PyQt6.QtGui import QFont
                QToolTip.setFont(QFont("Segoe UI", 10))
                QToolTip.showText(event.globalPosition().toPoint(), f"{node_name}:\n{self.node_summaries[node_name]}")
                
            # --- DRILL-DOWN NAVIGATION ---
            if getattr(self, 'active_node', None) == node_name:
                self.go_back_to_main()
            else:
                self.active_node = node_name
                self.btn_back.setText(f"← Back (Viewing: {node_name})")
                self.btn_back.adjustSize()
                self.btn_back.show()
                self.render_graph(self.last_nodes, self.last_edges)
        else:
            super().mousePressEvent(event)

    def wheelEvent(self, event):
        """Zoom in and out using the mouse wheel."""
        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / zoom_in_factor
        if event.angleDelta().y() > 0:
            self.scale(zoom_in_factor, zoom_in_factor)
        else:
            self.scale(zoom_out_factor, zoom_out_factor)


# ────────────────────────────────────────────────────────────────────────────
# Deletable List Widget — a list with checkboxes + a "Delete Selected" bar
# ────────────────────────────────────────────────────────────────────────────

class DeletableListWidget(QWidget):
    """A QListWidget wrapper that adds checkboxes and a Delete Selected button."""
    item_double_clicked = pyqtSignal(QListWidgetItem)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list_widget.itemDoubleClicked.connect(self.item_double_clicked.emit)
        layout.addWidget(self.list_widget)

        # Delete bar — hidden until items are checked
        self.delete_bar = QHBoxLayout()
        self.delete_bar.setContentsMargins(0, 0, 0, 0)
        self.lbl_selected = QLabel("0 selected")
        self.lbl_selected.setStyleSheet("font-size: 12px; color: #666;")
        self.delete_bar.addWidget(self.lbl_selected)
        self.delete_bar.addStretch()
        self.btn_delete = QPushButton("🗑 Delete Selected")
        self.btn_delete.setStyleSheet(
            "background: #ff3b30; color: white; border: none; font-weight: 600; "
            "padding: 5px 12px; border-radius: 5px; font-size: 12px;"
        )
        self.btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_bar.addWidget(self.btn_delete)

        self.delete_bar_widget = QWidget()
        self.delete_bar_widget.setLayout(self.delete_bar)
        self.delete_bar_widget.setVisible(False)
        layout.addWidget(self.delete_bar_widget)

    def clear(self):
        self.list_widget.clear()
        self.delete_bar_widget.setVisible(False)

    def add_item(self, text: str, data=None):
        item = QListWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Unchecked)
        if data is not None:
            item.setData(Qt.ItemDataRole.UserRole, data)
        self.list_widget.addItem(item)

    def get_checked_items(self) -> list:
        """Returns list of (row, item) tuples for all checked items."""
        checked = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                checked.append((i, item))
        return checked

    def connect_check_state_updates(self):
        """Call after populating items to track checkbox changes."""
        self.list_widget.itemChanged.connect(self._on_item_changed)

    def disconnect_check_state_updates(self):
        """Disconnect to prevent signals during clear/repopulate."""
        try:
            self.list_widget.itemChanged.disconnect(self._on_item_changed)
        except TypeError:
            pass

    def _on_item_changed(self, item):
        count = len(self.get_checked_items())
        self.delete_bar_widget.setVisible(count > 0)
        self.lbl_selected.setText(f"{count} selected")


# ────────────────────────────────────────────────────────────────────────────
# Subject Detail View
# ────────────────────────────────────────────────────────────────────────────

class SubjectDetailView(QWidget):
    go_back = pyqtSignal()
    open_notebook = pyqtSignal(str)
    open_pdf_in_viewer = pyqtSignal(str)

    CARD_STYLE = """
        QFrame#card {{
            background: {bg};
            border: 1px solid {border};
            border-radius: 10px;
        }}
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_subject_id = None
        self._cached_materials = []
        self._cached_videos = []
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            QWidget { background-color: #f5f5f7; color: #1c1c1e; font-family: 'Segoe UI', sans-serif; }
            QListWidget {
                background: #ffffff; border: 1px solid #e0e0e5; border-radius: 6px;
                font-size: 13px; padding: 4px;
            }
            QListWidget::item { padding: 8px 6px; border-bottom: 1px solid #f0f0f2; }
            QListWidget::item:hover { background: #e8f0fe; }
            QPushButton { font-size: 13px; padding: 6px 14px; border-radius: 6px; }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(10)

        # ── Header ──
        header = QHBoxLayout()
        header.setSpacing(10)

        self.btn_back = QPushButton("← Back")
        self.btn_back.setStyleSheet(
            "border: none; color: #007aff; font-size: 15px; font-weight: 600; padding: 4px 8px;"
        )
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.clicked.connect(self.go_back.emit)
        header.addWidget(self.btn_back)

        self.lbl_title = QLabel("Subject")
        self.lbl_title.setStyleSheet("font-size: 22px; font-weight: 700; color: #1c1c1e;")
        header.addWidget(self.lbl_title)
        header.addStretch()

        self.btn_delete = QPushButton("🗑  Delete Subject")
        self.btn_delete.setStyleSheet(
            "color: #ff3b30; border: 1px solid #ff3b30; border-radius: 6px; "
            "font-weight: 600; padding: 5px 12px;"
        )
        self.btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_delete.clicked.connect(self._on_delete_subject)
        header.addWidget(self.btn_delete)
        main_layout.addLayout(header)

        # ── Tabs ──
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab {
                padding: 8px 20px; font-weight: 600; font-size: 13px;
                border: none; border-bottom: 2px solid transparent; color: #888;
                margin-right: 4px;
            }
            QTabBar::tab:selected { color: #007aff; border-bottom: 2px solid #007aff; }
            QTabBar::tab:hover { color: #333; }
        """)
        self.tabs.addTab(self._build_dashboard_tab(), "📋  Dashboard")
        self.graph_view = KnowledgeGraphWidget()
        self.tabs.addTab(self.graph_view, "🧠  Knowledge Graph")
        main_layout.addWidget(self.tabs)

    # ── Dashboard Tab ───────────────────────────────────────────────────────

    def _build_dashboard_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)

        # ── Left: Notebooks ──
        nb_card = QFrame()
        nb_card.setObjectName("card")
        nb_card.setStyleSheet(self.CARD_STYLE.format(bg="#ffffff", border="#e0e0e5"))
        nb_layout = QVBoxLayout(nb_card)
        nb_layout.setContentsMargins(14, 14, 14, 14)

        nb_header = QHBoxLayout()
        nb_lbl = QLabel("📓 Notebooks")
        nb_lbl.setStyleSheet("font-size: 16px; font-weight: 700;")
        nb_header.addWidget(nb_lbl)
        nb_header.addStretch()
        btn_new_nb = QPushButton("+ New")
        btn_new_nb.setStyleSheet(
            "background: #007aff; color: white; border: none; font-weight: 600; "
            "padding: 5px 12px; border-radius: 5px;"
        )
        btn_new_nb.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new_nb.clicked.connect(self._on_new_notebook)
        nb_header.addWidget(btn_new_nb)
        nb_layout.addLayout(nb_header)

        hint = QLabel("Double-click to open  •  Check boxes to select for deletion")
        hint.setStyleSheet("font-size: 11px; color: #999; margin-bottom: 2px;")
        nb_layout.addWidget(hint)

        self.nb_list = DeletableListWidget()
        self.nb_list.item_double_clicked.connect(self._on_notebook_clicked)
        self.nb_list.btn_delete.clicked.connect(self._on_delete_notebooks)
        nb_layout.addWidget(self.nb_list)
        layout.addWidget(nb_card, stretch=4)

        # ── Right: Materials + Videos ──
        right = QVBoxLayout()
        right.setSpacing(12)

        # Materials card
        mat_card = QFrame()
        mat_card.setObjectName("card")
        mat_card.setStyleSheet(self.CARD_STYLE.format(bg="#ffffff", border="#e0e0e5"))
        mat_layout = QVBoxLayout(mat_card)
        mat_layout.setContentsMargins(14, 14, 14, 14)

        mat_header = QHBoxLayout()
        mat_lbl = QLabel("📄 Reference PDFs")
        mat_lbl.setStyleSheet("font-size: 16px; font-weight: 700;")
        mat_header.addWidget(mat_lbl)
        mat_header.addStretch()
        btn_upload = QPushButton("+ Upload")
        btn_upload.setStyleSheet(
            "background: #34c759; color: white; border: none; font-weight: 600; "
            "padding: 5px 12px; border-radius: 5px;"
        )
        btn_upload.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_upload.clicked.connect(self._on_upload_material)
        mat_header.addWidget(btn_upload)
        mat_layout.addLayout(mat_header)

        hint2 = QLabel("Double-click to open in PDF viewer  •  Check boxes to select for deletion")
        hint2.setStyleSheet("font-size: 11px; color: #999; margin-bottom: 2px;")
        mat_layout.addWidget(hint2)

        self.mat_list = DeletableListWidget()
        self.mat_list.item_double_clicked.connect(self._on_material_clicked)
        self.mat_list.btn_delete.clicked.connect(self._on_delete_materials)
        mat_layout.addWidget(self.mat_list)
        right.addWidget(mat_card)

        # Videos card
        vid_card = QFrame()
        vid_card.setObjectName("card")
        vid_card.setStyleSheet(self.CARD_STYLE.format(bg="#ffffff", border="#e0e0e5"))
        vid_layout = QVBoxLayout(vid_card)
        vid_layout.setContentsMargins(14, 14, 14, 14)

        vid_lbl = QLabel("🎥 Generated Videos")
        vid_lbl.setStyleSheet("font-size: 16px; font-weight: 700;")
        vid_layout.addWidget(vid_lbl)

        hint3 = QLabel("Double-click to play  •  Check boxes to select for deletion")
        hint3.setStyleSheet("font-size: 11px; color: #999; margin-bottom: 2px;")
        vid_layout.addWidget(hint3)

        self.vid_list = DeletableListWidget()
        self.vid_list.item_double_clicked.connect(self._on_video_clicked)
        self.vid_list.btn_delete.clicked.connect(self._on_delete_videos)
        vid_layout.addWidget(self.vid_list)
        right.addWidget(vid_card)

        layout.addLayout(right, stretch=5)
        return tab

    # ── Data Loading ────────────────────────────────────────────────────────

    def load_subject(self, subject_id: str):
        self.current_subject_id = subject_id
        self.refresh_data()

    def refresh_data(self):
        if not self.current_subject_id:
            return

        subject = get_subject_details(self.current_subject_id)
        if not subject:
            return

        self.lbl_title.setText(f"📚 {subject.name}")

        # ── Notebooks ──
        self.nb_list.disconnect_check_state_updates()
        self.nb_list.clear()
        for nb in subject.notebooks:
            self.nb_list.add_item(f"📓  {nb.name}", data=nb.id)
        self.nb_list.connect_check_state_updates()

        # ── Materials ──
        self.mat_list.disconnect_check_state_updates()
        self.mat_list.clear()
        self._cached_materials = list(subject.materials)
        for i, mat in enumerate(self._cached_materials):
            self.mat_list.add_item(f"📄  {mat.filename}", data=i)
        self.mat_list.connect_check_state_updates()

        # ── Videos ──
        self.vid_list.disconnect_check_state_updates()
        self.vid_list.clear()
        self._cached_videos = list(subject.videos)
        for i, vid in enumerate(self._cached_videos):
            self.vid_list.add_item(f"🎥  {vid.title}", data=i)
        self.vid_list.connect_check_state_updates()

        # ── Knowledge Graph ──
        self.graph_view.render_graph(subject.concept_nodes, subject.concept_edges)

    # ── Notebook Actions ────────────────────────────────────────────────────

    def _on_new_notebook(self):
        if not self.current_subject_id:
            return

        name, ok = QInputDialog.getText(
            self, "New Notebook", "Notebook name:", text="Untitled Notebook"
        )
        if not ok or not name.strip():
            return

        meta = NotebookStorage.create_notebook(name.strip())
        nb_id = meta["id"]

        from app.storage.database_ops import create_notebook as db_create_notebook
        db_create_notebook(name.strip(), self.current_subject_id, override_id=nb_id)
        self.refresh_data()

    def _on_notebook_clicked(self, item: QListWidgetItem):
        nb_id = item.data(Qt.ItemDataRole.UserRole)
        if nb_id:
            self.open_notebook.emit(nb_id)

    def _on_delete_notebooks(self):
        checked = self.nb_list.get_checked_items()
        if not checked:
            return
        reply = QMessageBox.question(
            self, "Delete Notebooks",
            f"Delete {len(checked)} notebook(s)? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            for _, item in checked:
                nb_id = item.data(Qt.ItemDataRole.UserRole)
                if nb_id:
                    NotebookStorage.delete_notebook(nb_id)
                    delete_notebook_record(nb_id)
            self.refresh_data()

    # ── Material (PDF) Actions ──────────────────────────────────────────────
    def _on_upload_material(self):
        if not self.current_subject_id:
            return

        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Upload Reference PDFs", "", "PDF Files (*.pdf)"
        )
        if not file_paths:
            return

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        materials_dir = os.path.join(base_dir, "storage_data", "materials")
        os.makedirs(materials_dir, exist_ok=True)

        dest_paths = []
        for file_path in file_paths:
            filename = os.path.basename(file_path)
            dest_path = os.path.join(materials_dir, f"{self.current_subject_id}_{filename}")
            try:
                shutil.copy2(file_path, dest_path)
                add_material(self.current_subject_id, filename, dest_path)
                dest_paths.append(dest_path)
            except Exception as e:
                QMessageBox.critical(self, "Upload Failed", f"Failed to copy {filename}:\n{e}")
                
        if not dest_paths:
            return
            
        self.refresh_data()
        
        # --- KNOWLEDGE GRAPH EXTRACTION BACKGROUND WORKER ---
        print(f"[Graph] Starting background extraction for {len(dest_paths)} files...")
        self.lbl_title.setText(self.lbl_title.text() + " (Extracting Graph...)")
        
        def extract_and_save(pdf_paths, subj_id):
            try:
                from pypdf import PdfReader
                from app.backend.workspace.graph_extractor import GraphExtractor
                from app.storage.database_ops import update_subject_knowledge_graph
                
                # 1. Read all PDF Texts
                text = ""
                for pdf_path in pdf_paths:
                    reader = PdfReader(pdf_path)
                    for page in reader.pages:
                        text += (page.extract_text() or "") + "\n"
                    
                # 2. Extract concepts using AI
                extractor = GraphExtractor()
                nodes, edges = extractor.extract_graph_from_text(text)
                
                # 3. Save to DB
                if nodes:
                    print(f"[Graph] Found {len(nodes)} nodes! Saving to DB...")
                    update_subject_knowledge_graph(subj_id, nodes, edges)
                else:
                    print("[Graph] No nodes found.")
                    
            except Exception as e:
                print(f"[GraphExtraction] Error: {e}")
        
        import threading
        thread = threading.Thread(target=extract_and_save, args=(dest_paths, self.current_subject_id))
        thread.daemon = True
        thread.start()

    def _on_material_clicked(self, item: QListWidgetItem):
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is None or idx >= len(self._cached_materials):
            return

        mat = self._cached_materials[idx]
        path = mat.file_path

        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "File Missing", f"The file no longer exists:\n{path}")
            return

        # Emit signal — MainWindow will switch to canvas and load the PDF viewer
        print(f"[SubjectDetailView] Opening PDF: {path}")
        self.open_pdf_in_viewer.emit(path)

    def _on_delete_materials(self):
        checked = self.mat_list.get_checked_items()
        if not checked:
            return
        reply = QMessageBox.question(
            self, "Delete PDFs",
            f"Delete {len(checked)} PDF(s)? The files will also be removed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            for _, item in checked:
                idx = item.data(Qt.ItemDataRole.UserRole)
                if idx is not None and idx < len(self._cached_materials):
                    mat = self._cached_materials[idx]
                    path = delete_material(mat.id)
                    if path and os.path.exists(path):
                        try:
                            os.remove(path)
                        except Exception:
                            pass
            self.refresh_data()
            
            # --- KNOWLEDGE GRAPH REBUILDER ---
            print("[Graph] PDF deleted! Starting background rebuild...")
            self.lbl_title.setText(self.lbl_title.text() + " (Rebuilding Graph...)")
            
            def rebuild_graph(subj_id):
                try:
                    from pypdf import PdfReader
                    from app.backend.workspace.graph_extractor import GraphExtractor
                    from app.storage.database_ops import update_subject_knowledge_graph, get_subject_details
                    
                    # 1. Get the subject's remaining materials from DB
                    subject = get_subject_details(subj_id)
                    remaining_materials = subject.materials if subject else []
                    
                    if not remaining_materials:
                        print("[Graph] No materials left. Clearing graph.")
                        update_subject_knowledge_graph(subj_id, [], [], clear_existing=True)
                    else:
                        print(f"[Graph] Rebuilding graph from {len(remaining_materials)} remaining PDF(s)...")
                        combined_text = ""
                        for mat in remaining_materials:
                            if mat.file_path and os.path.exists(mat.file_path):
                                try:
                                    reader = PdfReader(mat.file_path)
                                    for page in reader.pages:
                                        combined_text += (page.extract_text() or "") + "\n"
                                except Exception:
                                    pass
                                    
                        extractor = GraphExtractor()
                        nodes, edges = extractor.extract_graph_from_text(combined_text)
                        
                        # Save to DB and force it to clear out the old nodes first
                        update_subject_knowledge_graph(subj_id, nodes, edges, clear_existing=True)
                    
                    # 2. Tell UI to refresh when done
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(0, self.refresh_data)
                    
                except Exception as e:
                    print(f"[GraphRebuild] Error: {e}")
            
            import threading
            thread = threading.Thread(target=rebuild_graph, args=(self.current_subject_id,))
            thread.daemon = True
            thread.start()

            self.refresh_data()

    # ── Video Actions ───────────────────────────────────────────────────────

    def _on_video_clicked(self, item: QListWidgetItem):
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is None or idx >= len(self._cached_videos):
            return

        vid = self._cached_videos[idx]
        self._open_file_external(vid.video_url)

    def _on_delete_videos(self):
        checked = self.vid_list.get_checked_items()
        if not checked:
            return
        reply = QMessageBox.question(
            self, "Delete Videos",
            f"Delete {len(checked)} video(s)? The files will also be removed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            for _, item in checked:
                idx = item.data(Qt.ItemDataRole.UserRole)
                if idx is not None and idx < len(self._cached_videos):
                    vid = self._cached_videos[idx]
                    path = delete_video(vid.id)
                    if path and os.path.exists(path):
                        try:
                            os.remove(path)
                        except Exception:
                            pass
            self.refresh_data()

    # ── Delete Subject ──────────────────────────────────────────────────────

    def _on_delete_subject(self):
        if not self.current_subject_id:
            return

        reply = QMessageBox.question(
            self, "Delete Subject",
            "Are you sure you want to delete this subject and ALL its "
            "notebooks, materials, and videos?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_subject(self.current_subject_id)
            self.current_subject_id = None
            self.go_back.emit()

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _open_file_external(self, path: str):
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "File Missing", f"File not found:\n{path}")
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            QMessageBox.warning(self, "Open Failed", f"Could not open file:\n{e}")
