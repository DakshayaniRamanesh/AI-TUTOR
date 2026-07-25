"""
TableItem Canvas Item (QTableWidget proxy item with HeaderDragBar for 100% smooth canvas movement)
"""

from PyQt6.QtWidgets import (
    QGraphicsProxyWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from .base_item import BaseGraphicsItemMixin

class HeaderDragBar(QWidget):
    """
    Header drag handle allowing 100% smooth mouse dragging of proxy items.
    """
    def __init__(self, proxy_getter, parent=None):
        super().__init__(parent)
        self.proxy_getter = proxy_getter
        self._drag_start = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.globalPosition()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start:
            proxy = self.proxy_getter()
            if proxy:
                delta = event.globalPosition() - self._drag_start
                self._drag_start = event.globalPosition()
                proxy.setPos(proxy.pos() + delta)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_start = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        event.accept()

class TableWidgetContainer(QWidget):
    delete_requested = pyqtSignal()

    def __init__(self, headers=None, rows=None, proxy_getter=None, parent=None):
        super().__init__(parent)
        self.resize(440, 240)
        self.setStyleSheet("""
            QWidget#TableContainer {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 10px;
            }
            QTableWidget {
                border: none;
                gridline-color: #e5e5ea;
                font-size: 13px;
            }
            QPushButton {
                background-color: #f2f2f7;
                border: 1px solid #d1d1d6;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #e5e5ea;
            }
        """)

        self.setObjectName("TableContainer")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(4)

        # Header Drag Bar
        self.header_bar = HeaderDragBar(proxy_getter, self)
        tb_layout = QHBoxLayout(self.header_bar)
        tb_layout.setContentsMargins(0, 0, 0, 0)
        tb_layout.setSpacing(4)

        lbl_drag = QLabel("▤ Table", self.header_bar)
        lbl_drag.setStyleSheet("font-size: 12px; font-weight: bold; color: #388e3c; background: transparent;")
        tb_layout.addWidget(lbl_drag)

        btn_add_row = QPushButton("+ Row", self.header_bar)
        btn_add_row.clicked.connect(self._add_row)
        
        btn_rem_row = QPushButton("- Row", self.header_bar)
        btn_rem_row.clicked.connect(self._rem_row)
        
        btn_add_col = QPushButton("+ Col", self.header_bar)
        btn_add_col.clicked.connect(self._add_col)
        
        btn_rem_col = QPushButton("- Col", self.header_bar)
        btn_rem_col.clicked.connect(self._rem_col)

        btn_del = QPushButton("✕", self.header_bar)
        btn_del.setFixedSize(20, 20)
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #8e8e93;
                border: none;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                color: #d32f2f;
                background-color: #ffebee;
                border-radius: 10px;
            }
        """)
        btn_del.clicked.connect(self.delete_requested.emit)

        tb_layout.addWidget(btn_add_row)
        tb_layout.addWidget(btn_rem_row)
        tb_layout.addWidget(btn_add_col)
        tb_layout.addWidget(btn_rem_col)
        tb_layout.addStretch()
        tb_layout.addWidget(btn_del)

        layout.addWidget(self.header_bar)

        # Table
        num_cols = len(headers) if headers else 3
        num_rows = len(rows) if rows else 3
        
        self.table = QTableWidget(num_rows, num_cols, self)
        if headers:
            self.table.setHorizontalHeaderLabels(headers)
        else:
            self.table.setHorizontalHeaderLabels([f"Col {i+1}" for i in range(num_cols)])
            
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        if rows:
            for r, row_data in enumerate(rows):
                for c, val in enumerate(row_data):
                    if c < num_cols:
                        self.table.setItem(r, c, QTableWidgetItem(str(val)))
        else:
            for r in range(num_rows):
                for c in range(num_cols):
                    self.table.setItem(r, c, QTableWidgetItem(f"Data {r+1},{c+1}"))

        layout.addWidget(self.table)

    def _add_row(self):
        self.table.insertRow(self.table.rowCount())

    def _rem_row(self):
        if self.table.rowCount() > 1:
            self.table.removeRow(self.table.rowCount() - 1)

    def _add_col(self):
        c = self.table.columnCount()
        self.table.insertColumn(c)
        self.table.setHorizontalHeaderItem(c, QTableWidgetItem(f"Col {c+1}"))

    def _rem_col(self):
        if self.table.columnCount() > 1:
            self.table.removeColumn(self.table.columnCount() - 1)

class TableItem(QGraphicsProxyWidget, BaseGraphicsItemMixin):
    def __init__(self, headers=None, rows=None, parent=None):
        super().__init__(parent)
        self.setup_base_properties()
        self.setZValue(5)
        
        self.container = TableWidgetContainer(headers, rows, proxy_getter=lambda: self)
        self.container.delete_requested.connect(self._delete_self)
        self.setWidget(self.container)

    def _delete_self(self):
        scene = self.scene()
        if scene:
            scene.removeItem(self)

    def contextMenuEvent(self, event):
        self.build_context_menu(event.screenPos())

    def to_dict(self) -> dict:
        tbl = self.container.table
        headers = [tbl.horizontalHeaderItem(c).text() if tbl.horizontalHeaderItem(c) else f"Col {c+1}" for c in range(tbl.columnCount())]
        rows = []
        for r in range(tbl.rowCount()):
            row_data = []
            for c in range(tbl.columnCount()):
                it = tbl.item(r, c)
                row_data.append(it.text() if it else "")
            rows.append(row_data)

        return {
            "type": "TableItem",
            "x": self.x(),
            "y": self.y(),
            "headers": headers,
            "rows": rows,
            "z_value": self.zValue()
        }
