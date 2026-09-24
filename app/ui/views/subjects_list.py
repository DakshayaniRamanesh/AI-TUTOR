"""
Phase 2: Premium Subject Workspace - Subjects List View
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QScrollArea, QGridLayout, QInputDialog, QFrame, QLineEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from app.storage.database_ops import get_user_subjects, create_subject, get_or_create_user
from ..theme_manager import ThemeManager
from ..kestrel_theme import MONO_FONT, DISPLAY_FONT, primary_button_qss, ghost_button_qss
from datetime import datetime

class SubjectsListView(QWidget):
    open_subject_detail = pyqtSignal(str)
    go_back = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_user = get_or_create_user("student_01")
        self._setup_ui()
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme(ThemeManager.instance().current_theme)
        self.refresh_subjects()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(24)

        # Header Bar
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)
        
        # Title and Subtitle Container
        title_container = QVBoxLayout()
        title_container.setSpacing(4)
        
        self.lbl_title = QLabel("Your subjects", self)
        self.lbl_subtitle = QLabel("Pick up where you left off, or begin something new.", self)
        
        title_container.addWidget(self.lbl_title)
        title_container.addWidget(self.lbl_subtitle)
        
        header_layout.addLayout(title_container)
        header_layout.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search subjects...")
        self.search_input.setFixedWidth(200)
        self.search_input.textChanged.connect(self._filter_subjects)
        header_layout.addWidget(self.search_input)

        self.btn_new = QPushButton("New subject")
        self.btn_new.clicked.connect(self._on_new_subject)
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout.addWidget(self.btn_new)

        layout.addLayout(header_layout)

        # Grid for Subject Cards
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet("background-color: transparent;")
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(24)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.grid_layout.setColumnStretch(0, 1)
        self.grid_layout.setColumnStretch(1, 1)
        self.grid_layout.setColumnStretch(2, 1)
        
        self.scroll.setWidget(self.grid_widget)
        layout.addWidget(self.scroll)

    def _apply_theme(self, theme_name: str = "light"):
        c = ThemeManager.instance().get_colors()
        self.setStyleSheet(f"background-color: {c['bg_app']};")

        self.lbl_title.setStyleSheet(f"""
            font-size: 28px;
            font-weight: 600;
            color: {c['text_primary']};
            background: transparent;
            font-family: {DISPLAY_FONT};
        """)
        
        self.lbl_subtitle.setStyleSheet(f"""
            font-size: 14px;
            color: {c['text_secondary']};
            background: transparent;
            font-family: {DISPLAY_FONT};
        """)

        self.btn_new.setStyleSheet(primary_button_qss(c, radius=6))
        
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {c['input_bg']};
                color: {c['text_primary']};
                border: 1px solid {c['border_color']};
                border-radius: 6px;
                padding: 6px 12px;
                font-family: {DISPLAY_FONT};
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {c['accent']};
            }}
        """)

    def _filter_subjects(self, query: str):
        query = query.lower()
        for i in range(self.grid_layout.count()):
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if hasattr(widget, "subject_name"):
                    widget.setVisible(query in widget.subject_name.lower())

    def refresh_subjects(self):
        for i in reversed(range(self.grid_layout.count())): 
            widget_to_remove = self.grid_layout.itemAt(i).widget()
            if widget_to_remove:
                widget_to_remove.setParent(None)

        subjects = get_user_subjects(self.current_user.id)
        c = ThemeManager.instance().get_colors()
        
        if not subjects:
            self._show_empty_state()
            return

        row, col = 0, 0
        max_cols = 3

        for subject in subjects:
            card = self._create_subject_card(subject)
            self.grid_layout.addWidget(card, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def _show_empty_state(self):
        c = ThemeManager.instance().get_colors()
        empty_widget = QWidget()
        empty_layout = QVBoxLayout(empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(16)
        
        lbl_empty_title = QLabel("Build your first learning space")
        lbl_empty_title.setStyleSheet(f"color: {c['text_primary']}; font-family: {DISPLAY_FONT}; font-size: 20px; font-weight: 600;")
        lbl_empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        lbl_empty_body = QLabel("Keep tutorials, notes and notebooks together so Kestrel can understand the subject as you study.")
        lbl_empty_body.setStyleSheet(f"color: {c['text_secondary']}; font-family: {DISPLAY_FONT}; font-size: 14px;")
        lbl_empty_body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_empty_body.setWordWrap(True)
        lbl_empty_body.setMaximumWidth(400)
        
        btn_create = QPushButton("Create a subject")
        btn_create.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_create.setStyleSheet(primary_button_qss(c, radius=6))
        btn_create.setFixedWidth(160)
        btn_create.clicked.connect(self._on_new_subject)
        
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_layout.addWidget(btn_create)
        
        empty_layout.addStretch()
        empty_layout.addWidget(lbl_empty_title)
        empty_layout.addWidget(lbl_empty_body)
        empty_layout.addLayout(btn_layout)
        empty_layout.addStretch()
        
        self.grid_layout.addWidget(empty_widget, 0, 0, 1, 3)

    def _create_subject_card(self, subject) -> QFrame:
        c = ThemeManager.instance().get_colors()
        card = QFrame()
        card.setObjectName("SubjectCard")
        card.subject_name = subject.name
        
        # Deterministic muted accent based on subject name
        accent_hues = ["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444", "#06b6d4"]
        if ThemeManager.instance().is_dark():
            accent_hues = ["#60a5fa", "#a78bfa", "#34d399", "#fbbf24", "#f87171", "#22d3ee"]
            
        color_idx = hash(subject.name) % len(accent_hues)
        accent_color = accent_hues[color_idx]

        card.setStyleSheet(f"""
            QFrame#SubjectCard {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border_color']};
                border-radius: 8px;
            }}
            QFrame#SubjectCard:hover {{
                border: 1px solid {accent_color};
                background-color: {c['panel_card_bg']};
            }}
        """)

        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(20, 20, 20, 20)
        c_layout.setSpacing(12)

        # Header with Name and deterministic color bar
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        color_bar = QFrame()
        color_bar.setFixedSize(4, 24)
        color_bar.setStyleSheet(f"background-color: {accent_color}; border-radius: 2px;")
        header_layout.addWidget(color_bar)
        
        lbl_name = QLabel(subject.name)
        lbl_name.setStyleSheet(f"""
            font-family: {DISPLAY_FONT};
            font-size: 18px;
            font-weight: 600;
            color: {c['text_primary']};
            background: transparent;
        """)
        header_layout.addWidget(lbl_name)
        header_layout.addStretch()
        c_layout.addLayout(header_layout)

        # Stats Grid
        nb_count = len(subject.notebooks)
        mat_count = len(subject.materials)
        vid_count = len(subject.videos)
        
        ready_count = 0
        search_ready_count = 0
        proc_count = 0
        failed_count = 0
        
        for m in subject.materials:
            s = m.ingestion_status
            if s == "READY":
                ready_count += 1
            elif s == "PARTIAL":
                # Both PDFs (lexical) and Images (stored) that are partial go to search-ready / stored pool
                search_ready_count += 1
            elif s in ("REGISTERED", "EXTRACTING", "INDEXING"):
                proc_count += 1
            elif s == "FAILED":
                failed_count += 1
                
        stats_layout = QVBoxLayout()
        stats_layout.setSpacing(4)
        
        def add_stat_row(label, value):
            row = QHBoxLayout()
            lbl_key = QLabel(label)
            lbl_key.setStyleSheet(f"color: {c['text_secondary']}; font-family: {DISPLAY_FONT}; font-size: 13px;")
            lbl_val = QLabel(str(value))
            lbl_val.setStyleSheet(f"color: {c['text_primary']}; font-family: {MONO_FONT}; font-size: 13px;")
            row.addWidget(lbl_key)
            row.addStretch()
            row.addWidget(lbl_val)
            stats_layout.addLayout(row)
            
        add_stat_row("Notebooks", nb_count)
        add_stat_row("Resources", mat_count)
        if vid_count > 0:
            add_stat_row("Generated videos", vid_count)
            
        parts = []
        if ready_count > 0:
            parts.append(f"{ready_count} ready")
        if search_ready_count > 0:
            parts.append(f"{search_ready_count} search-ready")
        if proc_count > 0:
            parts.append(f"{proc_count} processing")
        if failed_count > 0:
            parts.append(f"{failed_count} needs attention")
            
        if parts:
            lbl_proc = QLabel(" • ".join(parts))
            color_hex = "#f59e0b" if failed_count > 0 else ("#3b82f6" if proc_count > 0 else "#10b981")
            lbl_proc.setStyleSheet(f"color: {color_hex}; font-family: {DISPLAY_FONT}; font-size: 12px; margin-top: 4px;")
            stats_layout.addWidget(lbl_proc)

        c_layout.addLayout(stats_layout)
        c_layout.addStretch()
        
        # Footer
        footer_layout = QHBoxLayout()
        
        last_updated = subject.created_at
        if subject.notebooks:
            last_updated = max((nb.updated_at for nb in subject.notebooks if nb.updated_at), default=last_updated)
            
        if last_updated:
            time_str = last_updated.strftime("%b %d, %Y")
            lbl_time = QLabel(f"Updated {time_str}")
            lbl_time.setStyleSheet(f"color: {c['text_secondary']}; font-family: {DISPLAY_FONT}; font-size: 11px;")
            footer_layout.addWidget(lbl_time)
            
        footer_layout.addStretch()
        
        btn_continue = QPushButton("Continue")
        btn_continue.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_continue.setStyleSheet(ghost_button_qss(c, radius=4))
        btn_continue.clicked.connect(lambda _, s_id=subject.id: self.open_subject_detail.emit(s_id))
        footer_layout.addWidget(btn_continue)
        
        c_layout.addLayout(footer_layout)

        return card

    def _on_new_subject(self):
        name, ok = QInputDialog.getText(self, "New Subject", "Enter subject name (e.g. Algebra Essentials):")
        if ok and name.strip():
            create_subject(self.current_user.id, name.strip())
            self.refresh_subjects()
