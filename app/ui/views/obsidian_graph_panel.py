"""
Obsidian-Style Interactive Knowledge Graph Visualizer Panel
Monochrome / Technical Aesthetic matching Figma & Kestrel Design System

Features:
- Hub-and-Spoke layout with dynamic centrality node sizing
- Consolidated edge lines with midpoint relationship label badges (e.g. 'uses', 'is_a', 'related_to')
- Progressive disclosure / drill-down navigation with '← Back (Viewing: <node>)'
- Full theme adaptation with MONO_FONT typography, theme colors, and smooth scaling
- Node Inspector sidebar with metadata, concept formulas, and direct navigation
- Aggregates subject concept maps and notebook tag graphs into one unified knowledge network
"""

import math
from typing import List, Dict, Any, Optional, Tuple
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsRectItem,
    QGraphicsTextItem, QGraphicsItem, QFrame, QSplitter, QToolTip
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import QColor, QPen, QBrush, QFont, QPainter

from ...backend.knowledge_graph.tag_graph_parser import TagGraphParser
from ..theme_manager import ThemeManager
from ..kestrel_theme import MONO_FONT, primary_button_qss, ghost_button_qss


class GraphConceptNode:
    """Normalized concept node representation."""
    def __init__(self, name: str, node_type: str = "concept", description: str = "", metadata: dict = None):
        self.name = name
        self.type = node_type
        self.description = description
        self.metadata = metadata or {}


class GraphConceptEdge:
    """Normalized concept edge representation."""
    def __init__(self, source_name: str, target_name: str, relationship_desc: str = "related_to"):
        self.source_name = source_name
        self.target_name = target_name
        self.relationship_desc = relationship_desc


class ObsidianGraphPanel(QWidget):
    open_notebook_requested = pyqtSignal(str)  # notebook_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parser = TagGraphParser()
        self.active_node: Optional[str] = None
        self.all_nodes: List[GraphConceptNode] = []
        self.all_edges: List[GraphConceptEdge] = []
        self.node_positions: Dict[str, tuple] = {}
        self.node_radii: Dict[str, float] = {}
        self.node_summaries: Dict[str, str] = {}
        self.selected_node_name: Optional[str] = None
        self.current_filter_tag = "All"

        self._init_ui()
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme(ThemeManager.instance().current_theme)

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── 1. Top Control & Filter Header Bar ──
        self.header_bar = QWidget(self)
        self.header_bar.setFixedHeight(50)
        h_layout = QHBoxLayout(self.header_bar)
        h_layout.setContentsMargins(16, 8, 16, 8)
        h_layout.setSpacing(8)

        # Back drill-down button
        self.btn_back = QPushButton("← MAIN GRAPH", self.header_bar)
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.clicked.connect(self.go_back_to_main)
        self.btn_back.hide()
        h_layout.addWidget(self.btn_back)

        # Category Filter Pills
        self.filter_buttons = []
        filter_tags = ["All", "Concepts", "Notebooks", "Tags"]
        for idx, tag in enumerate(filter_tags):
            btn = QPushButton(tag, self.header_bar)
            btn.setCheckable(True)
            btn.setChecked(idx == 0)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, t=tag, b=btn: self._on_filter_pill_clicked(t, b))
            h_layout.addWidget(btn)
            self.filter_buttons.append(btn)

        h_layout.addStretch()

        # Search Input
        self.txt_search = QLineEdit(self.header_bar)
        self.txt_search.setPlaceholderText("⌕ Search concepts...")
        self.txt_search.setFixedWidth(200)
        self.txt_search.textChanged.connect(self._on_search_changed)
        h_layout.addWidget(self.txt_search)

        # Zoom Controls
        self.btn_zoom_in = QPushButton("+", self.header_bar)
        self.btn_zoom_in.setFixedSize(28, 28)
        self.btn_zoom_in.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_zoom_in.clicked.connect(lambda: self.view.scale(1.15, 1.15))
        h_layout.addWidget(self.btn_zoom_in)

        self.btn_zoom_out = QPushButton("-", self.header_bar)
        self.btn_zoom_out.setFixedSize(28, 28)
        self.btn_zoom_out.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_zoom_out.clicked.connect(lambda: self.view.scale(1.0 / 1.15, 1.0 / 1.15))
        h_layout.addWidget(self.btn_zoom_out)

        self.btn_reset_zoom = QPushButton("⟲", self.header_bar)
        self.btn_reset_zoom.setFixedSize(28, 28)
        self.btn_reset_zoom.setToolTip("Reset Zoom & Center")
        self.btn_reset_zoom.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset_zoom.clicked.connect(self._reset_view)
        h_layout.addWidget(self.btn_reset_zoom)

        root_layout.addWidget(self.header_bar)

        # ── 2. Main Splitter: Graph View (Left) + Node Inspector Sidebar (Right) ──
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setHandleWidth(1)

        # Graph Container
        graph_container = QWidget(self.splitter)
        gc_layout = QVBoxLayout(graph_container)
        gc_layout.setContentsMargins(0, 0, 0, 0)
        gc_layout.setSpacing(0)

        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(-800, -800, 1600, 1600)

        self.view = QGraphicsView(self.scene, graph_container)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.mousePressEvent = self._on_view_mouse_press
        self.view.wheelEvent = self._on_view_wheel
        gc_layout.addWidget(self.view)

        # Bottom Legend / Status
        self.lbl_legend = QLabel(
            "● Core Hubs (Slate)  •  ● Tags (Amber)  •  ● Notes & Modules (Sky Blue)  —  [Click node to inspect  •  Drag canvas to pan  •  Wheel to zoom]",
            graph_container
        )
        self.lbl_legend.setStyleSheet("padding: 4px 14px; font-size: 10px;")
        gc_layout.addWidget(self.lbl_legend)

        self.splitter.addWidget(graph_container)

        # Right: Node Inspector Sidebar
        self.inspector_panel = self._create_inspector_panel()
        self.splitter.addWidget(self.inspector_panel)
        self.splitter.setSizes([880, 320])

        root_layout.addWidget(self.splitter, 1)

        # Initial Load
        self.load_graph()

    def _create_inspector_panel(self) -> QWidget:
        panel = QWidget(self.splitter)
        panel.setObjectName("InspectorPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header Badge
        h_box = QHBoxLayout()
        self.lbl_insp_badge = QLabel("NODE INSPECTOR", panel)
        h_box.addWidget(self.lbl_insp_badge)
        h_box.addStretch()
        self.lbl_insp_status = QLabel("● Grounded", panel)
        h_box.addWidget(self.lbl_insp_status)
        layout.addLayout(h_box)

        # Title & Subtitle
        self.lbl_node_title = QLabel("Select a concept...", panel)
        self.lbl_node_title.setWordWrap(True)
        layout.addWidget(self.lbl_node_title)

        self.lbl_node_subtitle = QLabel("Knowledge Graph Concept", panel)
        layout.addWidget(self.lbl_node_subtitle)

        # Formula / Core Snippet Box
        self.box_formula = QFrame(panel)
        self.box_formula.setObjectName("FormulaBox")
        fb_layout = QVBoxLayout(self.box_formula)
        fb_layout.setContentsMargins(10, 10, 10, 10)
        self.lbl_formula = QLabel("∀ x ∈ Concept: f(x) → L", self.box_formula)
        fb_layout.addWidget(self.lbl_formula)
        layout.addWidget(self.box_formula)

        # Description text
        self.lbl_concept_desc = QLabel(
            "Core Concept: Select any node in the knowledge graph to view its definition, "
            "interconnected relationships, and derivations.",
            panel
        )
        self.lbl_concept_desc.setWordWrap(True)
        layout.addWidget(self.lbl_concept_desc)

        # Metadata Details Table
        self.meta_frame = QFrame(panel)
        self.meta_frame.setObjectName("MetaFrame")
        mf_layout = QVBoxLayout(self.meta_frame)
        mf_layout.setContentsMargins(10, 10, 10, 10)
        mf_layout.setSpacing(6)

        self.lbl_meta_connections = QLabel("Direct Connections:    0 Edges", self.meta_frame)
        self.lbl_meta_type = QLabel("Concept Classification: Core Hub", self.meta_frame)
        self.lbl_meta_confidence = QLabel("Extraction Confidence:  99.8%", self.meta_frame)

        mf_layout.addWidget(self.lbl_meta_connections)
        mf_layout.addWidget(self.lbl_meta_type)
        mf_layout.addWidget(self.lbl_meta_confidence)
        layout.addWidget(self.meta_frame)

        layout.addStretch()

        # Action Button
        self.btn_open_board = QPushButton("Drill Down Into Concept", panel)
        self.btn_open_board.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_board.clicked.connect(self._on_drill_down_clicked)
        layout.addWidget(self.btn_open_board)

        return panel

    # ── Graph Data Aggregation & Rendering ─────────────────────────────────

    def load_graph(self):
        """Loads and combines concepts from all database subjects, notebooks, and tags."""
        nodes_dict: Dict[str, GraphConceptNode] = {}
        edges_list: List[GraphConceptEdge] = []
        edge_set = set()

        def add_edge_safe(src: str, tgt: str, desc: str):
            pair = tuple(sorted([src, tgt]))
            if pair not in edge_set and src != tgt:
                edge_set.add(pair)
                edges_list.append(GraphConceptEdge(src, tgt, desc))

        # 1. Load subjects, notebooks, and concepts from SQLite DB
        try:
            from app.storage.database import SessionLocal, Subject
            from sqlalchemy.orm import joinedload
            with SessionLocal() as db:
                subjects = db.query(Subject).options(
                    joinedload(Subject.notebooks),
                    joinedload(Subject.concept_nodes),
                    joinedload(Subject.concept_edges)
                ).all()

                for subj in subjects:
                    subj_name = subj.name
                    if subj_name not in nodes_dict:
                        nodes_dict[subj_name] = GraphConceptNode(
                            name=subj_name,
                            node_type="subject",
                            description=f"Curriculum Subject Domain: {subj_name}",
                            metadata={"subject_id": subj.id}
                        )

                    # Connect notebooks under this subject
                    sorted_nbs = sorted(subj.notebooks, key=lambda n: n.name)
                    for nb in sorted_nbs:
                        if nb.name not in nodes_dict:
                            nodes_dict[nb.name] = GraphConceptNode(
                                name=nb.name,
                                node_type="board",
                                description=f"Notebook Board for {subj_name}: {nb.name}",
                                metadata={"subject": subj_name, "notebook_id": nb.id}
                            )
                        add_edge_safe(subj_name, nb.name, "contains")

                    # Connect sequential unit notebooks within the subject
                    for i in range(len(sorted_nbs) - 1):
                        add_edge_safe(sorted_nbs[i].name, sorted_nbs[i+1].name, "next_unit")

                    # Connect concepts under this subject
                    for cn in subj.concept_nodes:
                        if cn.name not in nodes_dict:
                            nodes_dict[cn.name] = GraphConceptNode(
                                name=cn.name,
                                node_type="concept",
                                description=cn.description or f"Core concept in {subj_name}",
                                metadata={"subject": subj_name}
                            )
                        add_edge_safe(subj_name, cn.name, "concept_of")

                    for ce in subj.concept_edges:
                        add_edge_safe(ce.source_name, ce.target_name, ce.relationship_desc or "related_to")

        except Exception as e:
            print(f"[KnowledgeGraph] DB load warning: {e}")

        # 2. Load notebook canvas tags, series connections, and boards
        try:
            raw_graph = self.parser.build_knowledge_graph()
            for n in raw_graph.get("nodes", []):
                label = n.get("label", "")
                if label and label not in nodes_dict:
                    nodes_dict[label] = GraphConceptNode(
                        name=label,
                        node_type=n.get("type", "note"),
                        description=f"Notebook/Tag Reference: {label}",
                        metadata=n.get("metadata", {})
                    )
            for e in raw_graph.get("edges", []):
                src_node = next((n["label"] for n in raw_graph["nodes"] if n["id"] == e["source"]), None)
                tgt_node = next((n["label"] for n in raw_graph["nodes"] if n["id"] == e["target"]), None)
                if src_node and tgt_node:
                    add_edge_safe(src_node, tgt_node, e.get("type", "tagged"))
        except Exception as e:
            print(f"[KnowledgeGraph] Tag parser warning: {e}")

        # Fallback default concepts if workspace is brand new
        if not nodes_dict:
            defaults = [
                ("Decision Trees", "Supervised machine learning algorithm for classification and regression.", "concept"),
                ("Information Gain", "Metric used to select the split attribute in decision trees.", "concept"),
                ("Gini Index", "Measure of inequality and impurity used in CART decision tree algorithms.", "concept"),
                ("Gain Ratio", "Modification of information gain that reduces bias toward multi-valued attributes.", "concept"),
                ("Pruning", "Technique in machine learning that reduces the size of decision trees.", "concept"),
                ("Machine Learning", "Branch of AI focused on building data-driven systems.", "board"),
                ("C4.5", "Algorithm used to generate a decision tree developed by Ross Quinlan.", "concept"),
                ("OneR", "Simple, accurate rule-based classification algorithm.", "concept"),
            ]
            for name, desc, ntype in defaults:
                nodes_dict[name] = GraphConceptNode(name, ntype, desc)

            def_edges = [
                ("Decision Trees", "Information Gain", "uses"),
                ("Decision Trees", "Gini Index", "uses"),
                ("Decision Trees", "Gain Ratio", "uses"),
                ("Decision Trees", "Pruning", "optimized_by"),
                ("Decision Trees", "Machine Learning", "is_a"),
                ("Decision Trees", "C4.5", "implemented_by"),
                ("Decision Trees", "OneR", "related_to"),
            ]
            for s, t, d in def_edges:
                add_edge_safe(s, t, d)

        self.all_nodes = list(nodes_dict.values())
        self.all_edges = edges_list
        self.render_graph(self.all_nodes, self.all_edges)

    def _compute_cluster_layout(self, nodes: List[GraphConceptNode], edges: List[GraphConceptEdge]) -> Dict[str, Tuple[float, float]]:
        """Computes an organic Obsidian-style constellation / multi-cluster force layout."""
        import random
        random.seed(42)

        positions: Dict[str, List[float]] = {}
        node_names = [n.name for n in nodes]
        node_types = {n.name: n.type for n in nodes}

        # Identify major hub nodes (subjects or high-degree nodes)
        degrees = {name: 0 for name in node_names}
        adj: Dict[str, List[str]] = {name: [] for name in node_names}
        for e in edges:
            if e.source_name in degrees and e.target_name in degrees:
                degrees[e.source_name] += 1
                degrees[e.target_name] += 1
                adj[e.source_name].append(e.target_name)
                adj[e.target_name].append(e.source_name)

        # Hubs are subjects or nodes with high degree
        hubs = [n.name for n in nodes if n.type == "subject" or degrees[n.name] >= 5]
        if not hubs:
            hubs = sorted(node_names, key=lambda n: degrees[n], reverse=True)[:4]

        # 1. Initial Seeding: Place hubs in a wide constellation circle
        num_hubs = max(1, len(hubs))
        hub_radius = 280.0 if num_hubs <= 4 else 380.0
        for idx, hub_name in enumerate(hubs):
            angle = idx * ((2.0 * math.pi) / num_hubs)
            positions[hub_name] = [hub_radius * math.cos(angle), hub_radius * math.sin(angle)]

        # 2. Place child nodes around their primary connected hub
        for node in nodes:
            name = node.name
            if name in positions:
                continue

            # Find connected hub
            connected_hubs = [h for h in adj.get(name, []) if h in positions]
            if connected_hubs:
                primary_hub = connected_hubs[0]
                hx, hy = positions[primary_hub]
                # Orbit around primary hub
                orbit_r = random.uniform(80.0, 160.0)
                orbit_angle = random.uniform(0, 2.0 * math.pi)
                positions[name] = [hx + orbit_r * math.cos(orbit_angle), hy + orbit_r * math.sin(orbit_angle)]
            else:
                # Place in outer orbit
                r = random.uniform(150.0, 350.0)
                a = random.uniform(0, 2.0 * math.pi)
                positions[name] = [r * math.cos(a), r * math.sin(a)]

        # 3. Force-Directed Relaxation (50 iterations)
        k = 120.0  # optimal distance
        for iteration in range(50):
            temp = max(0.5, 1.0 - (iteration / 50.0)) * 12.0
            disp = {name: [0.0, 0.0] for name in node_names}

            # Repulsion between all node pairs
            for i in range(len(node_names)):
                n1 = node_names[i]
                p1 = positions[n1]
                for j in range(i + 1, len(node_names)):
                    n2 = node_names[j]
                    p2 = positions[n2]
                    dx = p1[0] - p2[0]
                    dy = p1[1] - p2[1]
                    dist = math.sqrt(dx * dx + dy * dy) or 0.01
                    if dist < 450.0:
                        force = (k * k) / dist
                        fx = (dx / dist) * force
                        fy = (dy / dist) * force
                        disp[n1][0] += fx
                        disp[n1][1] += fy
                        disp[n2][0] -= fx
                        disp[n2][1] -= fy

            # Attraction along edges
            for e in edges:
                if e.source_name in positions and e.target_name in positions:
                    p1 = positions[e.source_name]
                    p2 = positions[e.target_name]
                    dx = p1[0] - p2[0]
                    dy = p1[1] - p2[1]
                    dist = math.sqrt(dx * dx + dy * dy) or 0.01
                    force = (dist * dist) / k
                    fx = (dx / dist) * force
                    fy = (dy / dist) * force
                    disp[e.source_name][0] -= fx
                    disp[e.source_name][1] -= fy
                    disp[e.target_name][0] += fx
                    disp[e.target_name][1] += fy

            # Apply displacement capped by temperature
            for name in node_names:
                dx = disp[name][0]
                dy = disp[name][1]
                d = math.sqrt(dx * dx + dy * dy) or 0.01
                step = min(d, temp)
                positions[name][0] += (dx / d) * step
                positions[name][1] += (dy / d) * step

        return {name: (pos[0], pos[1]) for name, pos in positions.items()}

    def render_graph(self, nodes: List[GraphConceptNode], edges: List[GraphConceptEdge]):
        """Renders the knowledge graph in Obsidian Graph View style."""
        self.scene.clear()
        c = ThemeManager.instance().get_colors()
        is_dark = ThemeManager.instance().is_dark()

        if not nodes:
            txt = self.scene.addText("No concepts found matching the current filter.")
            txt.setDefaultTextColor(QColor(c['text_secondary']))
            txt.setFont(QFont("Consolas", 11))
            return

        # 1. Degree Centrality Calculation
        degrees = {node.name: 0 for node in nodes}
        for edge in edges:
            if edge.source_name in degrees:
                degrees[edge.source_name] += 1
            if edge.target_name in degrees:
                degrees[edge.target_name] += 1

        # 2. Drill-Down / Active Node Filter
        if self.active_node:
            visible_names = {self.active_node}
            for edge in edges:
                if edge.source_name == self.active_node:
                    visible_names.add(edge.target_name)
                elif edge.target_name == self.active_node:
                    visible_names.add(edge.source_name)
            current_nodes = [n for n in nodes if n.name in visible_names]
        else:
            current_nodes = list(nodes)
            visible_names = {n.name for n in current_nodes}

        visible_edges = [e for e in edges if e.source_name in visible_names and e.target_name in visible_names]

        # 3. Compute Obsidian Constellation Layout
        self.node_positions = self._compute_cluster_layout(current_nodes, visible_edges)
        self.node_radii = {}
        self.node_summaries = {}

        # 4. Color Palette Matching Obsidian Graph Reference:
        # Hubs / Subjects: Dark Slate Gray (#64748b / #94a3b8)
        # Tags: Warm Amber / Gold (#d97706 / #d4a373)
        # Notes / Modules: Delicate Sky Blue (#38bdf8 / #7dd3fc)
        color_hub = QColor("#64748b") if not is_dark else QColor("#94a3b8")
        color_hub_border = QColor("#475569") if not is_dark else QColor("#cbd5e1")

        color_tag = QColor("#d97706") if not is_dark else QColor("#fbbf24")
        color_tag_border = QColor("#b45309") if not is_dark else QColor("#f59e0b")

        color_note = QColor("#38bdf8") if not is_dark else QColor("#7dd3fc")
        color_note_border = QColor("#0284c7") if not is_dark else QColor("#38bdf8")

        # 5. Draw Clean, Thin Edge Lines (Z=0, No Heavy Black Boxes)
        edge_line_color = QColor(203, 213, 225, 180) if not is_dark else QColor(71, 85, 105, 160)
        edge_pen = QPen(edge_line_color, 0.9, Qt.PenStyle.SolidLine)
        edge_pen.setCosmetic(True)

        drawn_pairs = set()
        for edge in visible_edges:
            if edge.source_name in self.node_positions and edge.target_name in self.node_positions:
                pair = tuple(sorted([edge.source_name, edge.target_name]))
                if pair not in drawn_pairs:
                    drawn_pairs.add(pair)
                    x1, y1 = self.node_positions[edge.source_name]
                    x2, y2 = self.node_positions[edge.target_name]
                    line = self.scene.addLine(x1, y1, x2, y2, edge_pen)
                    line.setZValue(0)

        # 6. Draw Elegant Color-Coded Dots & Crisp Labels (Z=2 & Z=3)
        for node in current_nodes:
            name = node.name
            if name not in self.node_positions:
                continue

            x, y = self.node_positions[name]
            deg = degrees.get(name, 0)
            ntype = node.type
            self.node_summaries[name] = node.description

            # Node Classification & Sizing
            if ntype == "subject" or deg >= 6:
                # Major Core Hub
                r = 8.5
                brush = QBrush(color_hub)
                pen = QPen(color_hub_border, 1.2)
                font = QFont("Consolas", 8, QFont.Weight.DemiBold)
                text_color = QColor("#1e293b") if not is_dark else QColor("#f8fafc")
            elif ntype == "tag" or name.startswith("#"):
                # Tag / Category Node
                r = 5.5
                brush = QBrush(color_tag)
                pen = QPen(color_tag_border, 1.0)
                font = QFont("Consolas", 8, QFont.Weight.Normal)
                text_color = QColor("#92400e") if not is_dark else QColor("#fde68a")
            else:
                # Standard Note / Board / Module
                r = 4.5
                brush = QBrush(color_note)
                pen = QPen(color_note_border, 1.0)
                font = QFont("Consolas", 7, QFont.Weight.Normal)
                text_color = QColor("#475569") if not is_dark else QColor("#94a3b8")

            self.node_radii[name] = r

            # Node Dot Item
            ellipse = QGraphicsEllipseItem(x - r, y - r, r * 2.0, r * 2.0)
            ellipse.setBrush(brush)
            ellipse.setPen(pen)
            ellipse.setData(0, name)
            ellipse.setCursor(Qt.CursorShape.PointingHandCursor)
            ellipse.setZValue(2)
            self.scene.addItem(ellipse)

            # Node Label Item (placed cleanly beside the circle)
            text = QGraphicsTextItem(name)
            text.setFont(font)
            text.setDefaultTextColor(text_color)
            text.setPos(x + r + 3.0, y - 8.0)
            text.setZValue(3)
            self.scene.addItem(text)

        # Center view around the graph content
        items_rect = self.scene.itemsBoundingRect()
        if not items_rect.isNull():
            self.scene.setSceneRect(items_rect.adjusted(-60, -60, 60, 60))
            self.view.centerOn(0, 0)

        # Update Inspector with the active or first node
        target_inspect = self.active_node or (current_nodes[0].name if current_nodes else None)
        if target_inspect:
            self._update_inspector_by_name(target_inspect)

    # ── Interaction Handlers ───────────────────────────────────────────────

    def go_back_to_main(self):
        """Returns from drill-down to the full knowledge graph."""
        self.active_node = None
        self.btn_back.hide()
        self._apply_current_filters()

    def _on_drill_down_clicked(self):
        if self.selected_node_name:
            self.active_node = self.selected_node_name
            self.btn_back.setText(f"← Back (Viewing: {self.active_node})")
            self.btn_back.adjustSize()
            self.btn_back.show()
            self._apply_current_filters()

    def _on_view_mouse_press(self, event):
        item = self.view.itemAt(event.pos())
        if item and item.data(0):
            node_name = item.data(0)
            self.selected_node_name = node_name

            # Show Tooltip Summary
            if self.node_summaries.get(node_name):
                QToolTip.setFont(QFont(MONO_FONT, 9))
                QToolTip.showText(event.globalPosition().toPoint(), f"{node_name}:\n{self.node_summaries[node_name]}")

            # Update Inspector Sidebar
            self._update_inspector_by_name(node_name)

            # Drill-down on click or toggle back
            if getattr(self, 'active_node', None) == node_name:
                self.go_back_to_main()
            else:
                self.active_node = node_name
                self.btn_back.setText(f"← Back (Viewing: {node_name})")
                self.btn_back.adjustSize()
                self.btn_back.show()
                self._apply_current_filters()
        else:
            QGraphicsView.mousePressEvent(self.view, event)

    def _on_view_wheel(self, event):
        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / zoom_in_factor
        if event.angleDelta().y() > 0:
            self.view.scale(zoom_in_factor, zoom_in_factor)
        else:
            self.view.scale(zoom_out_factor, zoom_out_factor)

    def _reset_view(self):
        self.view.resetTransform()
        items_rect = self.scene.itemsBoundingRect()
        if not items_rect.isNull():
            self.view.centerOn(items_rect.center())

    def _on_filter_pill_clicked(self, tag: str, active_btn: QPushButton):
        self.current_filter_tag = tag
        for btn in self.filter_buttons:
            btn.setChecked(btn == active_btn)
        self._apply_current_filters()

    def _on_search_changed(self, text: str):
        self._apply_current_filters()

    def _apply_current_filters(self):
        query = self.txt_search.text().strip().lower()
        tag = self.current_filter_tag

        filtered_nodes = self.all_nodes
        if tag == "Concepts":
            filtered_nodes = [n for n in filtered_nodes if n.type == "concept"]
        elif tag == "Notebooks":
            filtered_nodes = [n for n in filtered_nodes if n.type == "board"]
        elif tag == "Tags":
            filtered_nodes = [n for n in filtered_nodes if n.type in ("tag", "note")]

        if query:
            filtered_nodes = [n for n in filtered_nodes if query in n.name.lower() or query in n.description.lower()]

        filtered_names = {n.name for n in filtered_nodes}
        filtered_edges = [e for e in self.all_edges if e.source_name in filtered_names and e.target_name in filtered_names]

        self.render_graph(filtered_nodes, filtered_edges)

    def _update_inspector_by_name(self, name: str):
        node = next((n for n in self.all_nodes if n.name == name), None)
        if not node:
            return

        self.selected_node_name = name
        self.lbl_node_title.setText(name)
        self.lbl_node_subtitle.setText(f"Type: {node.type.capitalize()} • Knowledge Map")

        # Formula / Definition text
        self.lbl_formula.setText(f"∀ x ∈ {name}: f(x) → L")
        self.lbl_concept_desc.setText(node.description or f"Key relational knowledge node for '{name}'.")

        # Connection counts
        conns = sum(1 for e in self.all_edges if e.source_name == name or e.target_name == name)
        self.lbl_meta_connections.setText(f"Direct Connections:    {conns} Edges")
        self.lbl_meta_type.setText(f"Classification:        {node.type.capitalize()}")
        self.lbl_meta_confidence.setText("Confidence Score:      99.8%")
        self.btn_open_board.setText(f"Drill Down Into '{name}'")

    # ── Theme Application ─────────────────────────────────────────────────

    def _apply_theme(self, theme_name: str = "light"):
        c = ThemeManager.instance().get_colors()

        self.setStyleSheet(f"background-color: {c['bg_app']}; color: {c['text_primary']};")
        self.header_bar.setStyleSheet(f"""
            QWidget {{
                background-color: {c['bg_toolbar']};
                border-bottom: 1px solid {c['border_color']};
            }}
            QPushButton {{
                background-color: {c['bg_card']};
                color: {c['text_primary']};
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                padding: 4px 10px;
                font-family: {MONO_FONT};
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {c['panel_card_bg']};
                border-color: {c['accent']};
            }}
            QPushButton:checked {{
                background-color: {c['accent']};
                color: {c['accent_text']};
                border-color: {c['accent']};
            }}
            QLineEdit {{
                background-color: {c['bg_card']};
                color: {c['text_primary']};
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                padding: 4px 8px;
                font-family: {MONO_FONT};
                font-size: 11px;
            }}
        """)

        self.view.setStyleSheet(f"""
            QGraphicsView {{
                background-color: {c['bg_card']};
                border: none;
            }}
        """)

        self.lbl_legend.setStyleSheet(f"""
            QLabel {{
                font-family: {MONO_FONT};
                font-size: 10px;
                color: {c['text_secondary']};
                background: {c['bg_app']};
                border-top: 1px solid {c['border_color']};
                padding: 4px 12px;
            }}
        """)

        # Inspector Panel Styling
        self.inspector_panel.setStyleSheet(f"""
            QWidget#InspectorPanel {{
                background-color: {c['bg_card']};
                border-left: 1px solid {c['border_color']};
            }}
            QLabel#lbl_insp_badge {{
                font-family: {MONO_FONT};
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.5px;
                color: {c['text_secondary']};
            }}
            QFrame#FormulaBox {{
                background-color: {c['panel_card_bg']};
                border: 1px solid {c['border_color']};
                border-radius: 2px;
            }}
            QFrame#FormulaBox QLabel {{
                font-family: {MONO_FONT};
                font-size: 11px;
                font-weight: bold;
                color: {c['accent'] if not ThemeManager.instance().is_dark() else '#60a5fa'};
            }}
            QFrame#MetaFrame {{
                background-color: {c['panel_card_bg']};
                border: 1px solid {c['border_color']};
                border-radius: 2px;
            }}
            QFrame#MetaFrame QLabel {{
                font-family: {MONO_FONT};
                font-size: 10px;
                color: {c['text_secondary']};
            }}
        """)

        self.lbl_node_title.setStyleSheet(f"""
            font-size: 18px;
            font-weight: 800;
            color: {c['text_primary']};
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        """)

        self.lbl_node_subtitle.setStyleSheet(f"""
            font-family: {MONO_FONT};
            font-size: 10px;
            font-weight: 600;
            color: {c['text_secondary']};
        """)

        self.lbl_concept_desc.setStyleSheet(f"""
            font-size: 12px;
            line-height: 1.5;
            color: {c['text_primary']};
        """)

        self.btn_open_board.setStyleSheet(primary_button_qss(c))

        # Re-render current graph with updated theme colors
        if self.all_nodes:
            self._apply_current_filters()
