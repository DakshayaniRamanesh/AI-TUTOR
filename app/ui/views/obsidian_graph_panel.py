from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import pyqtSignal
from app.ui.components.graph_canvas import GraphCanvas
from app.services.knowledge.graph_layout_service import save_node_layout_async
from app.services.knowledge.graph_query_service import GraphQueryService

class ObsidianGraphPanel(QWidget):
    open_notebook_requested = pyqtSignal(str)  # notebook_id

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = GraphCanvas(self)
        # GraphCanvas emits node_selected, which we could use to navigate if needed
        # self.canvas.node_selected.connect(...)
        layout.addWidget(self.canvas)
        
    def load_graph(self):
        snapshot = GraphQueryService().get_global_snapshot()
        self.canvas.set_snapshot(snapshot)
