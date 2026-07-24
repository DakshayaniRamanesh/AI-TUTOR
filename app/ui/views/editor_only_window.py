"""
Editor-Only View Window
Lightweight distraction-free Markdown editor OR Freeform Canvas Board view opened via Share Link.
Strips away administrative Git sidebar panels while keeping live editing & preview.
"""

import html
import json
import re
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTextEdit,
    QTextBrowser, QPushButton, QLabel, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from ..canvas_scene import CanvasScene
from ..canvas_view import CanvasView

class EditorOnlyWindow(QMainWindow):
    def __init__(self, filename: str = "physics_quantum_notes.md", initial_content: str = "", role: str = "editor", parent=None):
        super().__init__(parent)
        self.filename = filename
        self.role = role
        self.is_board = filename.endswith(".json") or "boards/" in filename
        self.setWindowTitle(f"Kestrel — Editor-Only Share Session ({filename})")
        self.resize(1060, 720)
        self._init_ui(initial_content)

    def _init_ui(self, initial_content: str):
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top Share Banner
        banner = QWidget(central)
        banner.setFixedHeight(44)
        banner.setStyleSheet("background-color: #007aff; color: white;")
        b_layout = QHBoxLayout(banner)
        b_layout.setContentsMargins(16, 0, 16, 0)

        type_icon = "🎨 Freeform Board" if self.is_board else "✏️ Note"
        lbl_info = QLabel(f"<b>Editor-Only Shared Session:</b> {type_icon} <i>{self.filename}</i> &nbsp;|&nbsp; Role: <b>{self.role.title()}</b>", banner)
        lbl_info.setStyleSheet("font-size: 13px; color: white;")
        b_layout.addWidget(lbl_info)

        b_layout.addStretch()

        lbl_status = QLabel("✓ Connected & Synced", banner)
        lbl_status.setStyleSheet("background-color: rgba(255,255,255,0.2); padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 11px;")
        b_layout.addWidget(lbl_status)

        layout.addWidget(banner)

        if self.is_board:
            # Freeform Canvas Board View
            canvas_container = QWidget(central)
            cc_layout = QVBoxLayout(canvas_container)
            cc_layout.setContentsMargins(0, 0, 0, 0)

            self.scene = CanvasScene(self)
            self.view = CanvasView(self.scene, self)
            cc_layout.addWidget(self.view)

            # Try parsing items
            try:
                payload = json.loads(initial_content)
                items = payload.get("items", [])
                self.scene.load_from_dict_list(items)
            except Exception:
                pass

            layout.addWidget(canvas_container, 1)

        else:
            # Markdown Text Editor Splitter
            toolbar = QWidget(central)
            toolbar.setFixedHeight(36)
            toolbar.setStyleSheet("background-color: #f8f8fa; border-bottom: 1px solid #d1d1d6;")
            tb_layout = QHBoxLayout(toolbar)
            tb_layout.setContentsMargins(12, 0, 12, 0)
            tb_layout.setSpacing(6)

            tb_actions = [
                ("Bold", "**", "**"), ("Italic", "*", "*"), ("H1", "# ", ""), ("H2", "## ", ""),
                ("Code", "```python\n", "\n```"), ("Math", "$$\n", "\n$$"), ("Checklist", "- [ ] ", "")
            ]

            for title, p, s in tb_actions:
                btn = QPushButton(title, toolbar)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ffffff;
                        color: #1c1c1e;
                        border: 1px solid #d1d1d6;
                        border-radius: 4px;
                        padding: 4px 8px;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #e5e5ea;
                    }
                """)
                btn.clicked.connect(lambda _, prefix=p, suffix=s: self._insert_formatting(prefix, suffix))
                tb_layout.addWidget(btn)

            tb_layout.addStretch()
            layout.addWidget(toolbar)

            # Splitter: Source Editor + Live Preview
            split = QSplitter(Qt.Orientation.Horizontal)
            split.setHandleWidth(1)
            split.setStyleSheet("QSplitter::handle { background-color: #d1d1d6; }")

            self.txt_source = QTextEdit(central)
            self.txt_source.setFont(QFont("Fira Code", 11))
            self.txt_source.setPlaceholderText("Collaborator Markdown editor...")
            self.txt_source.setStyleSheet("background-color: #ffffff; color: #1c1c1e; padding: 16px; border: none;")
            self.txt_source.setText(initial_content or "# Shared Note\n\nType content here...")
            self.txt_source.textChanged.connect(self._on_text_changed)
            split.addWidget(self.txt_source)

            if self.role == "viewer":
                self.txt_source.setReadOnly(True)

            self.browser_preview = QTextBrowser(central)
            self.browser_preview.setStyleSheet("background-color: #fafafa; padding: 20px; border-left: 1px solid #d1d1d6;")
            split.addWidget(self.browser_preview)

            split.setSizes([500, 500])
            layout.addWidget(split, 1)
            self._render_preview(self.txt_source.toPlainText())

        # Footer
        footer = QWidget(central)
        footer.setFixedHeight(26)
        footer.setStyleSheet("background-color: #f2f2f7; border-top: 1px solid #d1d1d6; color: #6e6e73; font-size: 11px;")
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(12, 0, 12, 0)
        self.lbl_word_count = QLabel("Simultaneous Session", footer)
        f_layout.addWidget(self.lbl_word_count)
        f_layout.addStretch()
        f_layout.addWidget(QLabel("Live Git Sync Active", footer))
        layout.addWidget(footer)

    def _insert_formatting(self, prefix: str, suffix: str):
        if self.role == "viewer" or self.is_board: return
        cursor = self.txt_source.textCursor()
        selected = cursor.selectedText() or "text"
        cursor.insertText(f"{prefix}{selected}{suffix}")

    def _on_text_changed(self):
        if hasattr(self, 'txt_source'):
            text = self.txt_source.toPlainText()
            self._render_preview(text)

    def _render_preview(self, text: str):
        if not hasattr(self, 'browser_preview'): return
        lines = text.split("\n")
        out = []
        for line in lines:
            escaped = html.escape(line)
            if escaped.startswith("# "): out.append(f"<h1 style='color:#000; border-bottom:1px solid #ccc;'>{escaped[2:]}</h1>")
            elif escaped.startswith("## "): out.append(f"<h2 style='color:#007aff;'>{escaped[3:]}</h2>")
            elif escaped.startswith("- [ ] "): out.append(f"<p><input type='checkbox' disabled> {escaped[6:]}</p>")
            elif escaped.startswith("- "): out.append(f"<ul><li>{escaped[2:]}</li></ul>")
            elif escaped.strip():
                fmt = re.sub(r'\$([^\$]+)\$', r'<span style="color:#b45309; font-weight:bold;">\1</span>', escaped)
                out.append(f"<p>{fmt}</p>")

        self.browser_preview.setHtml(f"<html><body style='font-family:sans-serif; color:#1c1c1e; line-height:1.6;'>{chr(10).join(out)}</body></html>")
        words = len(re.findall(r'\w+', text))
        self.lbl_word_count.setText(f"{words} words")
