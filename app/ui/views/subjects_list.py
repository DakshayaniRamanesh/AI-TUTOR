from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QScrollArea, QGridLayout, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal

# Import our DB layer (ensure your filename matches here — using database_ops)
from app.storage.database_ops import get_user_subjects, create_subject, get_or_create_user

class SubjectsListView(QWidget):
    # Signals for navigation
    open_subject_detail = pyqtSignal(str) # Passes the clicked subject_id
    go_back = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #f8f9fa; color: #1c1c1e; font-family: -apple-system, sans-serif;")
        
        # For prototyping without a real login screen, we'll auto-login a dummy user
        self.current_user = get_or_create_user("student_01")
        
        self._setup_ui()
        self.refresh_subjects()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header Bar
        header_layout = QHBoxLayout()
        
        self.btn_back = QPushButton("← Home")
        self.btn_back.clicked.connect(self.go_back.emit)
        self.btn_back.setStyleSheet("border: none; color: #007aff; font-size: 16px; font-weight: bold;")
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout.addWidget(self.btn_back)

        title = QLabel("My Subjects")
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin-left: 20px;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()

        self.btn_new = QPushButton("+ New Subject")
        self.btn_new.clicked.connect(self._on_new_subject)
        self.btn_new.setStyleSheet("""
            QPushButton {
                background-color: #007aff;
                color: white;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #005bb5; }
        """)
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
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.scroll.setWidget(self.grid_widget)
        layout.addWidget(self.scroll)

    def refresh_subjects(self):
        # Clear existing cards before redrawing
        for i in reversed(range(self.grid_layout.count())): 
            widget_to_remove = self.grid_layout.itemAt(i).widget()
            if widget_to_remove:
                widget_to_remove.setParent(None)

        subjects = get_user_subjects(self.current_user.id)
        
        if not subjects:
            empty_label = QLabel("No subjects yet. Click '+ New Subject' to create one.")
            empty_label.setStyleSheet("color: #6e6e73; font-size: 16px; margin-top: 40px;")
            self.grid_layout.addWidget(empty_label, 0, 0)
            return

        row, col = 0, 0
        max_cols = 3 # Adjust this for wider/narrower screens

        for subject in subjects:
            card = self._create_subject_card(subject)
            self.grid_layout.addWidget(card, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def _create_subject_card(self, subject) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(260, 140)
        
        # Because we defined relationships in SQLAlchemy, we can just do len() to get counts
        nb_count = len(subject.notebooks)
        mat_count = len(subject.materials)
        vid_count = len(subject.videos)

        # Basic styling with line breaks for the card format
        btn.setText(f"{subject.name}\n\n📓 {nb_count} Notes    📄 {mat_count} PDFs    🎥 {vid_count} Videos")
        
        btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 10px;
                text-align: left;
                padding: 15px;
                font-size: 14px;
                font-weight: 500;
                color: #1c1c1e;
            }
            QPushButton:hover {
                border-color: #007aff;
                background-color: #f0f8ff;
            }
        """)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # When clicked, emit the signal with this specific subject's ID
        btn.clicked.connect(lambda _, s_id=subject.id: self.open_subject_detail.emit(s_id))
        return btn

    def _on_new_subject(self):
        name, ok = QInputDialog.getText(self, "New Subject", "Enter subject name (e.g. Linear Algebra):")
        if ok and name.strip():
            create_subject(self.current_user.id, name.strip())
            self.refresh_subjects() # Re-render the grid
