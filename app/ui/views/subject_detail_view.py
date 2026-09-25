import os
import sys
import shutil
import math
import subprocess
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QListWidget, QListWidgetItem, QSplitter, QFileDialog, QMessageBox,
    QTabWidget, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, 
    QGraphicsTextItem, QInputDialog, QFrame, QMenu, QAbstractItemView, QGraphicsRectItem, QDialog, QDialogButtonBox,
    QScrollArea, QGridLayout, QSizePolicy
)
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QIcon, QAction
from PyQt6.QtCore import pyqtSignal, Qt, QSize, QTimer

from app.storage.database_ops import (
    get_subject_details, add_material, delete_subject,
    delete_notebook_record, delete_material, delete_video
)
from app.storage.notebook_storage import NotebookStorage
from app.ui.theme_manager import ThemeManager
from app.ui.kestrel_theme import MONO_FONT, DISPLAY_FONT, primary_button_qss, ghost_button_qss

class KnowledgeGraphWidget(QGraphicsView):
    """Draws a beautiful circular node map natively using PyQt graphics."""
    def __init__(self, parent=None):
        super().__init__(parent)
        from app.ui.theme_manager import ThemeManager
        from app.ui.kestrel_theme import MONO_FONT
        c = ThemeManager.instance().get_colors()

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setStyleSheet(f"background-color: {c['bg_card']}; border: 1px solid {c['border_color']}; border-radius: 4px;")
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.active_node = None
        self.last_nodes, self.last_edges = [], []
        
        from PyQt6.QtWidgets import QPushButton
        self.btn_back = QPushButton("← MAIN GRAPH", self)
        self.btn_back.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['bg_card']};
                color: {c['text_primary']};
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                padding: 5px 12px;
                font-family: {MONO_FONT};
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {c['panel_card_bg']};
                border-color: {c['accent']};
            }}
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
        from app.ui.theme_manager import ThemeManager
        from app.ui.kestrel_theme import MONO_FONT
        c = ThemeManager.instance().get_colors()
        is_dark = ThemeManager.instance().is_dark()
        
        if not nodes:
            placeholder = self._scene.addText(
                "No concepts extracted yet.\n"
                "Upload a PDF and generate notes/video to populate the graph."
            )
            placeholder.setDefaultTextColor(QColor(c['text_secondary']))
            placeholder.setFont(QFont(MONO_FONT, 11))
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
            
            # 3. Dynamic Sizing: Base size is 16, grows by 4 for every connection (Max 42)
            r = 16 + (deg * 4)
            self.node_radii[name] = min(r, 42)
            
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

        # Obsidian Graph Color Palette
        color_hub = QColor("#64748b") if not is_dark else QColor("#94a3b8")
        color_hub_border = QColor("#475569") if not is_dark else QColor("#cbd5e1")

        color_tag = QColor("#d97706") if not is_dark else QColor("#fbbf24")
        color_tag_border = QColor("#b45309") if not is_dark else QColor("#f59e0b")

        color_note = QColor("#38bdf8") if not is_dark else QColor("#7dd3fc")
        color_note_border = QColor("#0284c7") if not is_dark else QColor("#38bdf8")

        # 1. Draw Clean Thin Edge Lines
        edge_line_color = QColor(203, 213, 225, 180) if not is_dark else QColor(71, 85, 105, 160)
        edge_pen = QPen(edge_line_color, 0.9, Qt.PenStyle.SolidLine)
        edge_pen.setCosmetic(True)

        drawn_edges = set()
        for edge in edges:
            if edge.source_name in node_positions and edge.target_name in node_positions:
                pair = tuple(sorted([edge.source_name, edge.target_name]))
                if pair not in drawn_edges:
                    drawn_edges.add(pair)
                    x1, y1 = node_positions[edge.source_name]
                    x2, y2 = node_positions[edge.target_name]
                    line = self._scene.addLine(x1, y1, x2, y2, edge_pen)
                    line.setZValue(0)

        # 2. Draw Obsidian Dots & Clean Labels
        for idx, (name, (x, y)) in enumerate(node_positions.items()):
            is_hub = (idx == 0)
            is_tag = name.startswith("#")

            if is_hub:
                r = 8.5
                brush = QBrush(color_hub)
                pen = QPen(color_hub_border, 1.2)
                font = QFont("Consolas", 8, QFont.Weight.DemiBold)
                text_color = QColor("#1e293b") if not is_dark else QColor("#f8fafc")
            elif is_tag:
                r = 5.5
                brush = QBrush(color_tag)
                pen = QPen(color_tag_border, 1.0)
                font = QFont("Consolas", 8, QFont.Weight.Normal)
                text_color = QColor("#92400e") if not is_dark else QColor("#fde68a")
            else:
                r = 4.5
                brush = QBrush(color_note)
                pen = QPen(color_note_border, 1.0)
                font = QFont("Consolas", 7, QFont.Weight.Normal)
                text_color = QColor("#475569") if not is_dark else QColor("#94a3b8")

            ellipse = QGraphicsEllipseItem(x - r, y - r, r * 2.0, r * 2.0)
            ellipse.setBrush(brush)
            ellipse.setPen(pen)
            ellipse.setData(0, name)
            ellipse.setCursor(Qt.CursorShape.PointingHandCursor)
            ellipse.setZValue(2)
            self._scene.addItem(ellipse)

            text = QGraphicsTextItem(name)
            text.setFont(font)
            text.setDefaultTextColor(text_color)
            text.setPos(x + r + 3.0, y - 8.0)
            text.setZValue(3)
            self._scene.addItem(text)

        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(-60, -60, 60, 60))

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
# Deletable List Widget — a list with checkboxes + a "Delete Selected" action
# ────────────────────────────────────────────────────────────────────────────



class IngestionStatusChip(QLabel):
    def __init__(self, status, parent=None):
        super().__init__(parent)
        self.set_status(status)
        self.setContentsMargins(6, 2, 6, 2)
        
    def set_status(self, status):
        c = ThemeManager.instance().get_colors()
        self.setStyleSheet(f"border-radius: 4px; font-family: {MONO_FONT}; font-size: 10px; font-weight: bold;")
        if status == "READY":
            self.setText("Ready")
            self.setStyleSheet(self.styleSheet() + f"background-color: #10b981; color: #ffffff;")
        elif status == "PARTIAL":
            self.setText("Search ready - semantic search unavailable")
            self.setStyleSheet(self.styleSheet() + f"background-color: #f59e0b; color: #ffffff;")
        elif status in ("REGISTERED", "EXTRACTING", "INDEXING"):
            self.setText("Processing")
            self.setStyleSheet(self.styleSheet() + f"background-color: #3b82f6; color: #ffffff;")
        elif status == "FAILED":
            self.setText("Failed")
            self.setStyleSheet(self.styleSheet() + f"background-color: #ef4444; color: #ffffff;")
        else:
            self.setText(str(status))
            self.setStyleSheet(self.styleSheet() + f"background-color: {c['border_color']}; color: {c['text_secondary']};")

class ResourceRow(QFrame):
    delete_requested = pyqtSignal(str)
    open_requested = pyqtSignal(str)
    retry_requested = pyqtSignal(str)
    
    def __init__(self, material, parent=None):
        super().__init__(parent)
        self.material = material
        self.material_id = material.id
        self.file_path = getattr(material, 'file_path', None)
        c = ThemeManager.instance().get_colors()
        
        self.setObjectName("ResourceRow")
        self.setStyleSheet(f"QFrame#ResourceRow {{ border-bottom: 1px solid {c['border_color']}; padding: 8px; }} QFrame#ResourceRow:hover {{ background-color: {c['panel_card_bg']}; }}")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(16)
        
        import qtawesome as qta
        
        # Icon
        icon_lbl = QLabel()
        if getattr(material, 'resource_type', None) == "IMAGE":
            icon_lbl.setPixmap(qta.icon("fa5s.image", color=c['text_secondary']).pixmap(QSize(18, 18)))
        elif getattr(material, "title", None) is not None:  # simple check for video
            icon_lbl.setPixmap(qta.icon("fa5s.video", color=c['text_secondary']).pixmap(QSize(18, 18)))
        elif not hasattr(material, "file_path"): # simple check for notebook
            icon_lbl.setPixmap(qta.icon("fa5s.book", color=c['text_secondary']).pixmap(QSize(18, 18)))
        else:
            icon_lbl.setPixmap(qta.icon("fa5s.file-pdf", color=c['text_secondary']).pixmap(QSize(18, 18)))
        layout.addWidget(icon_lbl)
        
        # Name
        name_lbl = QLabel(getattr(material, "filename", getattr(material, "title", getattr(material, "name", "Unknown"))))
        name_lbl.setStyleSheet(f"font-family: {DISPLAY_FONT}; font-size: 13px; color: {c['text_primary']}; font-weight: 500;")
        layout.addWidget(name_lbl, stretch=2)
        
        # Status
        status = getattr(material, "ingestion_status", "READY")
        if getattr(material, 'resource_type', None) == "IMAGE" and status == "PARTIAL":
            self.status_chip = IngestionStatusChip("STORED")
            self.status_chip.setText("Stored - analysis pending")
        elif status == "PARTIAL":
            self.status_chip = IngestionStatusChip(status)
            self.status_chip.setText("Search ready - semantic search unavailable")
        else:
            self.status_chip = IngestionStatusChip(status)
        layout.addWidget(self.status_chip)
        
        layout.addStretch(1)
        
        # Actions
        btn_retry = QPushButton("Retry")
        btn_retry.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_retry.setStyleSheet(ghost_button_qss(c, radius=4))
        btn_retry.clicked.connect(lambda: self.retry_requested.emit(self.material_id))
        self.btn_retry = btn_retry
        layout.addWidget(btn_retry)
        self._update_retry_visibility(status)
        
        # Open action
        btn_open = QPushButton("Open")
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.setStyleSheet(ghost_button_qss(c, radius=4))
        btn_open.clicked.connect(lambda: self.open_requested.emit(self.material_id))
        layout.addWidget(btn_open)
        
        # Delete action
        btn_del = QPushButton("Delete")
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setStyleSheet(f"QPushButton {{ color: #ef4444; border: none; font-size: 12px; }} QPushButton:hover {{ text-decoration: underline; }}")
        btn_del.clicked.connect(lambda: self.delete_requested.emit(self.material_id))
        layout.addWidget(btn_del)
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def _update_retry_visibility(self, status):
        self.btn_retry.setVisible(status == "FAILED")

    def update_status(self, status):
        if getattr(self, 'material_type', None) == "IMAGE" and status == "PARTIAL":
            self.status_chip.set_status("STORED")
            self.status_chip.setText("Stored - analysis pending")
        elif status == "PARTIAL":
            self.status_chip.set_status(status)
            self.status_chip.setText("Search ready - semantic search unavailable")
        else:
            self.status_chip.set_status(status)
        self._update_retry_visibility(status)

    def mouseDoubleClickEvent(self, event):
        self.open_requested.emit(self.material_id)

class NotebookCard(QFrame):
    open_requested = pyqtSignal(str)
    
    def __init__(self, notebook, parent=None):
        super().__init__(parent)
        self.notebook_id = notebook.id
        c = ThemeManager.instance().get_colors()
        
        self.setObjectName("NotebookCard")
        self.setStyleSheet(f"QFrame#NotebookCard {{ background-color: {c['bg_card']}; border: 1px solid {c['border_color']}; border-radius: 6px; padding: 12px; }} QFrame#NotebookCard:hover {{ border-color: {c['accent']}; background-color: {c['panel_card_bg']}; }}")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        
        name_lbl = QLabel(notebook.name)
        name_lbl.setStyleSheet(f"font-family: {DISPLAY_FONT}; font-size: 14px; color: {c['text_primary']}; font-weight: 600;")
        layout.addWidget(name_lbl)
        
        time_str = notebook.updated_at.strftime("%b %d, %Y %H:%M") if notebook.updated_at else "Unknown"
        date_lbl = QLabel(f"Updated {time_str}")
        date_lbl.setStyleSheet(f"font-family: {DISPLAY_FONT}; font-size: 11px; color: {c['text_secondary']};")
        layout.addWidget(date_lbl)
        
        layout.addStretch()
        
        btn_open = QPushButton("Continue")
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.setStyleSheet(ghost_button_qss(c, radius=4))
        btn_open.clicked.connect(lambda: self.open_requested.emit(self.notebook_id))
        
        action_layout = QHBoxLayout()
        action_layout.addWidget(btn_open)
        action_layout.addStretch()
        layout.addLayout(action_layout)

class SubjectDetailView(QWidget):
    go_back = pyqtSignal()
    open_notebook = pyqtSignal(str)
    open_pdf_in_viewer = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_subject_id = None
        self._cached_subject = None
        self._workers = []
        self._resource_rows = {}
        self._setup_ui()
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme(ThemeManager.instance().current_theme)

    def _setup_ui(self):
        c = ThemeManager.instance().get_colors()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(16)

        # ── Header ──
        header = QHBoxLayout()
        header.setSpacing(12)
        
        self.btn_back = QPushButton("← Back to subjects")
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.clicked.connect(self.go_back.emit)
        header.addWidget(self.btn_back)

        self.lbl_title = QLabel("Subject")
        header.addWidget(self.lbl_title)
        
        self.lbl_readiness = QLabel("")
        header.addWidget(self.lbl_readiness)
        
        header.addStretch()

        self.btn_options = QPushButton("Options ▼")
        self.btn_options.setCursor(Qt.CursorShape.PointingHandCursor)
        self.options_menu = QMenu(self)
        self.action_delete = QAction("Delete subject", self)
        self.action_delete.triggered.connect(self._on_delete_subject)
        self.options_menu.addAction(self.action_delete)
        self.btn_options.setMenu(self.options_menu)
        header.addWidget(self.btn_options)
        
        main_layout.addLayout(header)

        # ── Tabs ──
        self.tabs = QTabWidget()
        
        self.overview_tab = QScrollArea()
        self.overview_tab.setWidgetResizable(True)
        self.overview_content = QWidget()
        self.overview_layout = QVBoxLayout(self.overview_content)
        self.overview_tab.setWidget(self.overview_content)
        
        self.graph_view = KnowledgeGraphWidget()
        
        self.resources_tab = QWidget()
        self.resources_layout = QVBoxLayout(self.resources_tab)
        
        self.tabs.addTab(self.overview_tab, "Overview")
        self.tabs.addTab(self.graph_view, "Knowledge Map")
        self.tabs.addTab(self.resources_tab, "Resources")
        main_layout.addWidget(self.tabs)
        
        # Build Overview Layout
        self._build_overview_layout()
        # Build Resources Layout
        self._build_resources_layout()

    def _build_overview_layout(self):
        self.overview_layout.setContentsMargins(0, 16, 0, 16)
        self.overview_layout.setSpacing(24)
        
        # Continue Studying Card
        self.continue_card = QFrame()
        self.continue_card.setObjectName("ContinueCard")
        cc_layout = QVBoxLayout(self.continue_card)
        self.lbl_cc_title = QLabel("Start your first notebook")
        self.lbl_cc_body = QLabel("Your notes will stay connected to the resources in this subject.")
        self.btn_cc_action = QPushButton("Create notebook")
        self.btn_cc_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cc_action.clicked.connect(self._on_new_notebook)
        
        cc_layout.addWidget(self.lbl_cc_title)
        cc_layout.addWidget(self.lbl_cc_body)
        cc_layout.addWidget(self.btn_cc_action, 0, Qt.AlignmentFlag.AlignLeft)
        
        # Sub-grid for notebooks and readiness
        sub_grid = QGridLayout()
        sub_grid.setSpacing(16)
        
        self.nb_container = QWidget()
        nb_vbox = QVBoxLayout(self.nb_container)
        nb_vbox.setContentsMargins(0,0,0,0)
        self.lbl_recent_nb = QLabel("Your notebooks")
        nb_vbox.addWidget(self.lbl_recent_nb)
        self.nb_grid = QGridLayout()
        nb_vbox.addLayout(self.nb_grid)
        nb_vbox.addStretch()
        
        self.readiness_card = QFrame()
        self.readiness_card.setObjectName("ReadinessCard")
        rd_layout = QVBoxLayout(self.readiness_card)
        self.lbl_rd_title = QLabel("What Kestrel can use")
        self.lbl_rd_stats = QLabel("")
        rd_layout.addWidget(self.lbl_rd_title)
        rd_layout.addWidget(self.lbl_rd_stats)
        rd_layout.addStretch()
        
        sub_grid.addWidget(self.nb_container, 0, 0)
        sub_grid.addWidget(self.readiness_card, 0, 1)
        
        self.overview_layout.addWidget(self.continue_card)
        self.overview_layout.addLayout(sub_grid)
        self.overview_layout.addStretch()

    def _build_resources_layout(self):
        self.resources_layout.setContentsMargins(0, 16, 0, 16)
        self.resources_layout.setSpacing(16)
        
        top_bar = QHBoxLayout()
        self.btn_add_resource = QPushButton("Add course material")
        self.btn_add_resource.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_resource.clicked.connect(self._on_upload_material)
        top_bar.addWidget(self.btn_add_resource)
        
        from PyQt6.QtWidgets import QLineEdit, QComboBox
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search resources...")
        self.search_input.setFixedWidth(200)
        self.search_input.textChanged.connect(self._filter_resources)
        top_bar.addWidget(self.search_input)
        
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All Types", "PDFs", "Images", "Notebooks", "Videos"])
        self.type_filter.currentIndexChanged.connect(self._filter_resources)
        top_bar.addWidget(self.type_filter)
        
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All Status", "Processing", "Ready", "Needs attention"])
        self.status_filter.currentIndexChanged.connect(self._filter_resources)
        top_bar.addWidget(self.status_filter)
        
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Recently added", "Name", "Type"])
        self.sort_combo.currentIndexChanged.connect(self._sort_resources)
        top_bar.addWidget(self.sort_combo)
        
        top_bar.addStretch()
        
        self.resources_layout.addLayout(top_bar)
        
        self.res_scroll = QScrollArea()
        self.res_scroll.setWidgetResizable(True)
        self.res_content = QWidget()
        self.res_list_layout = QVBoxLayout(self.res_content)
        self.res_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.res_scroll.setWidget(self.res_content)
        
        self.resources_layout.addWidget(self.res_scroll)

    def _apply_theme(self, theme_name: str = "light"):
        c = ThemeManager.instance().get_colors()
        self.setStyleSheet(f"QWidget {{ background-color: {c['bg_app']}; color: {c['text_primary']}; }}")
        
        self.btn_back.setStyleSheet(ghost_button_qss(c, radius=4) + "QPushButton { border: none; }")
        self.btn_options.setStyleSheet(ghost_button_qss(c, radius=4))
        
        self.lbl_title.setStyleSheet(f"font-size: 24px; font-weight: 600; font-family: {DISPLAY_FONT}; color: {c['text_primary']};")
        self.lbl_readiness.setStyleSheet(f"font-size: 13px; font-family: {DISPLAY_FONT}; color: {c['text_secondary']};")
        
        self.tabs.setStyleSheet(f"QTabWidget::pane {{ border: none; border-top: 1px solid {c['border_color']}; }} QTabBar::tab {{ padding: 12px 24px; font-size: 14px; font-family: {DISPLAY_FONT}; background: transparent; border: none; border-bottom: 2px solid transparent; color: {c['text_secondary']}; }} QTabBar::tab:selected {{ color: {c['text_primary']}; border-bottom: 2px solid {c['accent']}; }} QTabBar::tab:hover:!selected {{ color: {c['text_primary']}; }}")
        
        self.continue_card.setStyleSheet(f"QFrame#ContinueCard {{ background-color: {c['bg_card']}; border: 1px solid {c['border_color']}; border-radius: 8px; padding: 24px; }}")
        self.lbl_cc_title.setStyleSheet(f"font-size: 20px; font-weight: 600; font-family: {DISPLAY_FONT}; color: {c['text_primary']};")
        self.lbl_cc_body.setStyleSheet(f"font-size: 14px; font-family: {DISPLAY_FONT}; color: {c['text_secondary']}; margin-bottom: 12px;")
        self.btn_cc_action.setStyleSheet(primary_button_qss(c, radius=6))
        
        self.readiness_card.setStyleSheet(f"QFrame#ReadinessCard {{ background-color: {c['bg_card']}; border: 1px solid {c['border_color']}; border-radius: 8px; padding: 20px; }}")
        self.lbl_rd_title.setStyleSheet(f"font-size: 16px; font-weight: 600; font-family: {DISPLAY_FONT}; color: {c['text_primary']}; margin-bottom: 8px;")
        self.lbl_rd_stats.setStyleSheet(f"font-size: 14px; font-family: {DISPLAY_FONT}; color: {c['text_secondary']}; line-height: 1.5;")
        
        self.lbl_recent_nb.setStyleSheet(f"font-size: 16px; font-weight: 600; font-family: {DISPLAY_FONT}; color: {c['text_primary']}; margin-bottom: 8px;")
        self.btn_add_resource.setStyleSheet(primary_button_qss(c, radius=6))
        
        self.overview_tab.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.res_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.overview_content.setStyleSheet("background: transparent;")
        self.res_content.setStyleSheet("background: transparent;")
        self.resources_tab.setStyleSheet("background: transparent;")

    def load_subject(self, subject_id: str):
        self.current_subject_id = subject_id
        self.refresh_data()

    def refresh_data(self):
        if not self.current_subject_id:
            return

        self._cached_subject = get_subject_details(self.current_subject_id)
        if not self._cached_subject:
            return

        subject = self._cached_subject
        self.lbl_title.setText(subject.name)
        
        # Calculate readiness
        ready = sum(1 for m in subject.materials if m.ingestion_status in ("READY", "PARTIAL"))
        proc = sum(1 for m in subject.materials if m.ingestion_status in ("REGISTERED", "EXTRACTING", "INDEXING"))
        readiness_text = []
        if ready > 0:
            readiness_text.append(f"{ready} resources ready")
        if proc > 0:
            readiness_text.append(f"{proc} resource indexing")
        
        # Check for image processing
        images = sum(1 for m in subject.materials if m.resource_type == "IMAGE" and m.ingestion_status == "PARTIAL")
        if images > 0:
            readiness_text.append(f"{images} images stored - analysis pending")
            
        self.lbl_readiness.setText(" • ".join(readiness_text) if readiness_text else "No resources yet")
        
        # Overview Tab
        notebooks = sorted(subject.notebooks, key=lambda x: x.updated_at or x.created_at, reverse=True)
        if notebooks:
            recent_nb = notebooks[0]
            self.lbl_cc_title.setText(recent_nb.name)
            self.lbl_cc_body.setText(f"Last updated {recent_nb.updated_at.strftime('%b %d, %Y') if recent_nb.updated_at else 'Unknown'}")
            self.btn_cc_action.setText("Continue notebook")
            try:
                self.btn_cc_action.clicked.disconnect()
            except Exception: pass
            self.btn_cc_action.clicked.connect(lambda _, nb_id=recent_nb.id: self.open_notebook.emit(nb_id))
        else:
            self.lbl_cc_title.setText("Start your first notebook")
            self.lbl_cc_body.setText("Your notes will stay connected to the resources in this subject.")
            self.btn_cc_action.setText("Create notebook")
            try:
                self.btn_cc_action.clicked.disconnect()
            except Exception: pass
            self.btn_cc_action.clicked.connect(self._on_new_notebook)
            
        # Recent Notebooks
        for i in reversed(range(self.nb_grid.count())):
            widget = self.nb_grid.itemAt(i).widget()
            if widget: widget.setParent(None)
            
        for i, nb in enumerate(notebooks[:4]):
            card = NotebookCard(nb)
            card.open_requested.connect(self.open_notebook.emit)
            self.nb_grid.addWidget(card, i // 2, i % 2)
            
        # Readiness panel
        searchable = sum(m.chunk_count for m in subject.materials if m.chunk_count)
        stats_text = f"""{ready} Resources ready
        {proc} Resources processing
        {searchable} Searchable chunks
        {len(notebooks)} Notebooks
        {len(subject.videos)} Generated videos"""
        self.lbl_rd_stats.setText(stats_text)

        # Knowledge Map
        if subject.concept_nodes:
            self.graph_view.render_graph(subject.concept_nodes, subject.concept_edges)
        else:
            self.graph_view.render_graph([], [])

        # Resources Tab
        for i in reversed(range(self.res_list_layout.count())):
            widget = self.res_list_layout.itemAt(i).widget()
            if widget: widget.setParent(None)
            
        self._resource_rows = {}
        all_resources = list(subject.materials) + list(subject.videos) + list(subject.notebooks)
        all_resources.sort(key=lambda x: getattr(x, "created_at", getattr(x, "updated_at", None)), reverse=True)
        
        for res in all_resources:
            row = ResourceRow(res)
            if hasattr(res, "video_url"):
                row.open_requested.connect(self._on_open_video)
                row.delete_requested.connect(self._on_delete_video)
            elif hasattr(res, "file_path"):
                row.open_requested.connect(self._on_open_material)
                row.delete_requested.connect(self._on_delete_material)
                row.retry_requested.connect(self._on_retry_material)
                self._resource_rows[res.id] = row
            else:
                row.open_requested.connect(self.open_notebook.emit)
                row.delete_requested.connect(self._on_delete_notebook)
            self.res_list_layout.addWidget(row)
            
        self._filter_resources()
            
    def _on_new_notebook(self):
        if not self.current_subject_id: return
        name, ok = QInputDialog.getText(self, "New Notebook", "Notebook name:", text="Untitled Notebook")
        if not ok or not name.strip(): return
        meta = NotebookStorage.create_notebook(name.strip())
        from app.storage.database_ops import create_notebook as db_create_notebook
        db_create_notebook(name.strip(), self.current_subject_id, override_id=meta["id"])
        self.refresh_data()

    def _on_upload_material(self):
        if not self.current_subject_id: return
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Upload Reference Material", "", "Images and PDFs (*.pdf *.png *.jpg *.jpeg)")
        if not file_paths: return

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        materials_dir = os.path.join(base_dir, "storage_data", "materials")
        os.makedirs(materials_dir, exist_ok=True)

        new_materials = []
        for file_path in file_paths:
            filename = os.path.basename(file_path)
            dest_path = os.path.join(materials_dir, f"{self.current_subject_id}_{filename}")
            
            existing = next((m for m in self._cached_subject.materials if m.file_path == dest_path), None)
            if existing:
                QMessageBox.information(self, "Duplicate Upload", f"{filename} is already uploaded to this subject.")
                continue

            try:
                shutil.copy2(file_path, dest_path)
                res_type = "PDF" if dest_path.lower().endswith(".pdf") else "IMAGE"
                mat = add_material(self.current_subject_id, filename, dest_path, resource_type=res_type)
                new_materials.append((mat.id, dest_path, res_type))
            except Exception as e:
                QMessageBox.critical(self, "Upload Failed", f"Failed to copy {filename}:\n{e}")
                
        if not new_materials:
            return
            
        self.refresh_data()
        
        from app.ui.workers.ingestion_worker import IngestionWorker
        for mat_id, dest_path, res_type in new_materials:
            worker = IngestionWorker(
                material_id=mat_id, subject_id=self.current_subject_id,
                file_path=dest_path, resource_type=res_type,
                parent=self
            )
            worker.status_changed.connect(self._on_worker_status)
            worker.finished.connect(self._on_worker_finished)
            worker.error.connect(self._on_worker_error)
            self._workers.append(worker)
            if mat_id in self._resource_rows:
                self._resource_rows[mat_id].update_status("REGISTERED")
            worker.start()

    def _cleanup_worker(self, mat_id):
        worker = next((w for w in self._workers if getattr(w, 'material_id', None) == mat_id), None)
        if worker:
            if hasattr(worker, 'cancel'):
                worker.cancel()
            try:
                worker.status_changed.disconnect(self._on_worker_status)
                worker.finished.disconnect(self._on_worker_finished)
                worker.error.disconnect(self._on_worker_error)
            except Exception: pass
            self._workers.remove(worker)
            worker.deleteLater()

    def _on_worker_status(self, mat_id, status):
        if mat_id in self._resource_rows:
            self._resource_rows[mat_id].update_status(status)

    def _on_worker_finished(self, mat_id, result):
        self._cleanup_worker(mat_id)
        self.refresh_data()
        
    def _on_worker_error(self, mat_id, error):
        self._cleanup_worker(mat_id)
        if mat_id in self._resource_rows:
            self._resource_rows[mat_id].update_status("FAILED")

    def _on_open_video(self, vid_id):
        vid = next((v for v in self._cached_subject.videos if v.id == vid_id), None)
        if vid and vid.video_url:
            self._open_file_external(vid.video_url)

    def _on_retry_material(self, mat_id):
        mat = next((m for m in self._cached_subject.materials if m.id == mat_id), None)
        if not mat: return
        from app.ui.workers.ingestion_worker import IngestionWorker
        worker = IngestionWorker(
            material_id=mat.id, subject_id=self.current_subject_id,
            file_path=mat.file_path, resource_type=mat.resource_type,
            parent=self
        )
        worker.status_changed.connect(self._on_worker_status)
        worker.finished.connect(self._on_worker_finished)
        worker.error.connect(self._on_worker_error)
        self._workers.append(worker)
        if mat_id in self._resource_rows:
            self._resource_rows[mat_id].update_status("REGISTERED")
        worker.start()

    def _on_open_material(self, mat_id):
        mat = next((m for m in self._cached_subject.materials if m.id == mat_id), None)
        if not mat: return
        path = mat.file_path
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "File Missing", f"The file no longer exists:\n{path}")
            return
        if mat.resource_type == "IMAGE":
            self._open_file_external(path)
        else:
            self.open_pdf_in_viewer.emit(path)

    def _on_delete_material(self, mat_id):
        reply = QMessageBox.question(self, "Delete Resource", "Are you sure you want to delete this resource?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._cleanup_worker(mat_id)
            try:
                path = delete_material(mat_id)
                if path and os.path.exists(path):
                    try: os.remove(path)
                    except Exception: pass
            except Exception as e:
                QMessageBox.warning(self, "Delete Failed", f"Failed to delete resource:\n{e}")
            self.refresh_data()

    def _on_delete_video(self, vid_id):
        reply = QMessageBox.question(self, "Delete Video", "Are you sure you want to delete this video?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            path = delete_video(vid_id)
            if path and os.path.exists(path):
                try: os.remove(path)
                except Exception: pass
            self.refresh_data()

    def _on_delete_notebook(self, nb_id):
        reply = QMessageBox.question(
            self, "Delete Notebook", 
            "Are you sure you want to delete this notebook?\nThis cannot be undone.", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                NotebookStorage.delete_notebook(nb_id)
                delete_notebook_record(nb_id)
            except Exception as e:
                QMessageBox.warning(self, "Delete Failed", f"Failed to delete notebook:\n{e}")
            self.refresh_data()
            
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

    def _on_delete_subject(self):
        if not self.current_subject_id: return
        reply = QMessageBox.question(self, "Delete Subject", "Delete this subject and ALL its data?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            delete_subject(self.current_subject_id)
            self.current_subject_id = None
            self.go_back.emit()

    def _sort_resources(self):
        self._filter_resources()

    def _filter_resources(self):
        query = self.search_input.text().strip().lower()
        type_flt = self.type_filter.currentText()
        status_flt = self.status_filter.currentText()
        sort_idx = self.sort_combo.currentIndex()
        
        rows = []
        for i in range(self.res_list_layout.count()):
            w = self.res_list_layout.itemAt(i).widget()
            if isinstance(w, ResourceRow):
                rows.append(w)
                
        if sort_idx == 0:
            rows.sort(key=lambda w: (getattr(w.material, "created_at", None) or getattr(w.material, "updated_at", None) or datetime.min), reverse=True)
        elif sort_idx == 1:
            rows.sort(key=lambda w: getattr(w.material, "filename", getattr(w.material, "title", getattr(w.material, "name", ""))).lower())
        elif sort_idx == 2:
            rows.sort(key=lambda w: "Video" if hasattr(w.material, "video_url") else ("Notebook" if not hasattr(w.material, "file_path") else getattr(w.material, "resource_type", "PDF")))
            
        for w in rows:
            self.res_list_layout.removeWidget(w)
            
        for w in rows:
            self.res_list_layout.addWidget(w)
            mat = w.material
            name = getattr(mat, "filename", getattr(mat, "title", getattr(mat, "name", ""))).lower()
            if query and query not in name:
                w.setVisible(False)
                continue
                
            is_video = hasattr(mat, "video_url")
            is_nb = not hasattr(mat, "file_path") and not is_video
            res_type = "Videos" if is_video else ("Notebooks" if is_nb else ("Images" if getattr(mat, "resource_type", None) == "IMAGE" else "PDFs"))
            if type_flt != "All Types" and res_type != type_flt:
                w.setVisible(False)
                continue
                
            if status_flt != "All Status":
                status = getattr(mat, "ingestion_status", "READY")
                is_proc = status in ("REGISTERED", "EXTRACTING", "INDEXING")
                if status_flt == "Processing" and not is_proc:
                    w.setVisible(False)
                    continue
                if status_flt == "Ready" and status not in ("READY", "PARTIAL"):
                    w.setVisible(False)
                    continue
                if status_flt == "Needs attention" and status != "FAILED":
                    w.setVisible(False)
                    continue
            
            w.setVisible(True)
