import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, QTimer
from ..theme_manager import ThemeManager
from ..kestrel_theme import MONO_FONT, ghost_button_qss, primary_button_qss
from app.workers.model_readiness_worker import ModelReadinessWorker
from shared.ai_client import ai_client

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Unified Model Readiness")
        self.resize(500, 450)
        c = ThemeManager.instance().get_colors()

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border_color']};
            }}
            QLabel {{
                color: {c['text_primary']};
                font-family: {MONO_FONT};
            }}
            QTableWidget {{
                background-color: {c['bg_card']};
                color: {c['text_primary']};
                border: 1px solid {c['border_color']};
                gridline-color: {c['border_color']};
                font-family: {MONO_FONT};
                font-size: 11px;
            }}
            QHeaderView::section {{
                background-color: {c['panel_card_bg']};
                color: {c['text_primary']};
                border: 1px solid {c['border_color']};
                font-weight: bold;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        
        title = QLabel(f"UNIFIED MODEL READINESS - Provider: {ai_client.config.provider} | Model: {ai_client.config.model_id}")
        title.setStyleSheet(f"font-size: 12px; font-weight: 800; letter-spacing: 1px; color: {c['text_primary']}; font-family: {MONO_FONT};")
        layout.addWidget(title)
        
        self.btn_run_tests = QPushButton("RUN READINESS TESTS")
        self.btn_run_tests.setStyleSheet(primary_button_qss(c))
        self.btn_run_tests.clicked.connect(self._run_tests)
        layout.addWidget(self.btn_run_tests)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Capability", "Status", "Latency"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)
        
        self.lbl_overall = QLabel("Overall: NOT RUN")
        self.lbl_overall.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {c['text_secondary']};")
        layout.addWidget(self.lbl_overall)

        layout.addStretch()

        btn_close = QPushButton("CLOSE")
        btn_close.setStyleSheet(ghost_button_qss(c))
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)

        self.worker = None

    def _run_tests(self):
        self.btn_run_tests.setEnabled(False)
        self.btn_run_tests.setText("RUNNING...")
        self.table.setRowCount(0)
        self.lbl_overall.setText("Overall: RUNNING")

        self.worker = ModelReadinessWorker(self)
        self.worker.finished.connect(self._on_tests_finished)
        self.worker.start()

    def _on_tests_finished(self, results):
        self.btn_run_tests.setEnabled(True)
        self.btn_run_tests.setText("RUN READINESS TESTS")
        
        tests = results.get("tests", {})
        self.table.setRowCount(len(tests))
        
        c = ThemeManager.instance().get_colors()
        
        row = 0
        for name, data in tests.items():
            item_name = QTableWidgetItem(name)
            
            passed = data.get("pass", False)
            status_text = "PASS" if passed else "FAIL"
            item_status = QTableWidgetItem(status_text)
            
            if passed:
                item_status.setForeground(Qt.GlobalColor.green)
            else:
                item_status.setForeground(Qt.GlobalColor.red)
                item_status.setToolTip(data.get("error", "Unknown error"))
                
            latency_text = f"{data.get('latency', 0):.2f}s"
            item_latency = QTableWidgetItem(latency_text)
            
            self.table.setItem(row, 0, item_name)
            self.table.setItem(row, 1, item_status)
            self.table.setItem(row, 2, item_latency)
            row += 1
            
        is_ready = results.get("overall_ready", False)
        if is_ready:
            self.lbl_overall.setText("Overall: READY")
            self.lbl_overall.setStyleSheet("font-size: 14px; font-weight: bold; color: #16a34a;")
            # Tell main window about readiness
            if hasattr(self.parent(), "ai_ready"):
                self.parent().ai_ready = True
        else:
            self.lbl_overall.setText("Overall: FAILED")
            self.lbl_overall.setStyleSheet("font-size: 14px; font-weight: bold; color: #ef4444;")
            if hasattr(self.parent(), "ai_ready"):
                self.parent().ai_ready = False
