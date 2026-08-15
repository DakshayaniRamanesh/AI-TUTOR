"""
PDF Split-Screen Visual Viewer Widget
Renders the exact visual PDF document pages with QPdfView (preserving original fonts, diagrams, math equations, and layout),
provides standard mouse text selection highlighting, surrounding paragraph context extraction, and floating 'Reply ↰' button.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QGraphicsDropShadowEffect, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QPointF, QRectF, QObject, QEvent
from PyQt6.QtGui import QColor, QCursor, QPainter, QBrush, QPen
from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtPdfWidgets import QPdfView
from pypdf import PdfReader


class PdfHighlightOverlayWidget(QWidget):
    """
    Transparent overlay rendered over QPdfView's viewport to paint standard mouse text selection highlights.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.highlight_rects = []

    def set_highlight_rects(self, rects: list):
        self.highlight_rects = rects or []
        self.update()

    def clear_highlight(self):
        self.highlight_rects = []
        self.update()

    def paintEvent(self, event):
        if not self.highlight_rects:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        fill_color = QColor(64, 156, 255, 70)
        border_color = QColor(0, 122, 255, 180)
        
        painter.setBrush(QBrush(fill_color))
        painter.setPen(QPen(border_color, 1.2))
        
        for rect in self.highlight_rects:
            if isinstance(rect, QRectF):
                painter.drawRoundedRect(rect, 3, 3)
            elif isinstance(rect, (tuple, list)):
                if len(rect) == 4:
                    r = QRectF(rect[0], rect[1], rect[2], rect[3])
                    painter.drawRoundedRect(r, 3, 3)


class ReplyPillButton(QFrame):
    """
    Sleek, minimal dark pill button ('Reply ↰') floating directly above selected text on the PDF document.
    """
    reply_clicked = pyqtSignal(str, int, str) # selected_text, page_num, surrounding_context

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_text = ""
        self.current_page = 1
        self.surrounding_context = ""
        
        self.setObjectName("ReplyPillRoot")
        self.setFixedSize(95, 34)
        
        self.setStyleSheet("""
            QFrame#ReplyPillRoot {
                background-color: #222224;
                border: 1px solid #3a3a3c;
                border-radius: 16px;
            }
            QPushButton#BtnReplyPill {
                background-color: transparent;
                color: #ffffff;
                font-size: 13px;
                font-weight: 600;
                border: none;
                padding: 4px 8px;
            }
            QPushButton#BtnReplyPill:hover {
                color: #007aff;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(0)

        self.btn_reply = QPushButton("Reply ↰", self)
        self.btn_reply.setObjectName("BtnReplyPill")
        self.btn_reply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reply.clicked.connect(self._on_click)
        layout.addWidget(self.btn_reply)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 90))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)

        self.hide()

    def show_at(self, global_pos: QPoint, text: str, page_num: int, context: str):
        self.selected_text = text.strip()
        self.current_page = page_num
        self.surrounding_context = context.strip()
            
        parent_widget = self.parentWidget()
        if parent_widget:
            local_pos = parent_widget.mapFromGlobal(global_pos)
            px = max(10, min(parent_widget.width() - 105, local_pos.x() - 45))
            py = max(10, min(parent_widget.height() - 45, local_pos.y() - 42))
            self.move(px, py)
        self.show()
        self.raise_()

    def _on_click(self):
        self.reply_clicked.emit(self.selected_text, self.current_page, self.surrounding_context)


class PdfViewportEventFilter(QObject):
    """
    Event filter installed on QPdfView's viewport to capture mouse text selection on the visual PDF.
    """
    def __init__(self, pdf_widget):
        super().__init__(pdf_widget)
        self.pdf_widget = pdf_widget
        self.press_pos = None
        self.is_dragging = False

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.pdf_widget.zoom_in()
            else:
                self.pdf_widget.zoom_out()
            return True

        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self.press_pos = event.pos()
                self.is_dragging = True
                self.pdf_widget.overlay.clear_highlight()
                self.pdf_widget.reply_pill.hide()

        elif event.type() == QEvent.Type.MouseMove:
            if self.is_dragging and self.press_pos is not None:
                current_pos = event.pos()
                self.pdf_widget._update_selection_highlight(self.press_pos, current_pos)

        elif event.type() == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton and self.press_pos is not None:
                release_pos = event.pos()
                global_pos = QCursor.pos()
                self.is_dragging = False
                
                self.pdf_widget._update_selection_highlight(self.press_pos, release_pos)
                self.pdf_widget._handle_selection_released(self.press_pos, release_pos, global_pos)
                self.press_pos = None

        return False


class PdfViewerWidget(QWidget):
    """
    Split-Screen Visual RAG + Document Viewer.
    Allows viewing PDFs, extracting contextual text highlighting, and toggling between original and generated LaTeX formats.
    """
    close_requested = pyqtSignal()
    reply_clicked = pyqtSignal(str, int, str) # selected_text, page_num, surrounding_context
    latex_video_requested = pyqtSignal(str,str,str,str) # latex_file_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_path = ""
        self.latex_file_path = ""
        self.current_mode = "source"  # "source" or "latex"
        self.current_page = 1
        self.total_pages = 1
        self.pages_text = {} # page_num -> text

        self.pdf_doc = QPdfDocument(self)
        
        self.setStyleSheet("""
            QWidget#PdfViewerRoot {
                background-color: #ffffff;
                border-right: 2px solid #d1d1d6;
            }
            QFrame#HeaderBar {
                background-color: #f8f8fa;
                border-bottom: 1px solid #d1d1d6;
            }
            QLabel#DocTitleLabel {
                font-size: 13px;
                font-weight: 700;
                color: #1c1c1e;
            }
            QLabel#PageNumLabel {
                font-size: 12px;
                font-weight: 600;
                color: #8e8e93;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
                font-weight: 600;
                color: #1c1c1e;
            }
            QPushButton:hover {
                background-color: #e5e5ea;
            }
            QPushButton#BtnClosePdf {
                background-color: #ff3b30;
                color: white;
                border: none;
                font-weight: bold;
            }
            QPushButton#BtnClosePdf:hover {
                background-color: #d32f2f;
            }
        """)

        self.setObjectName("PdfViewerRoot")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Header Navigation Bar
        header = QFrame(self)
        header.setObjectName("HeaderBar")
        header.setFixedHeight(44)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 4, 12, 4)
        h_layout.setSpacing(8)

        self.lbl_title = QLabel("📄 Document", header)
        self.lbl_title.setObjectName("DocTitleLabel")

        # Tabs
        self.tab_source = QPushButton("Source PDF", header)
        self.tab_source.setCheckable(True)
        self.tab_source.setChecked(True)
        self.tab_source.clicked.connect(lambda: self._switch_mode("source"))
        
        self.tab_latex = QPushButton("Generated LaTeX", header)
        self.tab_latex.setCheckable(True)
        self.tab_latex.setVisible(False)  # Hidden until latex is loaded
        self.tab_latex.clicked.connect(lambda: self._switch_mode("latex"))
        
        self.btn_generate_video = QPushButton("🎬 Generate Animation Video", header)
        self.btn_generate_video.setStyleSheet("background-color: #34c759; color: white; border: none;")
        self.btn_generate_video.setVisible(False)
        self.btn_generate_video.clicked.connect(self._on_generate_clicked)

        self.video_progress_bar = QProgressBar(header)
        self.video_progress_bar.setRange(0, 100)
        self.video_progress_bar.setFixedSize(120, 20)
        self.video_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #d1d1d6;
                border-radius: 4px;
                text-align: center;
                background-color: #f2f2f7;
                color: #1c1c1e;
                font-size: 10px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #34c759;
                border-radius: 3px;
            }
        """)
        self.video_progress_bar.setVisible(False)

        self.lbl_page = QLabel("Page 1 of 1", header)
        self.lbl_page.setObjectName("PageNumLabel")

        btn_prev = QPushButton("◀ Prev", header)
        btn_prev.clicked.connect(self._prev_page)

        btn_next = QPushButton("Next ▶", header)
        btn_next.clicked.connect(self._next_page)

        btn_close = QPushButton("✕ Close", header)
        btn_close.setObjectName("BtnClosePdf")
        btn_close.clicked.connect(self.close_requested.emit)

        h_layout.addWidget(self.lbl_title)
        h_layout.addSpacing(20)
        h_layout.addWidget(self.tab_source)
        h_layout.addWidget(self.tab_latex)
        h_layout.addSpacing(10)
        h_layout.addWidget(self.btn_generate_video)
        h_layout.addWidget(self.video_progress_bar)
        h_layout.addStretch()
        h_layout.addWidget(btn_prev)
        h_layout.addWidget(self.lbl_page)
        h_layout.addWidget(btn_next)
        h_layout.addStretch()
        h_layout.addWidget(btn_close)

        main_layout.addWidget(header)

        # 2. Pure Visual PDF View (QPdfView) - Render original visual PDF pages
        self.pdf_view = QPdfView(self)
        self.pdf_view.setDocument(self.pdf_doc)
        self.pdf_view.setPageMode(QPdfView.PageMode.SinglePage)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.pdf_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.pdf_view.customContextMenuRequested.connect(self._on_custom_context_menu)

        if hasattr(self.pdf_view, 'pageNavigator') and self.pdf_view.pageNavigator():
            self.pdf_view.pageNavigator().currentPageChanged.connect(self._on_visual_page_changed)
        main_layout.addWidget(self.pdf_view)

        # Transparent Highlight Overlay Widget over QPdfView's viewport
        self.overlay = PdfHighlightOverlayWidget(self.pdf_view.viewport())
        self.overlay.setGeometry(self.pdf_view.viewport().rect())

        # Install viewport event filter for mouse selection
        self.event_filter = PdfViewportEventFilter(self)
        self.pdf_view.viewport().installEventFilter(self.event_filter)

        # 3. Floating 'Reply ↰' Pill Button
        self.reply_pill = ReplyPillButton(self)
        self.reply_pill.reply_clicked.connect(self.reply_clicked.emit)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'overlay') and hasattr(self, 'pdf_view'):
            self.overlay.setGeometry(self.pdf_view.viewport().rect())

    def _on_generate_clicked(self):
        from PyQt6.QtWidgets import QInputDialog
        # 1. Output Type
        output_type, ok1 = QInputDialog.getItem(
            self, "Output Type", "Do you want Notes or a Video?",
            ["video", "notes"], 0, False
        )
        if not ok1: return
        
        # 2. Page Range
        page_range, ok2 = QInputDialog.getText(
            self, "Target Section", "Enter page range (e.g. '15-20', or leave blank for full document):"
        )
        if not ok2: return
        
        # 3. Emphasis Note
        emphasis, ok3 = QInputDialog.getText(
            self, "Emphasis Note", "Any specific instructions? (e.g. 'Focus on the definition of vectors', or leave blank)"
        )
        if not ok3: return
        
        # Emit all of it to the main window
        self.latex_video_requested.emit(self.latex_file_path, page_range.strip(), emphasis.strip(), output_type)


    def load_pdf(self, file_path: str) -> bool:
        """
        Loads PDF into native QPdfView for exact visual page rendering & extracts text layers for RAG.
        """
        if not os.path.exists(file_path):
            return False

        try:
            self.file_path = file_path
            self.current_mode = "source"
            self.tab_source.setChecked(True)
            self.tab_latex.setChecked(False)
            
            fname = os.path.basename(file_path)
            self.lbl_title.setText(f"📄 {fname[:24]}..." if len(fname) > 26 else f"📄 {fname}")

            self.pdf_doc.load(file_path)
            self.total_pages = self.pdf_doc.pageCount() if self.pdf_doc.pageCount() > 0 else 1

            reader = PdfReader(file_path)
            self.pages_text = {}
            for idx, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                self.pages_text[idx + 1] = text.strip()

            self.current_page = 1
            self._render_current_page()
            return True
        except Exception as err:
            print(f"[PdfViewerWidget] Error loading PDF: {err}")
            return False

    def load_latex_pdf(self, latex_file_path: str) -> bool:
        """
        Loads a generated LaTeX PDF. Shows the LaTeX tab and switches to it.
        """
        if not os.path.exists(latex_file_path):
            return False
            
        try:
            self.latex_file_path = latex_file_path
            self.tab_latex.setVisible(True)
            self._switch_mode("latex")
            self.show()
            return True
        except Exception as err:
            print(f"[PdfViewerWidget] Error loading LaTeX PDF: {err}")
            return False

    def video_generation_started(self):
        self.btn_generate_video.setVisible(False)
        self.video_progress_bar.setValue(0)
        self.video_progress_bar.setFormat("Initializing...")
        self.video_progress_bar.setVisible(True)

    def update_video_progress(self, stage: str, progress: int):
        self.video_progress_bar.setValue(progress)
        
        # Clean up the stage string for a small progress bar
        short_stage = stage.replace("🎬 ", "").replace("Manim: ", "")
        if len(short_stage) > 15:
            short_stage = short_stage[:15] + "..."
            
        self.video_progress_bar.setFormat(f"{progress}% - {short_stage}")
        
        if progress >= 100:
            self.video_progress_bar.setVisible(False)
            self.btn_generate_video.setText("✓ Video Generated")
            self.btn_generate_video.setVisible(True)

    def _switch_mode(self, mode: str):
        if mode == "source" and self.file_path:
            self.current_mode = "source"
            self.tab_source.setChecked(True)
            self.tab_latex.setChecked(False)
            self.btn_generate_video.setVisible(False)
            self.video_progress_bar.setVisible(False)
            self.pdf_doc.load(self.file_path)
            self.total_pages = self.pdf_doc.pageCount() if self.pdf_doc.pageCount() > 0 else 1
            self.current_page = 1
            self._render_current_page()
            
        elif mode == "latex" and self.latex_file_path:
            self.current_mode = "latex"
            self.tab_source.setChecked(False)
            self.tab_latex.setChecked(True)
            if not self.video_progress_bar.isVisible():
                self.btn_generate_video.setVisible(True)
            self.pdf_doc.load(self.latex_file_path)
            self.total_pages = self.pdf_doc.pageCount() if self.pdf_doc.pageCount() > 0 else 1
            self.current_page = 1
            self._render_current_page()

    def _render_current_page(self):
        self.lbl_page.setText(f"Page {self.current_page} of {self.total_pages}")
        
        if hasattr(self.pdf_view, 'pageNavigator') and self.pdf_view.pageNavigator():
            try:
                self.pdf_view.pageNavigator().jump(self.current_page - 1, QPointF())
            except Exception:
                pass
        self.overlay.clear_highlight()
        self.reply_pill.hide()

    def _update_selection_highlight(self, press_pos: QPoint, current_pos: QPoint):
        """
        Paints visual blue selection highlight box over selected sentence during/after mouse drag.
        """
        rects = []
        try:
            sel = self.pdf_doc.getSelection(self.current_page - 1, QPointF(press_pos), QPointF(current_pos))
            if sel and sel.isValid() and sel.bounds():
                rects = sel.bounds()
        except Exception:
            pass

        if not rects:
            rects = [QRectF(QPointF(press_pos), QPointF(current_pos)).normalized()]

        self.overlay.set_highlight_rects(rects)

    def _handle_selection_released(self, press_pos: QPoint, release_pos: QPoint, global_pos: QPoint):
        """
        Called when mouse selection is completed; positions the floating 'Reply ↰' pill button.
        """
        selected_text = ""
        try:
            sel = self.pdf_doc.getSelection(self.current_page - 1, QPointF(press_pos), QPointF(release_pos))
            if sel and sel.isValid() and sel.text().strip():
                selected_text = sel.text().strip()
        except Exception:
            pass

        if not selected_text:
            page_content = self.pages_text.get(self.current_page, "")
            selected_text = page_content[:300] if page_content else f"Passage on Page {self.current_page}"

        page_content = self.pages_text.get(self.current_page, "")
        surrounding_context = self._extract_surrounding_context(selected_text, page_content)

        self.reply_pill.show_at(global_pos, selected_text, self.current_page, surrounding_context)

    def _extract_surrounding_context(self, selected_text: str, full_page_text: str) -> str:
        if not full_page_text or not selected_text:
            return selected_text

        paragraphs = full_page_text.split('\n\n')
        for p in paragraphs:
            if selected_text in p or any(w in p for w in selected_text.split()[:4]):
                return p.strip()
        
        return full_page_text[:400]

    def _on_custom_context_menu(self, pos: QPoint):
        global_pos = self.pdf_view.mapToGlobal(pos)
        page_content = self.pages_text.get(self.current_page, "")
        selected_text = page_content[:300] if page_content else f"Passage on Page {self.current_page}"
        surrounding_context = self._extract_surrounding_context(selected_text, page_content)
        self.reply_pill.show_at(global_pos, selected_text, self.current_page, surrounding_context)

    def _on_visual_page_changed(self, page_index: int):
        self.current_page = page_index + 1
        self.lbl_page.setText(f"Page {self.current_page} of {self.total_pages}")
        self.overlay.clear_highlight()
        self.reply_pill.hide()

    def zoom_in(self):
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.pdf_view.setZoomFactor(self.pdf_view.zoomFactor() * 1.2)

    def zoom_out(self):
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.pdf_view.setZoomFactor(self.pdf_view.zoomFactor() / 1.2)

    def _prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._render_current_page()

    def _next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._render_current_page()
