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

