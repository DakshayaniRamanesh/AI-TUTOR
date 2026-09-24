from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal
from app.services.memory.repositories import MemoryRepository

class LearningController(QObject):
    session_started = pyqtSignal(str)
    attempt_started = pyqtSignal(str)
    
    def __init__(self, memory_repo: MemoryRepository, parent=None):
        super().__init__(parent)
        self.memory_repo = memory_repo
        self.current_session_id: Optional[str] = None
        self.current_attempt_id: Optional[str] = None
        
    def start_learning_session(self) -> str:
        self.current_session_id = self.memory_repo.start_learning_session()
        self.session_started.emit(self.current_session_id)
        return self.current_session_id
        
    def start_problem_attempt(self) -> str:
        if not self.current_session_id:
            self.start_learning_session()
        self.current_attempt_id = self.memory_repo.start_problem_attempt(self.current_session_id)
        self.attempt_started.emit(self.current_attempt_id)
        return self.current_attempt_id

    def ensure_active_attempt(self) -> str:
        if not self.current_attempt_id:
            return self.start_problem_attempt()
        return self.current_attempt_id
