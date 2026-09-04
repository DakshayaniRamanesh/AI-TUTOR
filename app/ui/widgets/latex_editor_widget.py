"""
Interactive LaTeX Editor & Live PDF-Level Preview Widget for Kestrel AI Notebook
Allows real-time viewing, manual editing, live syntax-free PDF page preview, and on-demand PDF compilation.
"""

import os
import base64
import requests
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QTextBrowser, QSplitter, QFileDialog, QMessageBox,
    QApplication, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ...backend.math_engine.latex_formatter import format_math_to_html
from ..theme_manager import ThemeManager

class LatexEditorWidget(QWidget):
    export_pdf_requested = pyqtSignal(str) # Emits current latex_code
    close_requested = pyqtSignal()
    pdf_compiled = pyqtSignal(str) # Emits compiled pdf_file_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc_title = "LaTeX Document"
        self.is_dirty = False
        self._initial_code = ""

        self.theme_mgr = ThemeManager.instance()
        self.theme_mgr.theme_changed.connect(self._apply_theme)
        
        self._init_ui()
        self._apply_theme(self.theme_mgr.current_theme)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Header Bar (Compact single line bar)
        self.header = QFrame(self)
        self.header.setObjectName("LatexEditorHeader")
        self.header.setFixedHeight(42)
        h_layout = QHBoxLayout(self.header)
        h_layout.setContentsMargins(10, 4, 10, 4)
        h_layout.setSpacing(10)

        lbl_icon = QLabel("📝", self.header)
        lbl_icon.setFont(QFont("-apple-system", 13))

        self.lbl_title = QLabel("LaTeX Document Editor & Preview", self.header)
        self.lbl_title.setFont(QFont("-apple-system", 12, QFont.Weight.Bold))

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
        self.btn_close.clicked.connect(self._on_close_clicked)

        h_layout.addWidget(self.btn_copy)
        h_layout.addWidget(self.btn_refresh)
        h_layout.addWidget(self.btn_export)
        h_layout.addWidget(self.btn_close)

        layout.addWidget(self.header)

        # Splitter (Editor vs PDF-Page Live Preview)
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

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

        # Right: PDF-Styled Page Preview (Pure Black & White)
        right_container = QWidget(self.splitter)
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        lbl_preview = QLabel("PDF Page Live Preview (Pure Black & White):", right_container)
        lbl_preview.setFont(QFont("-apple-system", 11, QFont.Weight.Bold))

        self.preview_browser = QTextBrowser(right_container)
        self.preview_browser.setOpenExternalLinks(True)

        right_layout.addWidget(lbl_preview)
        right_layout.addWidget(self.preview_browser)

        self.splitter.addWidget(left_container)
        self.splitter.addWidget(right_container)
        self.splitter.setSizes([480, 520])

        layout.addWidget(self.splitter, stretch=1)

        # Debounce timer for preview update while typing
        from PyQt6.QtCore import QTimer
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(300)
        self._update_timer.timeout.connect(self.update_preview)

    def set_latex_code(self, code: str, title: str = "LaTeX Document"):
        self.doc_title = title
        self.lbl_title.setText(f"📝 {title}")
        self._initial_code = code
        self.is_dirty = False
        self.editor.setPlainText(code)
        self.update_preview()

    def get_latex_code(self) -> str:
        return self.editor.toPlainText()

    def _on_text_changed_debounced(self):
        if self.editor.toPlainText() != self._initial_code:
            self.is_dirty = True
        self._update_timer.start()

    def update_preview(self):
        code = self.editor.toPlainText()
        if not code.strip():
            self.preview_browser.setHtml("<p style='color:#666; font-style:italic; padding: 20px;'>No LaTeX code provided.</p>")
            return

        formatted_body = format_math_to_html(code)

        is_dark = self.theme_mgr.is_dark()
        page_bg = "#ffffff" if not is_dark else "#1c1c1e"
        outer_bg = "#f4f4f6" if not is_dark else "#111113"
        text_col = "#111111" if not is_dark else "#e8e8ed"
        border_col = "transparent"

        html_doc = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    background-color: {outer_bg};
                    margin: 0;
                    padding: 24px 12px;
                    display: flex;
                    justify-content: center;
                    font-family: 'Latin Modern Roman', 'Computer Modern Roman', 'CMU Serif', 'Times New Roman', 'Nimbus Roman', 'Times', serif;
                    -webkit-font-smoothing: antialiased;
                }}
                .pdf-page {{
                    background-color: {page_bg};
                    color: {text_col};
                    width: 90%;
                    max-width: 720px;
                    min-height: 960px;
                    margin: 0 auto;
                    padding: 50px 65px;
                    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
                    border: none;
                    box-sizing: border-box;
                    font-size: 15px;
                    line-height: 1.45;
                }}
                .pdf-sec-head {{
                    font-size: 19px;
                    font-weight: bold;
                    color: {text_col};
                    margin-top: 22px;
                    margin-bottom: 8px;
                    font-family: 'Latin Modern Roman', 'Computer Modern Roman', 'CMU Serif', 'Times New Roman', serif;
                }}
                .pdf-subsec-head {{
                    font-size: 16px;
                    font-weight: bold;
                    color: {text_col};
                    margin-top: 16px;
                    margin-bottom: 6px;
                    font-family: 'Latin Modern Roman', 'Computer Modern Roman', 'CMU Serif', 'Times New Roman', serif;
                }}
                .pdf-display-math {{
                    font-size: 17px;
                    text-align: center;
                    margin: 14px 0;
                    padding: 0;
                    background: transparent;
                    border: none;
                    color: {text_col};
                }}
                .pdf-inline-math {{
                    font-size: 15px;
                    font-weight: 600;
                    color: {text_col};
                    padding: 0 1px;
                }}
                .math-frac {{
                    display: inline-block;
                    vertical-align: middle;
                    text-align: center;
                    font-size: 0.95em;
                    padding: 0 2px;
                }}
                .math-num {{
                    display: block;
                    border-bottom: 1px solid currentColor;
                    padding: 0 2px;
                }}
                .math-den {{
                    display: block;
                    padding: 0 2px;
                }}
                table {{
                    font-family: inherit;
                }}
            </style>
        </head>
        <body>
            <div class="pdf-page">
                {formatted_body}
            </div>
        </body>
        </html>
        """
        self.preview_browser.setHtml(html_doc)

    def _copy_to_clipboard(self):
        QApplication.clipboard().setText(self.editor.toPlainText())
        self.btn_copy.setText("✓ Copied!")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: self.btn_copy.setText("📋 Copy Code"))

    def confirm_close(self) -> bool:
        if not self.is_dirty and not self.editor.toPlainText().strip():
            return True

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Close LaTeX Document?")
        msg_box.setText("You have an active LaTeX document workspace.")
        msg_box.setInformativeText("Would you like to export the latest edited LaTeX as a PDF before closing, or discard it?")
        
        btn_export = msg_box.addButton("📥 Export as PDF", QMessageBox.ButtonRole.AcceptRole)
        btn_discard = msg_box.addButton("🗑️ Discard Changes", QMessageBox.ButtonRole.DestructiveRole)
        btn_cancel = msg_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(btn_export)

        msg_box.exec()

        clicked = msg_box.clickedButton()
        if clicked == btn_export:
            return self._export_pdf()
        elif clicked == btn_discard:
            self.is_dirty = False
            return True
        else:
            return False

    def _on_close_clicked(self):
        if self.confirm_close():
            self.close_requested.emit()

    def _export_pdf(self) -> bool:
        # ALWAYS fetch the latest edited LaTeX code string from the code editor
        code = self.editor.toPlainText().strip()
        if not code:
            QMessageBox.warning(self, "Empty LaTeX", "Cannot compile empty LaTeX source.")
            return False

        default_filename = f"{self.doc_title.replace(' ', '_')}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Compiled PDF", default_filename, "PDF Documents (*.pdf)"
        )
        if not file_path:
            return False

        self.btn_export.setText("Compiling PDF...")
        self.btn_export.setEnabled(False)
        QApplication.processEvents()

        try:
            from ...backend.math_engine.latex_client import compile_custom_latex_pdf
            # Compiles the current (edited/non-edited) LaTeX code from the editor
            success, msg_or_path = compile_custom_latex_pdf(code, file_path)
            if success:
                self.is_dirty = False
                self.pdf_compiled.emit(file_path)
                QMessageBox.information(
                    self, "PDF Exported",
                    f"LaTeX compiled and saved successfully to:\n{file_path}"
                )
                return True
            else:
                QMessageBox.warning(self, "Compilation Error", f"LaTeX compilation failed:\n{msg_or_path}")
                return False
        except Exception as e:
            QMessageBox.warning(self, "Export Error", f"Failed to compile PDF:\n{e}")
            return False
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
                border-radius: 6px;
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
                padding: 4px 10px;
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
