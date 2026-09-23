from abc import ABC, abstractmethod
from typing import Union
from shared.contracts.recognition import RecognitionRequest, RecognitionResult
from shared.contracts.tutoring import EngineFailure

class ProviderClient(ABC):
    @abstractmethod
    def execute(self, image_b64: str) -> dict:
        """Executes a recognition request against an external provider."""
        pass

class Recognizer(ABC):
    @abstractmethod
    def recognize(self, request: RecognitionRequest) -> Union[RecognitionResult, EngineFailure]:
        """Processes a recognition request and returns either a success/ambiguous result, or a structured failure."""
        pass
