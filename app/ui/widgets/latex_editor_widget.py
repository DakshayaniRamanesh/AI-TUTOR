"""
Interactive LaTeX Editor & Live Preview Widget for Kestrel AI Notebook
Allows real-time viewing, manual editing, live math preview, and on-demand PDF compilation.
"""

import os
import base64
import requests
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QTextBrowser, QSplitter, QFileDialog, QMessageBox,
    QApplication, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence

from ...backend.math_engine.latex_formatter import format_math_to_html
from ..theme_manager import ThemeManager

class LatexEditorWidget(QWidget):
    export_pdf_requested = pyqtSignal(str) # Emits current latex_code
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc_title = "LaTeX Document"
        self.theme_mgr = ThemeManager.instance()
        self.theme_mgr.theme_changed.connect(self._apply_theme)
        
        self._init_ui()
        self._apply_theme(self.theme_mgr.current_theme)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header Bar
        self.header = QFrame(self)
        self.header.setObjectName("LatexEditorHeader")
        h_layout = QHBoxLayout(self.header)
        h_layout.setContentsMargins(8, 4, 8, 4)
        h_layout.setSpacing(10)

        lbl_icon = QLabel("📝", self.header)
        lbl_icon.setFont(QFont("-apple-system", 14))

        self.lbl_title = QLabel("LaTeX Document Editor & Preview", self.header)
        self.lbl_title.setFont(QFont("-apple-system", 13, QFont.Weight.Bold))

        h_layout.addWidget(lbl_icon)
        h_layout.addWidget(self.lbl_title)
        h_layout.addStretch()

        # Action Buttons
        self.btn_copy = QPushButton("📋 Copy Code", self.header)
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.clicked.connect(self._copy_to_clipboard)

        self.btn_refresh = QPushButton("🔄 Refresh Preview", self.header)
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.update_preview)

        self.btn_export = QPushButton("📥 Export as PDF", self.header)
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.clicked.connect(self._export_pdf)

        self.btn_close = QPushButton("✕ Close", self.header)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(lambda: self.close_requested.emit())

        h_layout.addWidget(self.btn_copy)
        h_layout.addWidget(self.btn_refresh)
        h_layout.addWidget(self.btn_export)
        h_layout.addWidget(self.btn_close)

        layout.addWidget(self.header)

        # Splitter (Editor vs Live Preview)
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Left: Monospace Code Editor
        left_container = QWidget(self.splitter)
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        lbl_editor = QLabel("LaTeX Source Code (Editable):", left_container)
        lbl_editor.setFont(QFont("-apple-system", 11, QFont.Weight.Bold))

        self.editor = QPlainTextEdit(left_container)
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.editor.setFont(font)
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.editor.textChanged.connect(self._on_text_changed_debounced)

        left_layout.addWidget(lbl_editor)
        left_layout.addWidget(self.editor)

        # Right: Rich Math Preview
        right_container = QWidget(self.splitter)
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        lbl_preview = QLabel("Live Math & Document Preview:", right_container)
        lbl_preview.setFont(QFont("-apple-system", 11, QFont.Weight.Bold))

        self.preview_browser = QTextBrowser(right_container)
        self.preview_browser.setOpenExternalLinks(True)

        right_layout.addWidget(lbl_preview)
        right_layout.addWidget(self.preview_browser)

        self.splitter.addWidget(left_container)
        self.splitter.addWidget(right_container)
        self.splitter.setSizes([500, 500])

        layout.addWidget(self.splitter)

        # Debounce timer for preview update while typing
        from PyQt6.QtCore import QTimer
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(400) # Update 400ms after user pauses typing
        self._update_timer.timeout.connect(self.update_preview)

    def set_latex_code(self, code: str, title: str = "LaTeX Document"):
        self.doc_title = title
        self.lbl_title.setText(f"📝 {title}")
        self.editor.setPlainText(code)
        self.update_preview()

    def get_latex_code(self) -> str:
        return self.editor.toPlainText()

    def _on_text_changed_debounced(self):
        self._update_timer.start()

    def update_preview(self):
        code = self.editor.toPlainText()
        if not code.strip():
            self.preview_browser.setHtml("<p style='color:#888; font-style:italic;'>No LaTeX code provided.</p>")
            return

        formatted_html = format_math_to_html(code)
        c = self.theme_mgr.get_colors()

        html_doc = f"""
        <html>
        <head>
            <style>
                body {{
                    background-color: {c['editor_bg']};
                    color: {c['text_primary']};
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    padding: 16px;
                    line-height: 1.6;
                }}
                h1, h2, h3 {{ color: {c['accent']}; }}
                .math-block {{
                    background: {c['bg_card']};
                    border-left: 3px solid {c['accent']};
                    padding: 10px 14px;
                    margin: 12px 0;
                    border-radius: 4px;
                }}
                .equation {{ font-size: 15px; font-weight: bold; }}
            </style>
        </head>
        <body>
            {formatted_html}
        </body>
        </html>
        """
        self.preview_browser.setHtml(html_doc)

    def _copy_to_clipboard(self):
        QApplication.clipboard().setText(self.editor.toPlainText())
        self.btn_copy.setText("✓ Copied!")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: self.btn_copy.setText("📋 Copy Code"))

    def _export_pdf(self):
        code = self.editor.toPlainText().strip()
        if not code:
            QMessageBox.warning(self, "Empty LaTeX", "Cannot compile empty LaTeX source.")
            return

        # Prompt save location
        default_filename = f"{self.doc_title.replace(' ', '_')}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Compiled PDF", default_filename, "PDF Documents (*.pdf)"
        )
        if not file_path:
            return

        self.btn_export.setText("Compiling PDF...")
        self.btn_export.setEnabled(False)
        QApplication.processEvents()

        try:
            from ...backend.math_engine.latex_client import compile_custom_latex_pdf
            success, msg_or_path = compile_custom_latex_pdf(code, file_path)
            if success:
                QMessageBox.information(
                    self, "PDF Exported",
                    f"LaTeX compiled and saved successfully to:\n{file_path}"
                )
            else:
                QMessageBox.warning(self, "Compilation Error", f"LaTeX compilation failed:\n{msg_or_path}")
        except Exception as e:
            QMessageBox.warning(self, "Export Error", f"Failed to compile PDF:\n{e}")
        finally:
            self.btn_export.setText("📥 Export as PDF")
            self.btn_export.setEnabled(True)

    def _apply_theme(self, theme_name: str = "light"):
        c = self.theme_mgr.get_colors()

        self.setStyleSheet(f"""
            LatexEditorWidget {{
                background-color: {c['bg_card']};
            }}
            QFrame#LatexEditorHeader {{
                background-color: {c['bg_titlebar']};
                border-bottom: 1px solid {c['border_color']};
                border-radius: 8px;
            }}
            QLabel {{
                color: {c['text_primary']};
            }}
            QPlainTextEdit {{
                background-color: {c['editor_bg']};
                color: {c['text_primary']};
                border: 1px solid {c['border_color']};
                border-radius: 6px;
                padding: 8px;
            }}
            QTextBrowser {{
                background-color: {c['editor_bg']};
                color: {c['text_primary']};
                border: 1px solid {c['border_color']};
                border-radius: 6px;
                padding: 8px;
            }}
            QPushButton {{
                background-color: {c['bg_card']};
                color: {c['text_primary']};
                border: 1px solid {c['border_color']};
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {c['accent']};
                color: #ffffff;
            }}
            QSplitter::handle {{
                background-color: {c['border_color']};
            }}
        """)
        self.update_preview()
