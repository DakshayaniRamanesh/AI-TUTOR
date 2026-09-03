"""
Obsidian-Style Interactive Knowledge Graph Visualizer Panel
Monochrome / Technical Aesthetic matching Figma Reference
Node-Edge physics force simulation visualizing document relationships, hashtags,
and cross-references with dragging, hover highlighting, Node Inspector sidebar, and tag filtering.
"""

import math
import random
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsLineItem,
    QGraphicsTextItem, QGraphicsItem, QFrame, QSplitter, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QColor, QPen, QBrush, QFont, QPainter

from ...backend.knowledge_graph.tag_graph_parser import TagGraphParser
from ..theme_manager import ThemeManager
from ..kestrel_theme import MONO_FONT, primary_button_qss, ghost_button_qss


class GraphNodeItem(QGraphicsEllipseItem):
    def __init__(self, node_data: dict, radius: float = 12.0, parent=None):
        super().__init__(-radius, -radius, radius * 2, radius * 2, parent)
        self.node_data = node_data
        self.radius = radius
        self.vx = 0.0
        self.vy = 0.0
        self.edges = []

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setAcceptHoverEvents(True)

        self._apply_node_style()

    def _apply_node_style(self):
        c = ThemeManager.instance().get_colors()
        ntype = self.node_data.get("type", "note")

        if ntype == "board":
            # Central board nodes: solid accent circle (black in light mode)
            self.base_color = QColor(c['accent'])
            self.setPen(QPen(QColor(c['border_color']), 2))
            self.setBrush(QBrush(self.base_color))
        elif ntype == "tag":
            # Tag nodes: subtle pill-like styling
            self.base_color = QColor(c['panel_card_bg'])
            self.setPen(QPen(QColor(c['border_color']), 1.5))
            self.setBrush(QBrush(self.base_color))
        else:
            # Markdown / Note nodes: card background with clean border
            self.base_color = QColor(c['bg_card'])
            self.setPen(QPen(QColor(c['text_secondary']), 1.5))
            self.setBrush(QBrush(self.base_color))

        # Title Label
        if hasattr(self, 'label_item') and self.label_item:
            self.scene().removeItem(self.label_item) if self.scene() else None

        self.label_item = QGraphicsTextItem(self.node_data.get("label", ""), self)
        self.label_item.setDefaultTextColor(QColor(c['text_primary']))
        font = QFont(MONO_FONT, 8, QFont.Weight.Bold if ntype == "board" else QFont.Weight.Medium)
        self.label_item.setFont(font)

        # Center label under circle
        rect = self.label_item.boundingRect()
        self.label_item.setPos(-rect.width() / 2, self.radius + 2)

    def hoverEnterEvent(self, event):
        c = ThemeManager.instance().get_colors()
        self.setScale(1.2)
        for edge in self.edges:
            edge.set_highlight(True)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setScale(1.0)
        for edge in self.edges:
            edge.set_highlight(False)
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self.edges:
                edge.update_position()
        return super().itemChange(change, value)


class GraphEdgeItem(QGraphicsLineItem):
    def __init__(self, source_item: GraphNodeItem, target_item: GraphNodeItem, parent=None):
        super().__init__(parent)
        self.source_item = source_item
        self.target_item = target_item
        
        source_item.edges.append(self)
        target_item.edges.append(self)

        c = ThemeManager.instance().get_colors()
        self.normal_pen = QPen(QColor(c['border_color']), 1.2, Qt.PenStyle.SolidLine)
        self.highlight_pen = QPen(QColor(c['accent']), 2.2, Qt.PenStyle.SolidLine)
        self.setPen(self.normal_pen)
        self.setZValue(-1)
        self.update_position()

    def update_position(self):
        p1 = self.source_item.pos()
        p2 = self.target_item.pos()
        self.setLine(p1.x(), p1.y(), p2.x(), p2.y())

    def set_highlight(self, highlight: bool):
        self.setPen(self.highlight_pen if highlight else self.normal_pen)


class ObsidianGraphPanel(QWidget):
    open_notebook_requested = pyqtSignal(str) # notebook_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parser = TagGraphParser()
        self.node_items = {}
        self.edge_items = []
        self.physics_enabled = True
        self.selected_node_id = None

        self._init_ui()
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme(ThemeManager.instance().current_theme)

        # Physics Force Simulation Timer (30 FPS)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._step_physics_simulation)
        self.timer.start(33)

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Top Control & Filter Header Bar
        self.header_bar = QWidget(self)
        self.header_bar.setFixedHeight(50)
        h_layout = QHBoxLayout(self.header_bar)
        h_layout.setContentsMargins(16, 8, 16, 8)
        h_layout.setSpacing(8)

        # Category Filter Pills
        self.filter_buttons = []
        filter_tags = ["All", "Pure Calculus", "Mechanics", "Heat Flow", "Kinetics"]
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
        self.txt_search.setPlaceholderText("⌕ Search nodes...")
        self.txt_search.setFixedWidth(200)
        self.txt_search.textChanged.connect(self._filter_graph)
        h_layout.addWidget(self.txt_search)

        # Zoom & Physics Buttons
        self.btn_zoom_in = QPushButton("+", self.header_bar)
        self.btn_zoom_in.setFixedSize(28, 28)
        self.btn_zoom_in.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_zoom_in.clicked.connect(lambda: self.view.scale(1.2, 1.2))
        h_layout.addWidget(self.btn_zoom_in)

        self.btn_zoom_out = QPushButton("-", self.header_bar)
        self.btn_zoom_out.setFixedSize(28, 28)
        self.btn_zoom_out.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_zoom_out.clicked.connect(lambda: self.view.scale(0.83, 0.83))
        h_layout.addWidget(self.btn_zoom_out)

        self.btn_physics = QPushButton("❚❚", self.header_bar)
        self.btn_physics.setFixedSize(28, 28)
        self.btn_physics.setToolTip("Toggle Physics")
        self.btn_physics.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_physics.clicked.connect(self._toggle_physics)
        h_layout.addWidget(self.btn_physics)

        root_layout.addWidget(self.header_bar)

        # Main Splitter: Interactive Graph View (Left) + Node Inspector Sidebar (Right)
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setHandleWidth(1)

        # ── Left: Graph Scene & View ──
        graph_container = QWidget(self.splitter)
        gc_layout = QVBoxLayout(graph_container)
        gc_layout.setContentsMargins(0, 0, 0, 0)
        gc_layout.setSpacing(0)

        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(-1000, -800, 2000, 1600)
        self.scene.selectionChanged.connect(self._on_scene_selection_changed)

        self.view = QGraphicsView(self.scene, graph_container)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        gc_layout.addWidget(self.view)

        # Bottom Legend / Status
        self.lbl_legend = QLabel("drag nodes to rearrange • click node to inspect", graph_container)
        self.lbl_legend.setStyleSheet("padding: 4px 12px; font-size: 10px;")
        gc_layout.addWidget(self.lbl_legend)

        self.splitter.addWidget(graph_container)

        # ── Right: Node Inspector Sidebar ──
        self.inspector_panel = self._create_inspector_panel()
        self.splitter.addWidget(self.inspector_panel)
        self.splitter.setSizes([850, 320])

        root_layout.addWidget(self.splitter, 1)

        # Initial Graph Load
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
        self.lbl_node_title = QLabel("Select a node...", panel)
        self.lbl_node_title.setWordWrap(True)
        layout.addWidget(self.lbl_node_title)

        self.lbl_node_subtitle = QLabel("Unit / Topic Reference", panel)
        layout.addWidget(self.lbl_node_subtitle)

        # Formula / Core Snippet Box
        self.box_formula = QFrame(panel)
        self.box_formula.setObjectName("FormulaBox")
        fb_layout = QVBoxLayout(self.box_formula)
        fb_layout.setContentsMargins(10, 10, 10, 10)
        self.lbl_formula = QLabel("lim A = 0", self.box_formula)
        fb_layout.addWidget(self.lbl_formula)
        layout.addWidget(self.box_formula)

        # Description text
        self.lbl_concept_desc = QLabel(
            "Core Concept: Direct factor cancellation reveals limit A = 0 along all linear paths through the origin.",
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

        self.lbl_meta_questions = QLabel("Linked Questions:       Q5, Q6", self.meta_frame)
        self.lbl_meta_theorems = QLabel("Connected Outbound:     4 Theorems", self.meta_frame)
        self.lbl_meta_confidence = QLabel("Confidence Score:       99.4%", self.meta_frame)

        mf_layout.addWidget(self.lbl_meta_questions)
        mf_layout.addWidget(self.lbl_meta_theorems)
        mf_layout.addWidget(self.lbl_meta_confidence)
        layout.addWidget(self.meta_frame)

        layout.addStretch()

        # Action Buttons
        self.btn_open_board = QPushButton("Open Board", panel)
        self.btn_open_board.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_board.clicked.connect(self._on_open_selected_board)
        layout.addWidget(self.btn_open_board)

        self.btn_expand = QPushButton("Expand Cluster", panel)
        self.btn_expand.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.btn_expand)

        return panel

    def _apply_theme(self, theme_name: str = "light"):
        c = ThemeManager.instance().get_colors()

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {c['bg_app']};
                color: {c['text_primary']};
                font-family: {MONO_FONT};
            }}
            QWidget#InspectorPanel {{
                background-color: {c['bg_card']};
                border-left: 1px solid {c['border_color']};
            }}
            QFrame#FormulaBox, QFrame#MetaFrame {{
                background-color: {c['input_bg']};
                border: 1px solid {c['border_color']};
                border-radius: 2px;
            }}
            QSplitter::handle {{
                background-color: {c['border_color']};
            }}
            QGraphicsView {{
                border: none;
                background-color: {c['bg_app']};
            }}
            QLineEdit {{
                background-color: {c['input_bg']};
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                padding: 4px 8px;
                font-family: {MONO_FONT};
                font-size: 11px;
                color: {c['text_primary']};
            }}
        """)

        # Header Bar Styling
        self.header_bar.setStyleSheet(f"background-color: {c['bg_card']}; border-bottom: 1px solid {c['border_color']};")
        self.scene.setBackgroundBrush(QBrush(QColor(c['bg_app'])))

        # Filter Pills Styling
        for btn in self.filter_buttons:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {c['text_secondary']};
                    border: 1px solid {c['border_color']};
                    border-radius: 2px;
                    padding: 4px 10px;
                    font-family: {MONO_FONT};
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:checked {{
                    background-color: {c['accent']};
                    color: {c['accent_text']};
                    border-color: {c['accent']};
                }}
                QPushButton:hover:!checked {{
                    border-color: {c['accent']};
                    color: {c['text_primary']};
                }}
            """)

        # Utility Buttons
        util_style = f"""
            QPushButton {{
                background-color: {c['bg_card']};
                color: {c['text_primary']};
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                font-family: {MONO_FONT};
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {c['panel_card_bg']};
                border-color: {c['accent']};
            }}
        """
        self.btn_zoom_in.setStyleSheet(util_style)
        self.btn_zoom_out.setStyleSheet(util_style)
        self.btn_physics.setStyleSheet(util_style)

        # Inspector Panel Typography & Buttons
        self.lbl_insp_badge.setStyleSheet(f"font-size: 11px; font-weight: 800; letter-spacing: 1px; color: {c['text_secondary']};")
        self.lbl_insp_status.setStyleSheet(f"font-size: 10px; font-weight: 600; color: {c['text_secondary']};")
        self.lbl_node_title.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {c['text_primary']};")
        self.lbl_node_subtitle.setStyleSheet(f"font-size: 11px; color: {c['text_secondary']};")
        self.lbl_formula.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {c['text_primary']};")
        self.lbl_concept_desc.setStyleSheet(f"font-size: 11px; color: {c['text_secondary']}; line-height: 1.4;")
        self.lbl_meta_questions.setStyleSheet(f"font-size: 11px; color: {c['text_secondary']};")
        self.lbl_meta_theorems.setStyleSheet(f"font-size: 11px; color: {c['text_secondary']};")
        self.lbl_meta_confidence.setStyleSheet(f"font-size: 11px; color: {c['text_secondary']};")
        self.lbl_legend.setStyleSheet(f"font-size: 10px; color: {c['text_secondary']}; font-family: {MONO_FONT};")

        self.btn_open_board.setStyleSheet(primary_button_qss(c))
        self.btn_expand.setStyleSheet(ghost_button_qss(c))

        # Re-apply styles to graph nodes and edges
        for node in self.node_items.values():
            node._apply_node_style()
        for edge in self.edge_items:
            edge.normal_pen = QPen(QColor(c['border_color']), 1.2, Qt.PenStyle.SolidLine)
            edge.highlight_pen = QPen(QColor(c['accent']), 2.2, Qt.PenStyle.SolidLine)
            edge.setPen(edge.normal_pen)

    def load_graph(self):
        self.scene.clear()
        self.node_items.clear()
        self.edge_items.clear()

        graph_data = self.parser.build_knowledge_graph()
        nodes = graph_data["nodes"]
        edges = graph_data["edges"]

        num_nodes = len(nodes)
        radius_span = max(180, num_nodes * 25)

        for idx, n in enumerate(nodes):
            r = 14.0 if n["type"] == "board" else (11.0 if n["type"] == "note" else 9.0)
            node_item = GraphNodeItem(n, radius=r)
            
            angle = (2 * math.pi / max(1, num_nodes)) * idx
            dist = random.uniform(60, radius_span)
            x = dist * math.cos(angle)
            y = dist * math.sin(angle)
            node_item.setPos(x, y)

            self.scene.addItem(node_item)
            self.node_items[n["id"]] = node_item

        for e in edges:
            src_item = self.node_items.get(e["source"])
            tgt_item = self.node_items.get(e["target"])
            if src_item and tgt_item:
                edge_item = GraphEdgeItem(src_item, tgt_item)
                self.scene.addItem(edge_item)
                self.edge_items.append(edge_item)

        # Select first node if available
        if nodes:
            first_node = nodes[0]
            self._update_inspector(first_node)

    def _on_filter_pill_clicked(self, tag: str, active_btn: QPushButton):
        for btn in self.filter_buttons:
            btn.setChecked(btn == active_btn)
        if tag == "All":
            self._filter_graph("")
        else:
            self._filter_graph(tag)

    def _on_scene_selection_changed(self):
        selected = self.scene.selectedItems()
        for item in selected:
            if isinstance(item, GraphNodeItem):
                self._update_inspector(item.node_data)
                break

    def _update_inspector(self, node_data: dict):
        self.selected_node_id = node_data.get("id")
        label = node_data.get("label", "Node")
        ntype = node_data.get("type", "note")

        self.lbl_node_title.setText(label)
        self.lbl_node_subtitle.setText(f"Type: {ntype.capitalize()} • Knowledge Graph Reference")
        
        # Customize formula and metadata display based on node
        clean_label = label.replace("#", "")
        self.lbl_formula.setText(f"∀ x ∈ {clean_label}: f(x) → L")
        self.lbl_concept_desc.setText(
            f"Core Concept: Represents relational mathematical knowledge connections for '{clean_label}' "
            "across derivations, proofs, and saved notebook boards."
        )
        self.lbl_meta_questions.setText(f"Linked References:     {len(self.edge_items)} Edges")
        self.lbl_meta_theorems.setText(f"Connected Outbound:    {ntype.capitalize()} Node")
        self.lbl_meta_confidence.setText("Confidence Score:      99.8%")
        self.btn_open_board.setText(f"Open {label}")

    def _on_open_selected_board(self):
        if not self.selected_node_id:
            return
        node_item = self.node_items.get(self.selected_node_id)
        if node_item:
            meta = node_item.node_data.get("metadata", {})
            nb_id = meta.get("id") or self.selected_node_id.replace("doc_", "").replace("md_", "")
            self.open_notebook_requested.emit(nb_id)

    def _toggle_physics(self):
        self.physics_enabled = not self.physics_enabled
        if self.physics_enabled:
            self.btn_physics.setText("❚❚")
            self.timer.start(33)
        else:
            self.btn_physics.setText("▶")
            self.timer.stop()

    def _filter_graph(self, text: str):
        query = text.strip().lower()
        for node_id, node_item in self.node_items.items():
            label = node_item.node_data.get("label", "").lower()
            if not query or query in label:
                node_item.setOpacity(1.0)
            else:
                node_item.setOpacity(0.15)

    def _step_physics_simulation(self):
        if not self.physics_enabled or not self.node_items:
            return

        nodes = list(self.node_items.values())
        k_repulsion = 40000.0
        k_attraction = 0.04
        rest_length = 120.0

        for i in range(len(nodes)):
            n1 = nodes[i]
            p1 = n1.pos()
            for j in range(i + 1, len(nodes)):
                n2 = nodes[j]
                p2 = n2.pos()

                dx = p2.x() - p1.x()
                dy = p2.y() - p1.y()
                dist_sq = dx * dx + dy * dy + 0.01
                dist = math.sqrt(dist_sq)

                if dist < 400:
                    force = k_repulsion / dist_sq
                    fx = (dx / dist) * force
                    fy = (dy / dist) * force

                    n1.vx -= fx
                    n1.vy -= fy
                    n2.vx += fx
                    n2.vy += fy

        for edge in self.edge_items:
            n1 = edge.source_item
            n2 = edge.target_item
            p1 = n1.pos()
            p2 = n2.pos()

            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            dist = math.sqrt(dx * dx + dy * dy) + 0.01

            force = (dist - rest_length) * k_attraction
            fx = (dx / dist) * force
            fy = (dy / dist) * force

            n1.vx += fx
            n1.vy -= fy
            n2.vx -= fx
            n2.vy -= fy

        for n in nodes:
            if not n.isSelected():
                n.vx *= 0.85
                n.vy *= 0.85
                n.setPos(n.x() + n.vx, n.y() + n.vy)
