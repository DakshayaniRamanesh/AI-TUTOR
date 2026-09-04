"""
Interactive Split-Screen LaTeX Editor & Native Vector PDF Viewer for Kestrel AI Notebook
Provides simultaneous LaTeX source editing on the left and pixel-perfect compiled vector PDF
rendering (using QPdfView) on the right, with on-demand background recompilation and export.
"""

import os
import shutil
import tempfile
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QSplitter, QFileDialog, QMessageBox,
    QApplication, QFrame, QSizePolicy, QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QPointF
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtPdfWidgets import QPdfView

from ..theme_manager import ThemeManager


class LatexRecompileWorker(QThread):
    """Background worker that compiles LaTeX code to a PDF using Tectonic."""
    compilation_finished = pyqtSignal(bool, str) # success, output_path_or_error

    def __init__(self, latex_code: str, target_pdf_path: str, parent=None):
        super().__init__(parent)
        self.latex_code = latex_code
        self.target_pdf_path = target_pdf_path

    def run(self):
        try:
            from ...backend.math_engine.latex_client import compile_custom_latex_pdf
            success, msg_or_path = compile_custom_latex_pdf(self.latex_code, self.target_pdf_path)
            self.compilation_finished.emit(success, msg_or_path)
        except Exception as e:
            self.compilation_finished.emit(False, str(e))


class LatexEditorWidget(QWidget):
    close_requested = pyqtSignal()
    pdf_compiled = pyqtSignal(str) # Emits compiled pdf_file_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc_title = "LaTeX Document"
        self.is_dirty = False
        self._initial_code = ""
        self.pdf_file_path = ""
        self.current_page = 1
        self.total_pages = 1
        self._recompile_worker = None

        self.theme_mgr = ThemeManager.instance()
        self.theme_mgr.theme_changed.connect(self._apply_theme)
        
        self._init_ui()
        self._apply_theme(self.theme_mgr.current_theme)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # 1. Top Header Bar
        self.header = QFrame(self)
        self.header.setObjectName("LatexEditorHeader")
        self.header.setFixedHeight(44)
        h_layout = QHBoxLayout(self.header)
        h_layout.setContentsMargins(12, 4, 12, 4)
        h_layout.setSpacing(10)

        lbl_icon = QLabel("📝", self.header)
        lbl_icon.setFont(QFont("-apple-system", 14))

        self.lbl_title = QLabel("LaTeX Document & Compiled PDF", self.header)
        self.lbl_title.setFont(QFont("-apple-system", 12, QFont.Weight.Bold))

        h_layout.addWidget(lbl_icon)
        h_layout.addWidget(self.lbl_title)
        h_layout.addStretch()

        # Action Buttons
        self.btn_copy = QPushButton("📋 Copy Code", self.header)
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.clicked.connect(self._copy_to_clipboard)

        self.btn_recompile = QPushButton("🔄 Recompile Preview", self.header)
        self.btn_recompile.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_recompile.setStyleSheet("font-weight: 700; color: #7c3aed;")
        self.btn_recompile.clicked.connect(self.recompile_preview)

        self.btn_export = QPushButton("📥 Export as PDF", self.header)
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.clicked.connect(self._export_pdf)

        self.btn_close = QPushButton("✕ Close", self.header)
        self.btn_close.setObjectName("BtnCloseLatex")
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self._on_close_clicked)

        h_layout.addWidget(self.btn_copy)
        h_layout.addWidget(self.btn_recompile)
        h_layout.addWidget(self.btn_export)
        h_layout.addWidget(self.btn_close)

        layout.addWidget(self.header)

        # 2. Main Horizontal Splitter (Left: Code Editor | Right: Native Vector PDF Viewer)
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # ---- Left Panel: Monospace Code Editor ----
        left_container = QWidget(self.splitter)
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        left_header_frame = QFrame(left_container)
        left_header_layout = QHBoxLayout(left_header_frame)
        left_header_layout.setContentsMargins(4, 2, 4, 2)
        lbl_editor = QLabel("LaTeX Source Code (Editable):", left_header_frame)
        lbl_editor.setFont(QFont("-apple-system", 11, QFont.Weight.Bold))
        left_header_layout.addWidget(lbl_editor)
        left_header_layout.addStretch()

        self.editor = QPlainTextEdit(left_container)
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.editor.setFont(font)
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.editor.textChanged.connect(self._on_text_changed)

        left_layout.addWidget(left_header_frame)
        left_layout.addWidget(self.editor)

        # ---- Right Panel: Native QPdfView Vector PDF Viewer ----
        right_container = QWidget(self.splitter)
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        # PDF Navigation Bar
        self.pdf_nav_bar = QFrame(right_container)
        self.pdf_nav_bar.setObjectName("PdfNavBar")
        self.pdf_nav_bar.setFixedHeight(36)
        pdf_nav_layout = QHBoxLayout(self.pdf_nav_bar)
        pdf_nav_layout.setContentsMargins(6, 2, 6, 2)
        pdf_nav_layout.setSpacing(8)

        lbl_preview = QLabel("📄 Vector PDF Preview:", self.pdf_nav_bar)
        lbl_preview.setFont(QFont("-apple-system", 11, QFont.Weight.Bold))

        self.btn_prev = QPushButton("◀ Prev", self.pdf_nav_bar)
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.clicked.connect(self._prev_page)

        self.lbl_page = QLabel("Page 1 of 1", self.pdf_nav_bar)
        self.lbl_page.setStyleSheet("font-size: 11px; font-weight: 600; color: #8e8e93;")

        self.btn_next = QPushButton("Next ▶", self.pdf_nav_bar)
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.clicked.connect(self._next_page)

        self.btn_zoom_in = QPushButton("🔍+", self.pdf_nav_bar)
        self.btn_zoom_in.setToolTip("Zoom In")
        self.btn_zoom_in.clicked.connect(self._zoom_in)

        self.btn_zoom_out = QPushButton("🔍-", self.pdf_nav_bar)
        self.btn_zoom_out.setToolTip("Zoom Out")
        self.btn_zoom_out.clicked.connect(self._zoom_out)

        self.btn_fit_width = QPushButton("↔ Fit Width", self.pdf_nav_bar)
        self.btn_fit_width.clicked.connect(self._fit_width)

        pdf_nav_layout.addWidget(lbl_preview)
        pdf_nav_layout.addStretch()
        pdf_nav_layout.addWidget(self.btn_prev)
        pdf_nav_layout.addWidget(self.lbl_page)
        pdf_nav_layout.addWidget(self.btn_next)
        pdf_nav_layout.addSpacing(6)
        pdf_nav_layout.addWidget(self.btn_zoom_in)
        pdf_nav_layout.addWidget(self.btn_zoom_out)
        pdf_nav_layout.addWidget(self.btn_fit_width)

        right_layout.addWidget(self.pdf_nav_bar)

        # Right Stacked Widget: Page 0 = Placeholder / Compiling, Page 1 = Native QPdfView
        self.pdf_stack = QStackedWidget(right_container)
        
        # Placeholder View
        self.placeholder_widget = QFrame(self.pdf_stack)
        self.placeholder_widget.setObjectName("PdfPlaceholderFrame")
        ph_layout = QVBoxLayout(self.placeholder_widget)
        ph_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.setSpacing(12)

        self.lbl_ph_icon = QLabel("📄", self.placeholder_widget)
        self.lbl_ph_icon.setFont(QFont("-apple-system", 36))
        self.lbl_ph_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_ph_text = QLabel("Compiling PDF Preview with Tectonic...\nPlease wait.", self.placeholder_widget)
        self.lbl_ph_text.setFont(QFont("-apple-system", 12))
        self.lbl_ph_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_ph_text.setStyleSheet("color: #8e8e93;")

        ph_layout.addWidget(self.lbl_ph_icon)
        ph_layout.addWidget(self.lbl_ph_text)

        # QPdfView View
        self.pdf_doc = QPdfDocument(self)
        self.pdf_view = QPdfView(self.pdf_stack)
        self.pdf_view.setDocument(self.pdf_doc)
        self.pdf_view.setPageMode(QPdfView.PageMode.SinglePage)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        if hasattr(self.pdf_view, 'pageNavigator') and self.pdf_view.pageNavigator():
            self.pdf_view.pageNavigator().currentPageChanged.connect(self._on_visual_page_changed)

        self.pdf_stack.addWidget(self.placeholder_widget) # Index 0
        self.pdf_stack.addWidget(self.pdf_view)           # Index 1
        self.pdf_stack.setCurrentIndex(0)

        right_layout.addWidget(self.pdf_stack, stretch=1)

        self.splitter.addWidget(left_container)
        self.splitter.addWidget(right_container)
        self.splitter.setSizes([480, 520])

        layout.addWidget(self.splitter, stretch=1)

    def set_latex_code(self, code: str, title: str = "LaTeX Document"):
        self.doc_title = title
        self.lbl_title.setText(f"📝 {title}")
        self._initial_code = code
        self.is_dirty = False
        self.editor.setPlainText(code)

    def get_latex_code(self) -> str:
        return self.editor.toPlainText()

    def _on_text_changed(self):
        if self.editor.toPlainText() != self._initial_code:
            self.is_dirty = True

    def load_pdf(self, file_path: str) -> bool:
        """Loads a compiled vector PDF into QPdfView on the right side of the split screen."""
        if not file_path or not os.path.exists(file_path):
            self.lbl_ph_text.setText("PDF preview not found.\nClick '🔄 Recompile Preview' to compile.")
            self.pdf_stack.setCurrentIndex(0)
            return False

        try:
            self.pdf_file_path = file_path
            self.pdf_doc.load(file_path)
            self.total_pages = max(1, self.pdf_doc.pageCount())
            self.current_page = 1
            self._render_current_page()
            self.pdf_stack.setCurrentIndex(1)
            return True
        except Exception as e:
            print(f"[LatexEditorWidget] Error loading PDF {file_path}: {e}")
            self.lbl_ph_text.setText(f"Could not load PDF: {e}")
            self.pdf_stack.setCurrentIndex(0)
            return False

    def recompile_preview(self):
        """Compiles the currently edited LaTeX source and reloads the QPdfView."""
        code = self.editor.toPlainText().strip()
        if not code:
            QMessageBox.warning(self, "Empty LaTeX", "Cannot compile an empty LaTeX document.")
            return

        # Target PDF in temp storage
        temp_dir = tempfile.gettempdir()
        safe_name = "".join(c for c in self.doc_title if c.isalnum() or c in " _-").strip().replace(" ", "_") or "preview"
        target_path = os.path.join(temp_dir, f"{safe_name}_preview.pdf")

        self.btn_recompile.setEnabled(False)
        self.btn_recompile.setText("⏳ Compiling...")
        self.lbl_ph_text.setText("Compiling LaTeX with Tectonic...\nPlease wait.")
        if self.pdf_stack.currentIndex() == 0:
            self.lbl_ph_icon.setText("⏳")

        # Stop previous worker if running
        if self._recompile_worker and self._recompile_worker.isRunning():
            self._recompile_worker.wait(100)

        self._recompile_worker = LatexRecompileWorker(code, target_path, parent=self)
        self._recompile_worker.compilation_finished.connect(self._on_recompilation_finished)
        self._recompile_worker.start()

    def _on_recompilation_finished(self, success: bool, msg_or_path: str):
        self.btn_recompile.setEnabled(True)
        self.btn_recompile.setText("🔄 Recompile Preview")
        self.lbl_ph_icon.setText("📄")

        if success and os.path.exists(msg_or_path):
            self.is_dirty = False
            self.load_pdf(msg_or_path)
            self.pdf_compiled.emit(msg_or_path)
            # Subtle indicator on button
            self.btn_recompile.setText("✓ PDF Updated!")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self.btn_recompile.setText("🔄 Recompile Preview"))
        else:
            self.lbl_ph_text.setText(f"Compilation notice:\n{msg_or_path[:200]}")
            QMessageBox.warning(
                self, "Compilation Notice",
                f"LaTeX compilation encountered an issue:\n\n{msg_or_path[:400]}"
            )

    def _prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._render_current_page()

    def _next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._render_current_page()

    def _render_current_page(self):
        self.lbl_page.setText(f"Page {self.current_page} of {self.total_pages}")
        if hasattr(self.pdf_view, 'pageNavigator') and self.pdf_view.pageNavigator():
            try:
                self.pdf_view.pageNavigator().jump(self.current_page - 1, QPointF())
            except Exception:
                pass

    def _on_visual_page_changed(self, page_index: int):
        self.current_page = page_index + 1
        self.lbl_page.setText(f"Page {self.current_page} of {self.total_pages}")

    def _zoom_in(self):
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.pdf_view.setZoomFactor(self.pdf_view.zoomFactor() * 1.2)

    def _zoom_out(self):
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.pdf_view.setZoomFactor(self.pdf_view.zoomFactor() / 1.2)

    def _fit_width(self):
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

    def _copy_to_clipboard(self):
        QApplication.clipboard().setText(self.editor.toPlainText())
        self.btn_copy.setText("✓ Copied!")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: self.btn_copy.setText("📋 Copy Code"))

    def confirm_close(self) -> bool:
        if not self.is_dirty:
            return True

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Close LaTeX Document?")
        msg_box.setText("You have unsaved changes in your LaTeX document.")
        msg_box.setInformativeText("Would you like to export the latest edited document as a PDF before closing?")
        
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

        # If already compiled and not modified, copy the existing PDF
        if not self.is_dirty and self.pdf_file_path and os.path.exists(self.pdf_file_path):
            try:
                shutil.copy2(self.pdf_file_path, file_path)
                QMessageBox.information(
                    self, "PDF Saved",
                    f"PDF saved successfully to:\n{file_path}"
                )
                return True
            except Exception as e:
                print(f"[LatexEditor] Notice copying PDF: {e}")

        self.btn_export.setText("Compiling PDF...")
        self.btn_export.setEnabled(False)
        QApplication.processEvents()

        try:
            from ...backend.math_engine.latex_client import compile_custom_latex_pdf
            success, msg_or_path = compile_custom_latex_pdf(code, file_path)
            if success:
                self.is_dirty = False
                self.pdf_file_path = file_path
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
            QFrame#PdfNavBar {{
                background-color: {c['bg_titlebar']};
                border-bottom: 1px solid {c['border_color']};
                border-radius: 4px;
            }}
            QFrame#PdfPlaceholderFrame {{
                background-color: {c['canvas_bg']};
                border: 1px dashed {c['border_color']};
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
            QPushButton#BtnCloseLatex {{
                background-color: #ef4444;
                color: #ffffff;
                border: none;
            }}
            QPushButton#BtnCloseLatex:hover {{
                background-color: #dc2626;
            }}
            QSplitter::handle {{
                background-color: {c['border_color']};
                width: 3px;
            }}
        """)

