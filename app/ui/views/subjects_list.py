"""
Curriculum Subjects & Notebooks View
Matches the Figma reference screen:
- Large bold display title: 'Curriculum Subjects & Notebooks'
- Monospace subheaders and tag pills
- Crisp monochrome cards with technical metadata footer (board counts, sync status)
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QScrollArea, QGridLayout, QInputDialog, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from app.storage.database_ops import get_user_subjects, create_subject, get_or_create_user
from ..theme_manager import ThemeManager
from ..kestrel_theme import MONO_FONT, primary_button_qss, ghost_button_qss


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
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

        # Header Bar
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        self.btn_back = QPushButton("← BACK", self)
        self.btn_back.clicked.connect(self.go_back.emit)
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout.addWidget(self.btn_back)

        self.lbl_title = QLabel("Curriculum Subjects & Notebooks", self)
        header_layout.addWidget(self.lbl_title)
        
        header_layout.addStretch()

        self.btn_new = QPushButton("+ NEW SUBJECT", self)
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
        self.grid_layout.setSpacing(16)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.scroll.setWidget(self.grid_widget)
        layout.addWidget(self.scroll)

    def _apply_theme(self, theme_name: str = "light"):
        c = ThemeManager.instance().get_colors()
        self.setStyleSheet(f"background-color: {c['bg_app']};")

        self.btn_back.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                padding: 5px 12px;
                color: {c['text_secondary']};
                font-family: {MONO_FONT};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{
                color: {c['text_primary']};
                border-color: {c['accent']};
            }}
        """)

        self.lbl_title.setStyleSheet(f"""
            font-size: 24px;
            font-weight: 800;
            color: {c['text_primary']};
            background: transparent;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin-left: 8px;
        """)

        self.btn_new.setStyleSheet(primary_button_qss(c))

    def refresh_subjects(self):
        for i in reversed(range(self.grid_layout.count())): 
            widget_to_remove = self.grid_layout.itemAt(i).widget()
            if widget_to_remove:
                widget_to_remove.setParent(None)

        subjects = get_user_subjects(self.current_user.id)
        c = ThemeManager.instance().get_colors()
        
        if not subjects:
            empty_label = QLabel("No curriculum subjects yet. Click '+ NEW SUBJECT' to initialize.")
            empty_label.setStyleSheet(f"color: {c['text_secondary']}; font-family: {MONO_FONT}; font-size: 13px; margin-top: 40px;")
            self.grid_layout.addWidget(empty_label, 0, 0)
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

    def _create_subject_card(self, subject) -> QFrame:
        c = ThemeManager.instance().get_colors()
        card = QFrame()
        card.setFixedSize(300, 160)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setObjectName("SubjectCard")

        card.setStyleSheet(f"""
            QFrame#SubjectCard {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border_color']};
                border-radius: 4px;
            }}
            QFrame#SubjectCard:hover {{
                border-color: {c['accent']};
                background-color: {c['panel_card_bg']};
            }}
        """)

        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(14, 12, 14, 12)
        c_layout.setSpacing(6)

        # Micro Header Tag
        lbl_tag = QLabel("CURRICULUM UNIT", card)
        lbl_tag.setStyleSheet(f"""
            font-family: {MONO_FONT};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1px;
            color: {c['text_secondary']};
            background: transparent;
        """)
        c_layout.addWidget(lbl_tag)

        # Subject Title
        lbl_name = QLabel(f"∑ {subject.name}", card)
        lbl_name.setStyleSheet(f"""
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            font-size: 16px;
            font-weight: 700;
            color: {c['text_primary']};
            background: transparent;
        """)
        c_layout.addWidget(lbl_name)

        # Description / Counts
        nb_count = len(subject.notebooks)
        mat_count = len(subject.materials)
        vid_count = len(subject.videos)

        lbl_desc = QLabel(f"Structured workspace for {subject.name} derivations, proofs & study notes.", card)
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"""
            font-size: 12px;
            color: {c['text_secondary']};
            background: transparent;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        """)
        c_layout.addWidget(lbl_desc)

        c_layout.addStretch()

        # Footer stats row
        footer_layout = QHBoxLayout()
        lbl_stats = QLabel(f"{nb_count} boards  {mat_count} PDFs", card)
        lbl_stats.setStyleSheet(f"""
            font-family: {MONO_FONT};
            font-size: 11px;
            color: {c['text_secondary']};
            background: transparent;
        """)
        footer_layout.addWidget(lbl_stats)

        footer_layout.addStretch()

        lbl_synced = QLabel("● Synced", card)
        lbl_synced.setStyleSheet(f"""
            font-family: {MONO_FONT};
            font-size: 11px;
            font-weight: 600;
            color: {c['text_secondary']};
            background: transparent;
        """)
        footer_layout.addWidget(lbl_synced)

        c_layout.addLayout(footer_layout)

        # Mouse click routing
        def _on_card_click(event):
            self.open_subject_detail.emit(subject.id)
        card.mousePressEvent = _on_card_click

        return card

    def _on_new_subject(self):
        name, ok = QInputDialog.getText(self, "New Subject", "Enter subject name (e.g. Linear Algebra):")
        if ok and name.strip():
            create_subject(self.current_user.id, name.strip())
            self.refresh_subjects()
