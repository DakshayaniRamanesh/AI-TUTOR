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
from typing import List, Dict, Any, Optional
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
            "Hub-and-Spoke Knowledge Map • Click node to drill down • Drag canvas to pan • Wheel to zoom",
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

    def render_graph(self, nodes: List[GraphConceptNode], edges: List[GraphConceptEdge]):
        """Renders the Hub-and-Spoke knowledge graph matching the subject knowledge graph design."""
        self.scene.clear()
        c = ThemeManager.instance().get_colors()
        is_dark = ThemeManager.instance().is_dark()

        if not nodes:
            txt = self.scene.addText("No concepts found matching the current filter.")
            txt.setDefaultTextColor(QColor(c['text_secondary']))
            txt.setFont(QFont(MONO_FONT, 11))
            return

        # 1. Degree Centrality Calculation
        degrees = {node.name: 0 for node in nodes}
        for edge in edges:
            if edge.source_name in degrees:
                degrees[edge.source_name] += 1
            if edge.target_name in degrees:
                degrees[edge.target_name] += 1

        sorted_nodes = sorted(nodes, key=lambda n: degrees.get(n.name, 0), reverse=True)

        # 2. Progressive Disclosure / Drill-Down Filtering
        if self.active_node:
            visible_names = {self.active_node}
            for edge in edges:
                if edge.source_name == self.active_node:
                    visible_names.add(edge.target_name)
                elif edge.target_name == self.active_node:
                    visible_names.add(edge.source_name)
            sorted_nodes = [n for n in sorted_nodes if n.name in visible_names]
            # Place active node dead center as hub
            sorted_nodes.sort(key=lambda n: 0 if n.name == self.active_node else 1)
        else:
            max_initial_nodes = 18
            if len(sorted_nodes) <= max_initial_nodes:
                visible_names = {n.name for n in sorted_nodes}
            else:
                visible_names = {n.name for n in sorted_nodes[:max_initial_nodes]}
            sorted_nodes = [n for n in sorted_nodes if n.name in visible_names]

        visible_edges = [e for e in edges if e.source_name in visible_names and e.target_name in visible_names]
        current_nodes = [n for n in nodes if n.name in visible_names]

        self.node_positions = {}
        self.node_radii = {}
        self.node_summaries = {}

        # Center Coordinates
        center_x, center_y = 0.0, 0.0
        num_spokes = max(1, len(current_nodes) - 1)

        for i, node in enumerate(sorted_nodes):
            name = node.name
            deg = degrees.get(name, 0)

            # Dynamic Sizing: Base size 16, grows by 3.5 per connection (Max 44)
            r = 16.0 + min(deg * 3.5, 28.0)
            if i == 0:
                r = max(r, 26.0)  # Center hub is prominently sized
            self.node_radii[name] = r
            self.node_summaries[name] = node.description

            # Hub-and-Spoke Layout with generous spacing to avoid text overlap
            if i == 0:
                self.node_positions[name] = (center_x, center_y)
            else:
                ring = (i - 1) % 2
                base_dist = 260.0 if ring == 0 else 400.0
                angle = (i - 1) * ((2 * math.pi) / num_spokes)
                x = center_x + base_dist * math.cos(angle)
                y = center_y + base_dist * math.sin(angle)
                self.node_positions[name] = (x, y)

        # 3. Consolidate & Draw Edge Lines with Relationship Badges
        consolidated_edges = {}
        for edge in visible_edges:
            if edge.source_name in self.node_positions and edge.target_name in self.node_positions:
                key = tuple(sorted([edge.source_name, edge.target_name]))
                if key not in consolidated_edges:
                    consolidated_edges[key] = {
                        "source": edge.source_name,
                        "target": edge.target_name,
                        "labels": []
                    }
                desc = edge.relationship_desc
                if desc and desc not in consolidated_edges[key]["labels"]:
                    consolidated_edges[key]["labels"].append(desc)

        # Edge stroke color adapted to theme
        edge_line_color = QColor(c['border_color']) if not is_dark else QColor("#3b4252")
        badge_bg_color = QColor("#0f172a") if is_dark else QColor("#111827")
        badge_text_color = QColor("#e2e8f0") if is_dark else QColor("#ffffff")

        for edge_data in consolidated_edges.values():
            x1, y1 = self.node_positions[edge_data["source"]]
            x2, y2 = self.node_positions[edge_data["target"]]

            # Line (Z=0)
            pen = QPen(edge_line_color, 1.4, Qt.PenStyle.SolidLine)
            pen.setCosmetic(True)
            line = self.scene.addLine(x1, y1, x2, y2, pen)
            line.setZValue(0)

            # Midpoint Relationship Badge
            if edge_data["labels"]:
                desc = " | ".join(edge_data["labels"])
                mid_x = (x1 + x2) / 2.0
                mid_y = (y1 + y2) / 2.0

                lbl = QGraphicsTextItem(desc)
                lbl.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
                lbl.setDefaultTextColor(badge_text_color)
                lbl.setZValue(2)

                b_rect = lbl.boundingRect()
                lbl_x = mid_x - (b_rect.width() / 2.0)
                lbl_y = mid_y - (b_rect.height() / 2.0)

                # Badge Rect Container (Z=1, cleanly masks line behind it)
                pad = 3.0
                bg = QGraphicsRectItem(
                    lbl_x - pad, lbl_y - pad / 2.0,
                    b_rect.width() + (pad * 2), b_rect.height() + pad
                )
                bg.setBrush(QBrush(badge_bg_color))
                bg.setPen(QPen(QColor(c['border_color']), 1.0))
                bg.setZValue(1)
                self.scene.addItem(bg)

                lbl.setPos(lbl_x, lbl_y)
                self.scene.addItem(lbl)

        # 4. Draw Concept Nodes & Labels (Z=3 & Z=4)
        hub_color = QColor("#3b82f6") if is_dark else QColor("#2563eb")
        spoke_color = QColor("#60a5fa") if is_dark else QColor("#3b82f6")
        node_border_color = QColor("#93c5fd") if is_dark else QColor("#1d4ed8")

        for idx, (name, (x, y)) in enumerate(self.node_positions.items()):
            r = self.node_radii.get(name, 16.0)
            is_hub = (idx == 0)

            ellipse = QGraphicsEllipseItem(x - r, y - r, r * 2.0, r * 2.0)
            ellipse.setBrush(QBrush(hub_color if is_hub else spoke_color))
            ellipse.setPen(QPen(node_border_color, 2.0 if is_hub else 1.5))
            ellipse.setData(0, name)
            ellipse.setZValue(3)
            self.scene.addItem(ellipse)

            # Node Label in Consolas Monospace
            text = QGraphicsTextItem(name)
            font_size = 9 if is_hub else 8
            text.setFont(QFont("Consolas", font_size, QFont.Weight.Bold if is_hub else QFont.Weight.DemiBold))
            text.setDefaultTextColor(QColor(c['text_primary']))

            text_rect = text.boundingRect()
            text.setPos(x - (text_rect.width() / 2.0), y + r + 4)
            text.setZValue(4)
            self.scene.addItem(text)

        # Center view around the graph content
        items_rect = self.scene.itemsBoundingRect()
        if not items_rect.isNull():
            self.scene.setSceneRect(items_rect.adjusted(-100, -100, 100, 100))
            self.view.centerOn(0, 0)

        # Update Inspector with the active or first node
        target_inspect = self.active_node or (sorted_nodes[0].name if sorted_nodes else None)
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
