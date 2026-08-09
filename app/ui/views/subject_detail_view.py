from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QListWidget, QListWidgetItem, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal

# Import our DB operations
from app.storage.database_ops import get_subject_details, create_notebook, add_material

class SubjectDetailView(QWidget):
    # Signals for navigation
    go_back = pyqtSignal()
    open_notebook = pyqtSignal(str) # Passes the notebook_id to open

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #ffffff; color: #1c1c1e; font-family: -apple-system, sans-serif;")
        self.current_subject_id = None
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Header
        header_layout = QHBoxLayout()
        self.btn_back = QPushButton("← Back to Subjects")
        self.btn_back.clicked.connect(self.go_back.emit)
        self.btn_back.setStyleSheet("border: none; color: #007aff; font-size: 16px; font-weight: bold;")
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        header_layout.addWidget(self.btn_back)

        self.lbl_title = QLabel("Subject Details")
        self.lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; margin-left: 20px;")
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # Content Splitter (Left: Notebooks, Right: Materials & Videos)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- Left Panel: Notebooks ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        nb_header = QHBoxLayout()
        nb_lbl = QLabel("Notebooks")
        nb_lbl.setStyleSheet("font-size: 18px; font-weight: bold;")
        nb_header.addWidget(nb_lbl)
        
        btn_new_nb = QPushButton("+ New Note")
        btn_new_nb.clicked.connect(self._on_new_notebook)
        nb_header.addWidget(btn_new_nb)
        left_layout.addLayout(nb_header)

        self.list_notebooks = QListWidget()
        self.list_notebooks.setStyleSheet("font-size: 14px; padding: 5px;")
        # Double-clicking a notebook opens it
        self.list_notebooks.itemDoubleClicked.connect(self._on_notebook_clicked)
        left_layout.addWidget(self.list_notebooks)
        
        splitter.addWidget(left_panel)

        # --- Right Panel: Resources (Materials & Videos) ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Materials Section
        mat_header = QHBoxLayout()
        mat_lbl = QLabel("Reference Materials (PDFs)")
        mat_lbl.setStyleSheet("font-size: 18px; font-weight: bold;")
        mat_header.addWidget(mat_lbl)
        
        btn_new_mat = QPushButton("+ Mock Upload PDF")
        btn_new_mat.clicked.connect(self._on_upload_material)
        mat_header.addWidget(btn_new_mat)
        right_layout.addLayout(mat_header)

        self.list_materials = QListWidget()
        self.list_materials.setStyleSheet("font-size: 14px; padding: 5px;")
        right_layout.addWidget(self.list_materials)

        # Videos Section
        vid_header = QHBoxLayout()
        vid_lbl = QLabel("Generated Videos")
        vid_lbl.setStyleSheet("font-size: 18px; font-weight: bold; margin-top: 15px;")
        vid_header.addWidget(vid_lbl)
        right_layout.addLayout(vid_header)

        self.list_videos = QListWidget()
        self.list_videos.setStyleSheet("font-size: 14px; padding: 5px;")
        right_layout.addWidget(self.list_videos)

        splitter.addWidget(right_panel)
        splitter.setSizes([400, 600])

        main_layout.addWidget(splitter)

    def load_subject(self, subject_id: str):
        """Called by the main window when switching to this view."""
        self.current_subject_id = subject_id
        self.refresh_data()

    def refresh_data(self):
        if not self.current_subject_id:
            return
            
        subject = get_subject_details(self.current_subject_id)
        if not subject:
            return

        self.lbl_title.setText(f"📚 {subject.name}")

        # Populate Notebooks
        self.list_notebooks.clear()
        for nb in subject.notebooks:
            item = QListWidgetItem(f"📓 {nb.name}")
            item.setData(Qt.ItemDataRole.UserRole, nb.id) # Hide the ID in the item for later retrieval
            self.list_notebooks.addItem(item)

        # Populate Materials
        self.list_materials.clear()
        for mat in subject.materials:
            self.list_materials.addItem(f"📄 {mat.filename}")

        # Populate Videos
        self.list_videos.clear()
        for vid in subject.videos:
            self.list_videos.addItem(f"🎥 {vid.title}")

    def _on_new_notebook(self):
        """Creates a new notebook explicitly linked to this subject."""
        if self.current_subject_id:
            create_notebook("Untitled Notebook", self.current_subject_id)
            self.refresh_data()

    def _on_upload_material(self):
        """Mocks a file upload to show the UI updating."""
        if self.current_subject_id:
            add_material(self.current_subject_id, "example_document.pdf", "/mock/path/example.pdf")
            self.refresh_data()

    def _on_notebook_clicked(self, item: QListWidgetItem):
        """Emits the ID of the clicked notebook so the main window can open it."""
        nb_id = item.data(Qt.ItemDataRole.UserRole)
        self.open_notebook.emit(nb_id)
