"""
Reference Data Drawer Panel (Physical Constants, Log Tables, Math Formulas)
"""

import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLineEdit,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QHeaderView
)
from PyQt6.QtCore import pyqtSignal
from ...data.constants import PHYSICAL_CONSTANTS
from ...data.math_tables import TRIG_VALUES, DERIVATIVE_FORMULAS, INTEGRAL_FORMULAS

class ReferencePanel(QWidget):
    insert_data_requested = pyqtSignal(dict) # payload: {"title": str, "headers": list, "rows": list}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reference Tables & Constants")
        self.resize(500, 600)
        self.setStyleSheet("""
            QWidget {
                background-color: #f2f2f7;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #d1d1d6;
                background: white;
                border-radius: 8px;
            }
            QTabBar::tab {
                background: #e5e5ea;
                border: 1px solid #d1d1d6;
                padding: 6px 14px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom: 2px solid #007aff;
                font-weight: bold;
            }
            QTableWidget {
                border: none;
                gridline-color: #e5e5ea;
            }
            QHeaderView::section {
                background-color: #f2f2f7;
                font-weight: bold;
                border: none;
                padding: 4px;
            }
            QPushButton {
                background-color: #007aff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # Header
        header_layout = QHBoxLayout()
        title_lbl = QLabel("Reference Database")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #1c1c1e;")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Search bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search constants or formulas...")
        self.search_input.setStyleSheet("padding: 6px; border: 1px solid #c7c7cc; border-radius: 6px; background: white;")
        self.search_input.textChanged.connect(self._filter_tables)
        layout.addWidget(self.search_input)

        # Tab widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Tab 1: Physical Constants
        self.tab_const = QWidget()
        tc_layout = QVBoxLayout(self.tab_const)
        self.table_const = QTableWidget(len(PHYSICAL_CONSTANTS), 4)
        self.table_const.setHorizontalHeaderLabels(["Name", "Symbol", "Value", "Unit"])
        self.table_const.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for r, item in enumerate(PHYSICAL_CONSTANTS):
            self.table_const.setItem(r, 0, QTableWidgetItem(item["name"]))
            self.table_const.setItem(r, 1, QTableWidgetItem(item["symbol"]))
            self.table_const.setItem(r, 2, QTableWidgetItem(str(item["value"])))
            self.table_const.setItem(r, 3, QTableWidgetItem(item["unit"]))
        tc_layout.addWidget(self.table_const)
        
        btn_inst_const = QPushButton("Insert Constants Table onto Canvas")
        btn_inst_const.clicked.connect(self._insert_constants)
        tc_layout.addWidget(btn_inst_const)
        self.tabs.addTab(self.tab_const, "Constants")

        # Tab 2: Derivatives & Integrals
        self.tab_math = QWidget()
        tm_layout = QVBoxLayout(self.tab_math)
        self.table_math = QTableWidget(len(DERIVATIVE_FORMULAS) + len(INTEGRAL_FORMULAS), 2)
        self.table_math.setHorizontalHeaderLabels(["Function / Integrand", "Derivative / Integral"])
        self.table_math.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        row_idx = 0
        for item in DERIVATIVE_FORMULAS:
            self.table_math.setItem(row_idx, 0, QTableWidgetItem(f"d/dx ({item['function']})"))
            self.table_math.setItem(row_idx, 1, QTableWidgetItem(item["derivative"]))
            row_idx += 1
        for item in INTEGRAL_FORMULAS:
            self.table_math.setItem(row_idx, 0, QTableWidgetItem(f"∫ {item['integrand']} dx"))
            self.table_math.setItem(row_idx, 1, QTableWidgetItem(item["integral"]))
            row_idx += 1
        tm_layout.addWidget(self.table_math)
        
        btn_inst_math = QPushButton("Insert Math Formulas onto Canvas")
        btn_inst_math.clicked.connect(self._insert_math)
        tm_layout.addWidget(btn_inst_math)
        self.tabs.addTab(self.tab_math, "Calculus Formulas")

        # Tab 3: Trig Values
        self.tab_trig = QWidget()
        tr_layout = QVBoxLayout(self.tab_trig)
        self.table_trig = QTableWidget(len(TRIG_VALUES), 5)
        self.table_trig.setHorizontalHeaderLabels(["Deg", "Rad", "sin", "cos", "tan"])
        self.table_trig.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for r, item in enumerate(TRIG_VALUES):
            self.table_trig.setItem(r, 0, QTableWidgetItem(item["angle_deg"]))
            self.table_trig.setItem(r, 1, QTableWidgetItem(item["angle_rad"]))
            self.table_trig.setItem(r, 2, QTableWidgetItem(item["sin"]))
            self.table_trig.setItem(r, 3, QTableWidgetItem(item["cos"]))
            self.table_trig.setItem(r, 4, QTableWidgetItem(item["tan"]))
        tr_layout.addWidget(self.table_trig)
        
        btn_inst_trig = QPushButton("Insert Trig Table onto Canvas")
        btn_inst_trig.clicked.connect(self._insert_trig)
        tr_layout.addWidget(btn_inst_trig)
        self.tabs.addTab(self.tab_trig, "Trig Table")

    def _filter_tables(self, text: str):
        query = text.lower()
        for tbl in [self.table_const, self.table_math, self.table_trig]:
            for r in range(tbl.rowCount()):
                show = False
                for c in range(tbl.columnCount()):
                    it = tbl.item(r, c)
                    if it and query in it.text().lower():
                        show = True
                        break
                tbl.setRowHidden(r, not show)

    def _insert_constants(self):
        rows = [[c["name"], c["symbol"], str(c["value"]), c["unit"]] for c in PHYSICAL_CONSTANTS[:8]]
        self.insert_data_requested.emit({
            "title": "Physical Constants",
            "headers": ["Name", "Symbol", "Value", "Unit"],
            "rows": rows
        })

    def _insert_math(self):
        rows = [[f"d/dx ({f['function']})", f['derivative']] for f in DERIVATIVE_FORMULAS[:8]]
        self.insert_data_requested.emit({
            "title": "Calculus Derivatives Sheet",
            "headers": ["Function", "Derivative"],
            "rows": rows
        })

    def _insert_trig(self):
        rows = [[t["angle_deg"], t["angle_rad"], t["sin"], t["cos"], t["tan"]] for t in TRIG_VALUES]
        self.insert_data_requested.emit({
            "title": "Trigonometric Exact Values",
            "headers": ["Deg", "Rad", "sin", "cos", "tan"],
            "rows": rows
        })
