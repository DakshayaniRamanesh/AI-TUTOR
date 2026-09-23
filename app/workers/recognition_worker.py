from PyQt6.QtCore import QThread, pyqtSignal
from shared.contracts.recognition import RecognitionRequest, RecognitionResult
from shared.contracts.tutoring import EngineFailure
from app.services.recognition.recognizer import Recognizer

class RecognitionWorker(QThread):
    success_emitted = pyqtSignal(RecognitionResult)
    failure_emitted = pyqtSignal(EngineFailure)

    def __init__(self, recognizer: Recognizer, request: RecognitionRequest, parent=None):
        super().__init__(parent)
        # State isolated immediately (no UI widget references)
        self.recognizer = recognizer
        self.request = request

    def run(self):
        # Executes outside GUI thread
        result = self.recognizer.recognize(self.request)
        
        # Emits structured payloads
        if isinstance(result, RecognitionResult):
            if not result.plain_text or not result.plain_text.strip():
                failure = EngineFailure(
                    request_id=self.request.request_id,
                    provider_name=result.provider_name or "unknown",
                    user_message="No handwriting detected or text is empty.",
                    technical_details="Empty or whitespace-only response from provider."
                )
                self.failure_emitted.emit(failure)
            else:
                self.success_emitted.emit(result)
        elif isinstance(result, EngineFailure):
            self.failure_emitted.emit(result)
        else:
            # Fallback
            failure = EngineFailure(
                request_id=self.request.request_id,
                provider_name="unknown",
                user_message="An unexpected response type was returned.",
                technical_details=f"Received: {type(result)}",
            )
            self.failure_emitted.emit(failure)
