"""
Obsidian-Style Interactive Knowledge Graph Visualizer Panel
Node-Edge physics force simulation visualizing document relationships, hashtags (#physics, #quantum),
and cross-references with dragging, hover highlighting, and live tag search filtering.
"""

import math
import random
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsLineItem,
    QGraphicsTextItem, QGraphicsItem, QFrame, QSlider, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QColor, QPen, QBrush, QFont, QPainter, QRadialGradient

from ...backend.tag_graph_parser import TagGraphParser

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

        # Color coding based on type
        ntype = node_data.get("type", "note")
        if ntype == "tag":
            self.base_color = QColor("#ff9500") # Amber Orange for Hashtags
        elif ntype == "board":
            self.base_color = QColor("#28a745") # Emerald Green for Notebook Canvas Boards
        else:
            self.base_color = QColor("#007aff") # Apple Blue for Markdown Notes

        self.setPen(QPen(self.base_color.darker(110), 2))
        self.setBrush(QBrush(self.base_color))

        # Title Label
        self.label_item = QGraphicsTextItem(node_data.get("label", ""), self)
        self.label_item.setDefaultTextColor(QColor("#1c1c1e"))
        font = QFont("Segoe UI", 9, QFont.Weight.Bold if ntype == "tag" else QFont.Weight.Normal)
        self.label_item.setFont(font)
        
        # Center label under circle
        rect = self.label_item.boundingRect()
        self.label_item.setPos(-rect.width() / 2, radius + 2)

    def hoverEnterEvent(self, event):
        self.setBrush(QBrush(self.base_color.lighter(130)))
        self.setScale(1.2)
        for edge in self.edges:
            edge.set_highlight(True)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setBrush(QBrush(self.base_color))
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

        self.normal_pen = QPen(QColor(140, 140, 145, 120), 1.5, Qt.PenStyle.SolidLine)
        self.highlight_pen = QPen(QColor("#007aff"), 2.5, Qt.PenStyle.SolidLine)
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

        self._init_ui()
        
        # Physics Force Simulation Timer (30 FPS)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._step_physics_simulation)
        self.timer.start(33)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header Bar Controls
        header = QHBoxLayout()
        lbl_title = QLabel("❖  Knowledge Graph", self)
        lbl_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #1c1c1e;")

        self.txt_search = QLineEdit(self)
        self.txt_search.setPlaceholderText("⌕ Search #tags or notes...")
        self.txt_search.setStyleSheet("border: 1px solid #d1d1d6; border-radius: 6px; padding: 6px 12px; font-size: 13px; background: #ffffff;")
        self.txt_search.textChanged.connect(self._filter_graph)

        self.btn_physics = QPushButton("❚❚ Pause Physics", self)
        self.btn_physics.setStyleSheet("background: #ffffff; border: 1px solid #d1d1d6; border-radius: 6px; padding: 6px 12px; font-weight: bold;")
        self.btn_physics.clicked.connect(self._toggle_physics)

        btn_refresh = QPushButton("⟳ Refresh Graph", self)
        btn_refresh.setStyleSheet("background: #007aff; color: white; border-radius: 6px; padding: 6px 14px; font-weight: bold;")
        btn_refresh.clicked.connect(self.load_graph)

        header.addWidget(lbl_title)
        header.addStretch()
        header.addWidget(self.txt_search)
        header.addWidget(self.btn_physics)
        header.addWidget(btn_refresh)
        main_layout.addLayout(header)

        # Interactive Graph Scene & View
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(-1000, -800, 2000, 1600)
        self.scene.setBackgroundBrush(QBrush(QColor("#f8f8fa")))

        self.view = QGraphicsView(self.scene, self)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setStyleSheet("QGraphicsView { border: 1px solid #d1d1d6; border-radius: 10px; background-color: #f8f8fa; }")

        main_layout.addWidget(self.view)

        # Initial Graph Load
        self.load_graph()

    def load_graph(self):
        self.scene.clear()
        self.node_items.clear()
        self.edge_items.clear()

        graph_data = self.parser.build_knowledge_graph()
        nodes = graph_data["nodes"]
        edges = graph_data["edges"]

        # 1. Create Node Items
        num_nodes = len(nodes)
        radius_span = max(180, num_nodes * 25)

        for idx, n in enumerate(nodes):
            r = 14.0 if n["type"] == "board" else (11.0 if n["type"] == "note" else 10.0)
            node_item = GraphNodeItem(n, radius=r)
            
            # Initial circular layout placement
            angle = (2 * math.pi / max(1, num_nodes)) * idx
            dist = random.uniform(80, radius_span)
            x = dist * math.cos(angle)
            y = dist * math.sin(angle)
            node_item.setPos(x, y)

            self.scene.addItem(node_item)
            self.node_items[n["id"]] = node_item

        # 2. Create Edge Items
        for e in edges:
            src_item = self.node_items.get(e["source"])
            tgt_item = self.node_items.get(e["target"])
            if src_item and tgt_item:
                edge_item = GraphEdgeItem(src_item, tgt_item)
                self.scene.addItem(edge_item)
                self.edge_items.append(edge_item)

    def _toggle_physics(self):
        self.physics_enabled = not self.physics_enabled
        if self.physics_enabled:
            self.btn_physics.setText("❚❚ Pause Physics")
            self.timer.start(33)
        else:
            self.btn_physics.setText("▶ Play Physics")
            self.timer.stop()

    def _filter_graph(self, text: str):
        query = text.strip().lower()
        for node_id, node_item in self.node_items.items():
            label = node_item.node_data.get("label", "").lower()
            if not query or query in label:
                node_item.setOpacity(1.0)
            else:
                node_item.setOpacity(0.2)

    def _step_physics_simulation(self):
        if not self.physics_enabled or not self.node_items:
            return

        nodes = list(self.node_items.values())
        k_repulsion = 40000.0
        k_attraction = 0.04
        rest_length = 120.0

        # 1. Repulsion force between all node pairs
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

        # 2. Attraction force along edges
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
            n1.vy += fy
            n2.vx -= fx
            n2.vy -= fy

        # 3. Apply velocity & damping
        for n in nodes:
            if not n.isSelected():
                n.vx *= 0.85
                n.vy *= 0.85
                n.setPos(n.x() + n.vx, n.y() + n.vy)
