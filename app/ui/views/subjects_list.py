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
        self.grid_layout.setSpacing(20)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.grid_layout.setColumnStretch(0, 1)
        self.grid_layout.setColumnStretch(1, 1)
        self.grid_layout.setColumnStretch(2, 1)
        
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
        card.setObjectName("SubjectCard")
        card.setCursor(Qt.CursorShape.PointingHandCursor)

        card.setStyleSheet(f"""
            QFrame#SubjectCard {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border_color']};
                border-radius: 8px;
            }}
            QFrame#SubjectCard:hover {{
                border: 1.5px solid {c['accent']};
                background-color: {c['panel_card_bg']};
            }}
        """)

        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(18, 16, 18, 16)
        c_layout.setSpacing(6)

        # Subject-specific metadata mapping matching Figma reference
        META_MAP = {
            "Combined Mathematics": {
                "tag": "A/L COMBINED MATHEMATICS • UNITS 01-05",
                "symbol": "∑",
                "desc": "Pure Maths (Algebra, Calculus, Vectors, Complex Numbers) and Applied Mechanics (Dynamics, Statics, SHM).",
                "extra_stats": "42 AI proofs"
            },
            "Physics": {
                "tag": "A/L PHYSICS • UNITS 01-11",
                "symbol": "Ψ",
                "desc": "Mechanics, Waves & Oscillations, Thermal Physics, Gravitational & Electrostatic Fields, Electronics & Quantum.",
                "extra_stats": "12 past papers"
            },
            "Chemistry": {
                "tag": "A/L CHEMISTRY • UNITS 01-14",
                "symbol": "Δ",
                "desc": "Atomic Structure, Chemical Bonding, Reaction Kinetics, Equilibrium, Organic Mechanisms & Aromatic Chemistry.",
                "extra_stats": "36 syntheses"
            },
            "Semester 1 Notebooks": {
                "tag": "SEMESTER 1 • UNITS 01-06",
                "symbol": "∫",
                "desc": "Foundational units across Combined Mathematics, Physics, and Chemistry covering first-term coursework and assessments.",
                "extra_stats": "20 AI proofs"
            },
            "Semester 1 Revision": {
                "tag": "SEMESTER 1 • REVISION SET",
                "symbol": "§",
                "desc": "Consolidated revision boards, past paper walkthroughs, and quick-reference summaries for Semester 1 content.",
                "extra_stats": "15 past papers"
            },
        }

        meta = META_MAP.get(subject.name, {
            "tag": f"CURRICULUM UNIT • {subject.name.upper()}",
            "symbol": "∑",
            "desc": f"Structured workspace for {subject.name} derivations, proofs & study notes.",
            "extra_stats": f"{len(subject.materials)} PDFs"
        })

        # Micro Header Tag
        lbl_tag = QLabel(meta["tag"], card)
        lbl_tag.setStyleSheet(f"""
            font-family: {MONO_FONT};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1px;
            color: {c['text_secondary']};
            background: transparent;
        """)
        c_layout.addWidget(lbl_tag)

        # Subject Title with symbol
        lbl_name = QLabel(f"{meta['symbol']} {subject.name}", card)
        lbl_name.setStyleSheet(f"""
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            font-size: 15px;
            font-weight: 700;
            color: {c['text_primary']};
            background: transparent;
        """)
        c_layout.addWidget(lbl_name)

        # Description / Syllabus summary (tightly hugged)
        nb_count = len(subject.notebooks)
        lbl_desc = QLabel(meta["desc"], card)
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"""
            font-size: 12px;
            color: {c['text_secondary']};
            background: transparent;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            line-height: 1.4;
            margin-bottom: 4px;
        """)
        c_layout.addWidget(lbl_desc)

        # Footer stats row sitting close under the description
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 4, 0, 0)
        stats_text = f"{nb_count} boards  {meta['extra_stats']}"
        lbl_stats = QLabel(stats_text, card)
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
        card.mousePressEvent = lambda e, s_id=subject.id: self.open_subject_detail.emit(s_id)
        return card

    def _on_new_subject(self):
        name, ok = QInputDialog.getText(self, "New Subject", "Enter subject name (e.g. Linear Algebra):")
        if ok and name.strip():
            create_subject(self.current_user.id, name.strip())
            self.refresh_subjects()
