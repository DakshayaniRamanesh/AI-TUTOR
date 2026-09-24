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

from shared.contracts.graph_contracts import GraphNodeDTO, GraphEdgeDTO, GraphSnapshot
from app.ui.theme_manager import ThemeManager
from app.ui.kestrel_theme import DISPLAY_FONT, MONO_FONT, primary_button_qss, ghost_button_qss
from app.services.knowledge.graph_layout_service import save_node_layout

class DraggableNode(QGraphicsEllipseItem):
    def __init__(self, node_id, scope_type, scope_id, x, y, r, canvas, *args, **kwargs):
        super().__init__(x - r, y - r, r * 2.0, r * 2.0, *args, **kwargs)
        self.node_id = node_id
        self.scope_type = scope_type
        self.scope_id = scope_id
        self.canvas = canvas
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setZValue(2)
        self._start_pos = None
        
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._start_pos = self.scenePos()
        
    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self._start_pos:
            end_pos = self.scenePos()
            if end_pos != self._start_pos:
                center = self.mapToScene(self.boundingRect().center())
                self.canvas.node_layout_changed.emit(self.node_id, self.scope_type, self.scope_id, center.x(), center.y())
        self._start_pos = None




class GraphCanvas(QWidget):
    open_notebook_requested = pyqtSignal(str)  # notebook_id
    open_source_requested = pyqtSignal(object) # GraphEvidenceDTO
    node_layout_changed = pyqtSignal(str, str, str, float, float) # node_id, scope_type, scope_id, x, y

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.active_node: Optional[str] = None
        self.all_nodes: List[GraphNodeDTO] = []
        self.all_edges: List[GraphEdgeDTO] = []
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

        # Set empty snapshot initially
        self.set_snapshot(GraphSnapshot(scope="GLOBAL", scope_id=None, revision=0))

    def _create_inspector_panel(self) -> QWidget:
        panel = QWidget(self.splitter)
        panel.setObjectName("InspectorPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Badge
        h_box = QHBoxLayout()
        self.lbl_insp_badge = QLabel("NODE INSPECTOR", panel)
        self.lbl_insp_badge.setObjectName("lbl_insp_badge")
        h_box.addWidget(self.lbl_insp_badge)
        h_box.addStretch()
        self.lbl_insp_status = QLabel("● Grounded", panel)
        self.lbl_insp_status.setObjectName("lbl_insp_status")
        h_box.addWidget(self.lbl_insp_status)
        layout.addLayout(h_box)

        # Title & Subtitle
        self.lbl_node_title = QLabel("Select a concept...", panel)
        self.lbl_node_title.setObjectName("lbl_node_title")
        self.lbl_node_title.setWordWrap(True)
        layout.addWidget(self.lbl_node_title)

        self.lbl_node_subtitle = QLabel("Knowledge Graph Node", panel)
        self.lbl_node_subtitle.setObjectName("lbl_node_subtitle")
        layout.addWidget(self.lbl_node_subtitle)



        # Description text
        self.lbl_concept_desc = QLabel(
            "Core Concept: Select any node in the knowledge graph to view its definition, "
            "interconnected relationships, and derivations.",
            panel
        )
        self.lbl_concept_desc.setObjectName("lbl_concept_desc")
        self.lbl_concept_desc.setWordWrap(True)
        layout.addWidget(self.lbl_concept_desc)

        # Clean Key-Value Details (Borderless, Modern Stat Rows)
        self.meta_frame = QFrame(panel)
        self.meta_frame.setObjectName("MetaFrame")
        mf_layout = QVBoxLayout(self.meta_frame)
        mf_layout.setContentsMargins(0, 8, 0, 8)
        mf_layout.setSpacing(8)

        def make_stat_row(label_text: str):
            row = QHBoxLayout()
            lbl_key = QLabel(label_text, self.meta_frame)
            lbl_key.setObjectName("StatKey")
            lbl_val = QLabel("—", self.meta_frame)
            lbl_val.setObjectName("StatVal")
            lbl_val.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(lbl_key)
            row.addStretch()
            row.addWidget(lbl_val)
            mf_layout.addLayout(row)
            return lbl_val

        self.lbl_val_connections = make_stat_row("Direct Connections")
        self.lbl_val_type = make_stat_row("Classification")
        self.lbl_val_evidence = make_stat_row("Evidence Source")

        layout.addWidget(self.meta_frame)

        layout.addStretch()
        
        self.btn_open_source = QPushButton("Open Evidence Source", panel)
        self.btn_open_source.setObjectName("btn_open_source")
        self.btn_open_source.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_source.clicked.connect(self._on_open_source_clicked)
        self.btn_open_source.hide()
        layout.addWidget(self.btn_open_source)

        # Action Button
        self.btn_open_board = QPushButton("Drill Down Into Concept", panel)
        self.btn_open_board.setObjectName("btn_open_board")
        self.btn_open_board.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_board.clicked.connect(self._on_drill_down_clicked)
        layout.addWidget(self.btn_open_board)

        return panel

    # ── Graph Data Aggregation & Rendering ─────────────────────────────────

    def set_snapshot(self, snapshot: GraphSnapshot):
        """Replaces the current graph with a new snapshot and re-renders."""
        self.all_nodes = list(snapshot.nodes)
        self.all_edges = list(snapshot.edges)
        
        # Merge layout states if any
        if snapshot.layout:
            for node_id, l_state in snapshot.layout.items():
                self.node_positions[node_id] = (l_state.x, l_state.y)
                
        self.render_graph(self.all_nodes, self.all_edges)

    def _compute_cluster_layout(self, nodes: List[GraphNodeDTO], edges: List[GraphEdgeDTO]) -> Dict[str, Tuple[float, float]]:
        """Computes an organic Obsidian-style constellation / multi-cluster force layout."""
        import random
        random.seed(42)

        positions: Dict[str, List[float]] = {}
        node_names = [n.id for n in nodes]
        node_types = {n.id: n.node_type for n in nodes}

        # Identify major hub nodes (subjects or high-degree nodes)
        degrees = {name: 0 for name in node_names}
        adj: Dict[str, List[str]] = {name: [] for name in node_names}
        for e in edges:
            if e.source_node_id in degrees and e.target_node_id in degrees:
                degrees[e.source_node_id] += 1
                degrees[e.target_node_id] += 1
                adj[e.source_node_id].append(e.target_node_id)
                adj[e.target_node_id].append(e.source_node_id)

        # Hubs are subjects or nodes with high degree
        hubs = [n.id for n in nodes if n.node_type == "subject" or degrees[n.id] >= 5]
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
            name = node.id
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
                if e.source_node_id in positions and e.target_node_id in positions:
                    p1 = positions[e.source_node_id]
                    p2 = positions[e.target_node_id]
                    dx = p1[0] - p2[0]
                    dy = p1[1] - p2[1]
                    dist = math.sqrt(dx * dx + dy * dy) or 0.01
                    force = (dist * dist) / k
                    fx = (dx / dist) * force
                    fy = (dy / dist) * force
                    disp[e.source_node_id][0] -= fx
                    disp[e.source_node_id][1] -= fy
                    disp[e.target_node_id][0] += fx
                    disp[e.target_node_id][1] += fy

            # Apply displacement capped by temperature
            for name in node_names:
                if name in pinned_nodes: continue
                dx = disp[name][0]
                dy = disp[name][1]
                d = math.sqrt(dx * dx + dy * dy) or 0.01
                step = min(d, temp)
                positions[name][0] += (dx / d) * step
                positions[name][1] += (dy / d) * step

        return {name: (pos[0], pos[1]) for name, pos in positions.items()}

    def render_graph(self, nodes: List[GraphNodeDTO], edges: List[GraphEdgeDTO]):
        """Renders the knowledge graph in Obsidian Graph View style."""
        self.scene.clear()
        c = ThemeManager.instance().get_colors()
        is_dark = ThemeManager.instance().is_dark()

        if not nodes:
            # Honest empty state
            txt = self.scene.addText("No connected knowledge yet")
            txt.setDefaultTextColor(QColor(c['text_primary']))
            txt.setFont(QFont(DISPLAY_FONT, 16, QFont.Weight.Bold))
            txt.setPos(-txt.boundingRect().width() / 2, -20)
            
            body = self.scene.addText("Add resources to a subject and Kestrel will build this map from real material.")
            body.setDefaultTextColor(QColor(c['text_secondary']))
            body.setFont(QFont(DISPLAY_FONT, 12, QFont.Weight.Normal))
            body.setPos(-body.boundingRect().width() / 2, 20)
            return

        # 1. Degree Centrality Calculation
        degrees = {node.id: 0 for node in nodes}
        for edge in edges:
            if edge.source_node_id in degrees:
                degrees[edge.source_node_id] += 1
            if edge.target_node_id in degrees:
                degrees[edge.target_node_id] += 1

        # 2. Drill-Down / Active Node Filter
        if self.active_node:
            visible_names = {self.active_node}
            for edge in edges:
                if edge.source_node_id == self.active_node:
                    visible_names.add(edge.target_node_id)
                elif edge.target_node_id == self.active_node:
                    visible_names.add(edge.source_node_id)
            current_nodes = [n for n in nodes if n.id in visible_names]
        else:
            current_nodes = list(nodes)
            visible_names = {n.id for n in current_nodes}

        visible_edges = [e for e in edges if e.source_node_id in visible_names and e.target_node_id in visible_names]

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
            if edge.source_node_id in self.node_positions and edge.target_node_id in self.node_positions:
                pair = tuple(sorted([edge.source_node_id, edge.target_node_id]))
                if pair not in drawn_pairs:
                    drawn_pairs.add(pair)
                    x1, y1 = self.node_positions[edge.source_node_id]
                    x2, y2 = self.node_positions[edge.target_node_id]
                    line = self.scene.addLine(x1, y1, x2, y2, edge_pen)
                    line.setZValue(0)

        # 6. Draw Elegant Color-Coded Dots & Crisp Labels (Z=2 & Z=3)
        for node in current_nodes:
            name = node.id
            if name not in self.node_positions:
                continue

            x, y = self.node_positions[name]
            deg = degrees.get(name, 0)
            ntype = node.node_type
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
            ellipse = DraggableNode(name, self.current_snapshot.scope, self.current_snapshot.scope_id or "", x, y, r, self)
            ellipse.setBrush(brush)
            ellipse.setPen(pen)
            ellipse.setData(0, name)
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

    def _on_open_source_clicked(self):
        if not getattr(self, 'selected_node_name', None): return
        node = next((n for n in self.all_nodes if n.id == self.selected_node_name), None)
        if node and node.evidence:
            self.open_source_requested.emit(node.evidence[0])

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
            filtered_nodes = [n for n in filtered_nodes if n.node_type == "concept"]
        elif tag == "Notebooks":
            filtered_nodes = [n for n in filtered_nodes if n.node_type == "board"]
        elif tag == "Tags":
            filtered_nodes = [n for n in filtered_nodes if n.node_type in ("tag", "note")]

        if query:
            filtered_nodes = [n for n in filtered_nodes if query in n.id.lower() or query in n.description.lower()]

        filtered_names = {n.id for n in filtered_nodes}
        filtered_edges = [e for e in self.all_edges if e.source_node_id in filtered_names and e.target_node_id in filtered_names]

        self.render_graph(filtered_nodes, filtered_edges)

    def _update_inspector_by_name(self, name: str):
        node = next((n for n in self.all_nodes if n.id == name), None)
        if not node:
            return

        self.selected_node_name = name
        self.lbl_node_title.setText(name)

        type_display = {
            "subject": "Subject Domain",
            "board": "Notebook Board",
            "tag": "Topic Category",
            "note": "Document Note",
            "concept": "Concept Node"
        }.get(node.node_type, node.node_type.capitalize())

        self.lbl_node_subtitle.setText(f"Type: {type_display} • Knowledge Graph")

        self.lbl_concept_desc.setText(node.description or f"Key relational knowledge node for '{name}'.")

        # Connection counts
        conns = sum(1 for e in self.all_edges if e.source_node_id == name or e.target_node_id == name)
        self.lbl_val_connections.setText(f"{conns} {'Edge' if conns == 1 else 'Edges'}")
        self.lbl_val_type.setText(type_display)
        
        if node.evidence:
            ev = node.evidence[0]
            if ev.chunk_id:
                self.lbl_val_evidence.setText("Semantic Chunk")
            elif ev.material_id:
                self.lbl_val_evidence.setText("Material Structure")
            else:
                self.lbl_val_evidence.setText("Structural DB")
            self.btn_open_source.show()
        else:
            self.lbl_val_evidence.setText("None")
            self.btn_open_source.hide()
            
        self.btn_open_board.setText(f"Drill Down Into '{name}'")

    # ── Theme Application ─────────────────────────────────────────────────

    def _apply_theme(self, theme_name: str = "light"):
        c = ThemeManager.instance().get_colors()
        is_dark = ThemeManager.instance().is_dark()

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
                border-radius: 4px;
                padding: 5px 12px;
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
                border-radius: 4px;
                padding: 5px 10px;
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
                padding: 5px 14px;
            }}
        """)

        # Clean Borderless Inspector Panel Styling
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
            QLabel#lbl_insp_status {{
                font-family: {MONO_FONT};
                font-size: 10px;
                font-weight: 600;
                color: #10b981;
            }}
            QFrame#FormulaBox {{
                background-color: {c['panel_card_bg']};
                border: none;
                border-left: 3px solid {c['accent']};
                border-radius: 4px;
            }}
            QFrame#FormulaBox QLabel#lbl_formula {{
                font-family: {MONO_FONT};
                font-size: 11px;
                font-weight: bold;
                color: {c['text_primary']};
            }}
            QFrame#MetaFrame {{
                background-color: transparent;
                border: none;
            }}
            QLabel#StatKey {{
                font-family: {MONO_FONT};
                font-size: 11px;
                color: {c['text_secondary']};
            }}
            QLabel#StatVal {{
                font-family: {MONO_FONT};
                font-size: 11px;
                font-weight: 700;
                color: {c['text_primary']};
            }}
        """)

        self.lbl_node_title.setStyleSheet(f"""
            font-size: 20px;
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
            color: {c['text_secondary']};
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        """)

        self.btn_open_board.setStyleSheet(primary_button_qss(c))

        # Re-render current graph with updated theme colors
        if self.all_nodes:
            self._apply_current_filters()
