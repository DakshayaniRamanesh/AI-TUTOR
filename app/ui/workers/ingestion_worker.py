from PyQt6.QtCore import QThread, pyqtSignal
from backend.workspace.subject_ingestion_service import SubjectIngestionService

class IngestionWorker(QThread):
    """
    Background worker for ingesting materials without blocking the UI.
    """
    
    # Signals
    # Emits (material_id, status_string)
    status_changed = pyqtSignal(str, str)
    
    # Emits (material_id, result_dict)
    finished = pyqtSignal(str, dict)
    
    # Emits (material_id, error_string)
    error = pyqtSignal(str, str)

    def __init__(self, material_id: str, subject_id: str, file_path: str, resource_type: str, parent=None):
        super().__init__(parent)
        self.material_id = material_id
        self.subject_id = subject_id
        self.file_path = file_path
        self.resource_type = resource_type
        self.service = SubjectIngestionService()
        self._is_cancelled = False
        
    def cancel(self):
        self._is_cancelled = True
        
    def run(self):
        try:
            self.status_changed.emit(self.material_id, "Extracting...")
            
            # The service handles its own status updates to the database
            result = self.service.ingest_material(
                self.material_id, 
                self.subject_id, 
                self.file_path, 
                self.resource_type,
                cancel_check=lambda: self._is_cancelled
            )
            
            if result.get("status") == "FAILED":
                self.error.emit(self.material_id, result.get("error", "Unknown error"))
            else:
                self.status_changed.emit(self.material_id, "Ready" if result.get("status") == "READY" else "Ready (Lexical Only)")
                self.finished.emit(self.material_id, result)
                
        except Exception as e:
            self.error.emit(self.material_id, str(e))
