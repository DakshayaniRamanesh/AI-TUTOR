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
    QGraphicsTextItem, QGraphicsItem, QFrame, QSplitter, QToolTip,
    QGraphicsPolygonItem, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import QColor, QPen, QBrush, QFont, QPainter, QPolygonF

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
    ask_tutor_requested = pyqtSignal(str) # prompt query for AI tutor

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
        filter_tags = ["All", "Concepts", "Techniques", "Formulas", "Notebooks"]
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
            "● Core Domain (Slate)  •  ● Concepts (Amber)  •  ● Techniques (Emerald)  •  ● Formulas (Violet)  •  ➔ Prerequisites / Flow  —  [Click node to inspect & ask tutor  •  Drag to pan  •  Wheel to zoom]",
            graph_container
        )
        self.lbl_legend.setStyleSheet("padding: 4px 14px; font-size: 10px;")
        gc_layout.addWidget(self.lbl_legend)

        self.splitter.addWidget(graph_container)

        # Right: Node Inspector Sidebar
        self.inspector_panel = self._create_inspector_panel()
        self.splitter.addWidget(self.inspector_panel)
        self.splitter.setSizes([860, 340])

        root_layout.addWidget(self.splitter, 1)

        # Set empty snapshot initially
        self.set_snapshot(GraphSnapshot(scope="GLOBAL", scope_id=None, revision=0))

    def _create_inspector_panel(self) -> QWidget:
        container = QWidget(self.splitter)
        container.setObjectName("InspectorPanel")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(0)

        # Scroll Area for clean presentation of rich learning material
        scroll = QScrollArea(container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("InspectorContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Header Badge
        h_box = QHBoxLayout()
        self.lbl_insp_badge = QLabel("KNOWLEDGE INSPECTOR", content)
        self.lbl_insp_badge.setObjectName("lbl_insp_badge")
        h_box.addWidget(self.lbl_insp_badge)
        h_box.addStretch()
        self.lbl_insp_status = QLabel("● Active", content)
        self.lbl_insp_status.setObjectName("lbl_insp_status")
        h_box.addWidget(self.lbl_insp_status)
        layout.addLayout(h_box)

        # Title & Subtitle
        self.lbl_node_title = QLabel("Select a concept...", content)
        self.lbl_node_title.setObjectName("lbl_node_title")
        self.lbl_node_title.setWordWrap(True)
        layout.addWidget(self.lbl_node_title)

        self.lbl_node_subtitle = QLabel("Knowledge Graph Node", content)
        self.lbl_node_subtitle.setObjectName("lbl_node_subtitle")
        layout.addWidget(self.lbl_node_subtitle)

        # Formula / Core Rule Box
        self.formula_frame = QFrame(content)
        self.formula_frame.setObjectName("FormulaBox")
        ff_layout = QVBoxLayout(self.formula_frame)
        ff_layout.setContentsMargins(10, 8, 10, 8)
        self.lbl_formula_heading = QLabel("CORE PRINCIPLE / FORMULA", self.formula_frame)
        self.lbl_formula_heading.setObjectName("lbl_formula_heading")
        self.lbl_formula_val = QLabel("", self.formula_frame)
        self.lbl_formula_val.setObjectName("lbl_formula")
        self.lbl_formula_val.setWordWrap(True)
        ff_layout.addWidget(self.lbl_formula_heading)
        ff_layout.addWidget(self.lbl_formula_val)
        self.formula_frame.hide()
        layout.addWidget(self.formula_frame)

        # Description text
        self.lbl_concept_desc = QLabel(
            "Select any node in the knowledge graph to view its definition, "
            "interconnected learning pathway, and prerequisite formulas.",
            content
        )
        self.lbl_concept_desc.setObjectName("lbl_concept_desc")
        self.lbl_concept_desc.setWordWrap(True)
        layout.addWidget(self.lbl_concept_desc)

        # ── Connected Learning Pathway Section ──
        self.pathway_frame = QFrame(content)
        self.pathway_frame.setObjectName("PathwayFrame")
        pf_layout = QVBoxLayout(self.pathway_frame)
        pf_layout.setContentsMargins(0, 4, 0, 4)
        pf_layout.setSpacing(10)

        # Prerequisites sub-box
        self.box_prereqs = QWidget(self.pathway_frame)
        bp_layout = QVBoxLayout(self.box_prereqs)
        bp_layout.setContentsMargins(0, 0, 0, 0)
        bp_layout.setSpacing(4)
        self.lbl_prereqs_title = QLabel("PREREQUISITES TO LEARN FIRST", self.box_prereqs)
        self.lbl_prereqs_title.setObjectName("SectionHeader")
        self.prereqs_chip_layout = QHBoxLayout()
        self.prereqs_chip_layout.setSpacing(6)
        bp_layout.addWidget(self.lbl_prereqs_title)
        bp_layout.addLayout(self.prereqs_chip_layout)
        pf_layout.addWidget(self.box_prereqs)

        # Unlocks sub-box
        self.box_unlocks = QWidget(self.pathway_frame)
        bu_layout = QVBoxLayout(self.box_unlocks)
        bu_layout.setContentsMargins(0, 0, 0, 0)
        bu_layout.setSpacing(4)
        self.lbl_unlocks_title = QLabel("UNLOCKS & BUILDS INTO", self.box_unlocks)
        self.lbl_unlocks_title.setObjectName("SectionHeader")
        self.unlocks_chip_layout = QHBoxLayout()
        self.unlocks_chip_layout.setSpacing(6)
        bu_layout.addWidget(self.lbl_unlocks_title)
        bu_layout.addLayout(self.unlocks_chip_layout)
        pf_layout.addWidget(self.box_unlocks)

        # Applications / Derivations sub-box
        self.box_apps = QWidget(self.pathway_frame)
        ba_layout = QVBoxLayout(self.box_apps)
        ba_layout.setContentsMargins(0, 0, 0, 0)
        ba_layout.setSpacing(4)
        self.lbl_apps_title = QLabel("APPLICATIONS & DERIVATIONS", self.box_apps)
        self.lbl_apps_title.setObjectName("SectionHeader")
        self.apps_chip_layout = QHBoxLayout()
        self.apps_chip_layout.setSpacing(6)
        ba_layout.addWidget(self.lbl_apps_title)
        ba_layout.addLayout(self.apps_chip_layout)
        pf_layout.addWidget(self.box_apps)

        layout.addWidget(self.pathway_frame)

        # Clean Key-Value Details (Borderless, Modern Stat Rows)
        self.meta_frame = QFrame(content)
        self.meta_frame.setObjectName("MetaFrame")
        mf_layout = QVBoxLayout(self.meta_frame)
        mf_layout.setContentsMargins(0, 6, 0, 6)
        mf_layout.setSpacing(6)

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

        # Action Buttons
        self.btn_ask_tutor = QPushButton("✦ Ask AI Tutor About Concept", content)
        self.btn_ask_tutor.setObjectName("btn_ask_tutor")
        self.btn_ask_tutor.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ask_tutor.clicked.connect(self._on_ask_tutor_clicked)
        layout.addWidget(self.btn_ask_tutor)

        self.btn_open_board = QPushButton("Focus / Center On Concept", content)
        self.btn_open_board.setObjectName("btn_open_board")
        self.btn_open_board.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_board.clicked.connect(self._on_drill_down_clicked)
        layout.addWidget(self.btn_open_board)

        self.btn_open_source = QPushButton("Open Evidence Source", content)
        self.btn_open_source.setObjectName("btn_open_source")
        self.btn_open_source.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_source.clicked.connect(self._on_open_source_clicked)
        self.btn_open_source.hide()
        layout.addWidget(self.btn_open_source)

        scroll.setWidget(content)
        c_layout.addWidget(scroll)
        return container

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    # ── Graph Data Aggregation & Rendering ─────────────────────────────────

    def set_snapshot(self, snapshot: GraphSnapshot):
        """Replaces the current graph with a new snapshot and re-renders."""
        self.current_snapshot = snapshot
        self.all_nodes = list(snapshot.nodes)
        self.all_edges = list(snapshot.edges)
        self.node_positions = {}
        
        # Merge layout states if any
        if snapshot.layout:
            for node_id, l_state in snapshot.layout.items():
                self.node_positions[node_id] = (l_state.x, l_state.y)
                
        self.render_graph(self.all_nodes, self.all_edges)

    def _compute_cluster_layout(self, nodes: List[GraphNodeDTO], edges: List[GraphEdgeDTO]) -> Dict[str, Tuple[float, float]]:
        """Computes an organic Obsidian-style constellation / multi-cluster force layout."""
        import random
        random.seed(42)

        node_names = [n.id for n in nodes]
        positions: Dict[str, List[float]] = {
            node_id: [float(pos[0]), float(pos[1])]
            for node_id, pos in self.node_positions.items()
            if node_id in node_names
        }
        pinned_nodes = {
            node_id for node_id, state in getattr(self.current_snapshot, "layout", {}).items()
            if getattr(state, "pinned", False)
        }

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
        hubs = [n.id for n in nodes if getattr(n.node_type, "value", str(n.node_type)).upper() == "SUBJECT" or degrees[n.id] >= 5]
        if not hubs:
            hubs = sorted(node_names, key=lambda n: degrees[n], reverse=True)[:4]

        # 1. Initial Seeding: Place hubs in a wide constellation circle
        num_hubs = max(1, len(hubs))
        hub_radius = 280.0 if num_hubs <= 4 else 380.0
        for idx, hub_name in enumerate(hubs):
            angle = idx * ((2.0 * math.pi) / num_hubs)
            positions.setdefault(hub_name, [hub_radius * math.cos(angle), hub_radius * math.sin(angle)])

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
                orbit_r = random.uniform(90.0, 170.0)
                orbit_angle = random.uniform(0, 2.0 * math.pi)
                positions[name] = [hx + orbit_r * math.cos(orbit_angle), hy + orbit_r * math.sin(orbit_angle)]
            else:
                # Place in outer orbit
                r = random.uniform(160.0, 360.0)
                a = random.uniform(0, 2.0 * math.pi)
                positions[name] = [r * math.cos(a), r * math.sin(a)]

        # 3. Force-Directed Relaxation (50 iterations)
        k = 130.0  # optimal distance
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
        """Renders the knowledge graph in Obsidian Graph View style with pedagogical direction."""
        self.scene.clear()
        c = ThemeManager.instance().get_colors()
        is_dark = ThemeManager.instance().is_dark()

        if not nodes:
            # Empty state
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

        # 4. Color Palette & Radius Calculation
        color_hub = QColor("#64748b") if not is_dark else QColor("#94a3b8")
        color_hub_border = QColor("#475569") if not is_dark else QColor("#cbd5e1")

        color_tag = QColor("#d97706") if not is_dark else QColor("#fbbf24")
        color_tag_border = QColor("#b45309") if not is_dark else QColor("#f59e0b")

        color_note = QColor("#0284c7") if not is_dark else QColor("#38bdf8")
        color_note_border = QColor("#0369a1") if not is_dark else QColor("#7dd3fc")

        for node in current_nodes:
            name = node.id
            ntype = getattr(node.node_type, "value", str(node.node_type)).upper()
            deg = degrees.get(name, 0)
            if ntype == "SUBJECT" or deg >= 6:
                r = 9.0
            elif ntype in ("FORMULA", "THEOREM"):
                r = 6.5
            elif ntype in ("TECHNIQUE", "MODULE"):
                r = 6.0
            else:
                r = 5.0
            self.node_radii[name] = r
            self.node_summaries[name] = node.description

        # 5. Draw Distinctive Pedagogical Edges with Directional Cues
        drawn_pairs = set()
        for edge in visible_edges:
            if edge.source_node_id not in self.node_positions or edge.target_node_id not in self.node_positions:
                continue

            rel = getattr(edge.relation_type, "value", str(edge.relation_type)).upper()
            pair_key = (edge.source_node_id, edge.target_node_id, rel)
            if pair_key in drawn_pairs:
                continue
            drawn_pairs.add(pair_key)

            x1, y1 = self.node_positions[edge.source_node_id]
            x2, y2 = self.node_positions[edge.target_node_id]

            # Style based on pedagogical relationship
            if rel == "PREREQUISITE_OF":
                edge_color = QColor("#d97706") if not is_dark else QColor("#f59e0b")
                pen = QPen(edge_color, 1.5, Qt.PenStyle.SolidLine)
                has_arrow = True
                arrow_to_target = True
            elif rel == "APPLIES_TO":
                edge_color = QColor("#0284c7") if not is_dark else QColor("#38bdf8")
                pen = QPen(edge_color, 1.3, Qt.PenStyle.SolidLine)
                has_arrow = True
                arrow_to_target = True
            elif rel == "DERIVED_FROM":
                edge_color = QColor("#7c3aed") if not is_dark else QColor("#a78bfa")
                pen = QPen(edge_color, 1.3, Qt.PenStyle.DashDotLine)
                has_arrow = True
                arrow_to_target = False  # Points from origin
            elif rel == "PART_OF":
                edge_color = QColor(148, 163, 184, 150) if not is_dark else QColor(100, 116, 139, 150)
                pen = QPen(edge_color, 1.0, Qt.PenStyle.DashLine)
                has_arrow = False
                arrow_to_target = True
            else:
                edge_color = QColor(203, 213, 225, 140) if not is_dark else QColor(71, 85, 105, 140)
                pen = QPen(edge_color, 1.0, Qt.PenStyle.SolidLine)
                has_arrow = False
                arrow_to_target = True

            pen.setCosmetic(True)
            line = self.scene.addLine(x1, y1, x2, y2, pen)
            line.setZValue(0)

            # Draw crisp directional arrowhead
            if has_arrow:
                dx = x2 - x1 if arrow_to_target else x1 - x2
                dy = y2 - y1 if arrow_to_target else y1 - y2
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 20.0:
                    ux = dx / dist
                    uy = dy / dist
                    tgt_id = edge.target_node_id if arrow_to_target else edge.source_node_id
                    r_tgt = self.node_radii.get(tgt_id, 5.0)
                    tgt_x = x2 if arrow_to_target else x1
                    tgt_y = y2 if arrow_to_target else y1
                    
                    tip_x = tgt_x - ux * (r_tgt + 2.5)
                    tip_y = tgt_y - uy * (r_tgt + 2.5)
                    arrow_len = 7.5
                    arrow_w = 3.5
                    bx = tip_x - ux * arrow_len
                    by = tip_y - uy * arrow_len
                    px = -uy * arrow_w
                    py = ux * arrow_w

                    poly = QPolygonF([
                        QPointF(tip_x, tip_y),
                        QPointF(bx + px, by + py),
                        QPointF(bx - px, by - py)
                    ])
                    arrow_item = self.scene.addPolygon(poly, QPen(edge_color, 0.5), QBrush(edge_color))
                    arrow_item.setZValue(1)

        # 6. Draw Elegant Color-Coded Dots & Crisp Labels (Z=2 & Z=3)
        for node in current_nodes:
            name = node.id
            if name not in self.node_positions:
                continue

            x, y = self.node_positions[name]
            deg = degrees.get(name, 0)
            ntype = getattr(node.node_type, "value", str(node.node_type)).upper()
            r = self.node_radii[name]

            # Node Classification & Sizing
            if ntype == "SUBJECT" or deg >= 6:
                # Major Core Hub: Slate
                brush = QBrush(color_hub)
                pen = QPen(color_hub_border, 1.2)
                font = QFont("Consolas", 8, QFont.Weight.DemiBold)
                text_color = QColor("#1e293b") if not is_dark else QColor("#f8fafc")
            elif ntype in ("FORMULA", "THEOREM"):
                # Formulas / Theorems: Violet
                brush = QBrush(QColor("#7c3aed") if not is_dark else QColor("#a78bfa"))
                pen = QPen(QColor("#6d28d9") if not is_dark else QColor("#c4b5fd"), 1.2)
                font = QFont("Consolas", 8, QFont.Weight.DemiBold)
                text_color = QColor("#5b21b6") if not is_dark else QColor("#ddd6fe")
            elif ntype == "TECHNIQUE":
                # Techniques: Emerald Green
                brush = QBrush(QColor("#059669") if not is_dark else QColor("#34d399"))
                pen = QPen(QColor("#047857") if not is_dark else QColor("#6ee7b7"), 1.1)
                font = QFont("Consolas", 8, QFont.Weight.Normal)
                text_color = QColor("#065f46") if not is_dark else QColor("#a7f3d0")
            elif ntype == "MODULE" or name.startswith("#"):
                # Tag / Module: Warm Amber
                brush = QBrush(color_tag)
                pen = QPen(color_tag_border, 1.0)
                font = QFont("Consolas", 8, QFont.Weight.Normal)
                text_color = QColor("#92400e") if not is_dark else QColor("#fde68a")
            else:
                # Standard Concept: Sky Blue
                brush = QBrush(color_note)
                pen = QPen(color_note_border, 1.0)
                font = QFont("Consolas", 7, QFont.Weight.Normal)
                text_color = QColor("#0369a1") if not is_dark else QColor("#bae6fd")

            # Node Dot Item
            ellipse = DraggableNode(name, self.current_snapshot.scope, self.current_snapshot.scope_id or "", x, y, r, self)
            ellipse.setBrush(brush)
            ellipse.setPen(pen)
            ellipse.setData(0, name)
            self.scene.addItem(ellipse)

            # Node Label Item (placed cleanly beside the circle)
            text = QGraphicsTextItem(node.display_name)
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
        target_inspect = self.active_node or (current_nodes[0].id if current_nodes else None)
        if target_inspect:
            self._update_inspector_by_name(target_inspect)

    # ── Interaction Handlers ───────────────────────────────────────────────

    def go_back_to_main(self):
        """Returns from drill-down to the full knowledge graph."""
        self.active_node = None
        self.btn_back.hide()
        self._apply_current_filters()

    def select_and_focus_node(self, node_id_or_name: str):
        """Selects a node from connected chips or search and centers the viewport."""
        node = next((n for n in self.all_nodes if n.id == node_id_or_name or n.display_name.lower() == node_id_or_name.lower()), None)
        if not node:
            return
        self.selected_node_name = node.id
        self._update_inspector_by_name(node.id)
        if node.id in self.node_positions:
            pos = self.node_positions[node.id]
            self.view.centerOn(pos[0], pos[1])

    def _on_ask_tutor_clicked(self):
        """Invokes the AI tutor with a targeted contextual explanation query."""
        if not getattr(self, 'selected_node_name', None):
            return
        node = next((n for n in self.all_nodes if n.id == self.selected_node_name), None)
        name = node.display_name if node else self.selected_node_name
        prompt = f"Can you explain {name} in detail, showing its core principles, formulas, and how it connects to its prerequisites?"
        self.ask_tutor_requested.emit(prompt)

    def _on_open_source_clicked(self):
        if not getattr(self, 'selected_node_name', None): return
        node = next((n for n in self.all_nodes if n.id == self.selected_node_name), None)
        if node and node.evidence:
            self.open_source_requested.emit(node.evidence[0])

    def _on_drill_down_clicked(self):
        if self.selected_node_name:
            self.active_node = self.selected_node_name
            node = next((n for n in self.all_nodes if n.id == self.selected_node_name), None)
            dname = node.display_name if node else self.active_node
            self.btn_back.setText(f"← Back (Viewing: {dname})")
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
                node = next((n for n in self.all_nodes if n.id == node_name), None)
                dname = node.display_name if node else node_name
                self.btn_back.setText(f"← Back (Viewing: {dname})")
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
            filtered_nodes = [n for n in filtered_nodes if getattr(n.node_type, "value", str(n.node_type)).upper() == "CONCEPT"]
        elif tag == "Techniques":
            filtered_nodes = [n for n in filtered_nodes if getattr(n.node_type, "value", str(n.node_type)).upper() == "TECHNIQUE"]
        elif tag == "Formulas":
            filtered_nodes = [n for n in filtered_nodes if getattr(n.node_type, "value", str(n.node_type)).upper() in ("FORMULA", "THEOREM")]
        elif tag == "Notebooks":
            filtered_nodes = [n for n in filtered_nodes if getattr(n.node_type, "value", str(n.node_type)).upper() == "NOTEBOOK"]

        if query:
            filtered_nodes = [n for n in filtered_nodes if
                              query in n.display_name.lower() or
                              query in (n.description or "").lower()]

        filtered_names = {n.id for n in filtered_nodes}
        filtered_edges = [e for e in self.all_edges if e.source_node_id in filtered_names and e.target_node_id in filtered_names]

        self.render_graph(filtered_nodes, filtered_edges)

    def _update_inspector_by_name(self, name: str):
        node = next((n for n in self.all_nodes if n.id == name or n.display_name.lower() == name.lower()), None)
        if not node:
            return

        self.selected_node_name = node.id
        self.lbl_node_title.setText(node.display_name)

        node_type = getattr(node.node_type, "value", str(node.node_type)).upper()
        type_display = {
            "SUBJECT": "Subject Domain",
            "NOTEBOOK": "Notebook Board",
            "MODULE": "Module",
            "RESOURCE": "Document Resource",
            "CONCEPT": "Core Concept",
            "TECHNIQUE": "Solving Technique",
            "FORMULA": "Mathematical Formula",
            "THEOREM": "Theorem & Law",
            "EXERCISE": "Exercise",
            "EXAMPLE": "Worked Example",
        }.get(node_type, str(node_type).title())

        self.lbl_node_subtitle.setText(f"Type: {type_display} • Knowledge Graph")

        desc = node.description or f"Key relational knowledge node for '{node.display_name}'."
        self.lbl_concept_desc.setText(desc)

        # Check for formula or rule equations in description
        if any(sym in desc for sym in ("=", "lim", "Delta", "tau", "^2", "ax", "∫", "√")):
            self.formula_frame.show()
            self.lbl_formula_val.setText(desc)
        else:
            self.formula_frame.hide()

        # Connection counts
        conns = sum(1 for e in self.all_edges if e.source_node_id == node.id or e.target_node_id == node.id)
        self.lbl_val_connections.setText(f"{conns} {'Edge' if conns == 1 else 'Edges'}")
        self.lbl_val_type.setText(type_display)

        # ── Populate Connected Learning Pathway ──
        self._clear_layout(self.prereqs_chip_layout)
        self._clear_layout(self.unlocks_chip_layout)
        self._clear_layout(self.apps_chip_layout)

        c = ThemeManager.instance().get_colors()

        def make_chip(target_id: str, label_text: str):
            btn = QPushButton(label_text)
            btn.setObjectName("ConceptChip")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton#ConceptChip {{
                    background-color: {c['panel_card_bg']};
                    color: {c['text_primary']};
                    border: 1px solid {c['border_color']};
                    border-radius: 10px;
                    padding: 3px 8px;
                    font-family: {MONO_FONT};
                    font-size: 10px;
                    font-weight: 500;
                }}
                QPushButton#ConceptChip:hover {{
                    border-color: {c['accent']};
                    background-color: {c['bg_card']};
                }}
            """)
            btn.clicked.connect(lambda _, tid=target_id: self.select_and_focus_node(tid))
            return btn

        # Map IDs to display names
        node_name_map = {n.id: n.display_name for n in self.all_nodes}

        # 1. Prerequisites (where target == node.id and rel == PREREQUISITE_OF, or source == node.id and rel == DERIVED_FROM)
        prereq_ids = []
        for e in self.all_edges:
            rel = getattr(e.relation_type, "value", str(e.relation_type)).upper()
            if e.target_node_id == node.id and rel == "PREREQUISITE_OF":
                prereq_ids.append(e.source_node_id)
            elif e.source_node_id == node.id and rel == "DERIVED_FROM":
                prereq_ids.append(e.target_node_id)

        if prereq_ids:
            self.box_prereqs.show()
            for pid in set(prereq_ids):
                p_name = node_name_map.get(pid, pid)
                self.prereqs_chip_layout.addWidget(make_chip(pid, p_name))
            self.prereqs_chip_layout.addStretch()
        else:
            self.box_prereqs.hide()

        # 2. Unlocks / Next (where source == node.id and rel == PREREQUISITE_OF)
        unlock_ids = []
        for e in self.all_edges:
            rel = getattr(e.relation_type, "value", str(e.relation_type)).upper()
            if e.source_node_id == node.id and rel == "PREREQUISITE_OF":
                unlock_ids.append(e.target_node_id)

        if unlock_ids:
            self.box_unlocks.show()
            for uid in set(unlock_ids):
                u_name = node_name_map.get(uid, uid)
                self.unlocks_chip_layout.addWidget(make_chip(uid, u_name))
            self.unlocks_chip_layout.addStretch()
        else:
            self.box_unlocks.hide()

        # 3. Applications & Derivations
        app_ids = []
        for e in self.all_edges:
            rel = getattr(e.relation_type, "value", str(e.relation_type)).upper()
            if rel == "APPLIES_TO":
                if e.source_node_id == node.id:
                    app_ids.append(e.target_node_id)
                elif e.target_node_id == node.id:
                    app_ids.append(e.source_node_id)

        if app_ids:
            self.box_apps.show()
            for aid in set(app_ids):
                a_name = node_name_map.get(aid, aid)
                self.apps_chip_layout.addWidget(make_chip(aid, a_name))
            self.apps_chip_layout.addStretch()
        else:
            self.box_apps.hide()

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
            self.lbl_val_evidence.setText("Curricular Grounding")
            self.btn_open_source.hide()

        self.btn_open_board.setText(f"Center On '{node.display_name}'")

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
            QWidget#InspectorContent {{
                background-color: {c['bg_card']};
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
            QLabel#lbl_formula_heading {{
                font-family: {MONO_FONT};
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 1px;
                color: {c['accent']};
            }}
            QLabel#lbl_formula {{
                font-family: {MONO_FONT};
                font-size: 11px;
                font-weight: bold;
                color: {c['text_primary']};
            }}
            QLabel#SectionHeader {{
                font-family: {MONO_FONT};
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 0.8px;
                color: {c['text_secondary']};
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
            QPushButton#btn_ask_tutor {{
                background-color: #2563eb;
                color: #ffffff;
                border: 1px solid #1d4ed8;
                border-radius: 6px;
                padding: 9px 14px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton#btn_ask_tutor:hover {{
                background-color: #1d4ed8;
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

        self.btn_open_board.setStyleSheet(ghost_button_qss(c, radius=6))

        # Re-render current graph with updated theme colors
        if self.all_nodes:
            self._apply_current_filters()
