from typing import Union
import json
from shared.contracts.recognition import (
    RecognitionRequest,
    RecognitionResult,
    RecognitionStatus,
    ContentType,
    RecognitionAlternative
)
from shared.contracts.tutoring import EngineFailure, ErrorCode
from .recognizer import Recognizer, ProviderClient

class LegacyProviderClient(ProviderClient):
    """Temporary bridge to the legacy handwriting OCR module."""
    def __init__(self, stroke_count: int = 1):
        self.stroke_count = stroke_count
        
    def execute(self, image_b64: str) -> dict:
        # We don't actually use the image right now in the legacy mock
        from app.services.recognition.handwriting_ocr import recognize_handwriting
        text = recognize_handwriting(stroke_count=self.stroke_count)
        return {"text": text}

class RealProviderClient(ProviderClient):
    """Bridge to the real handwriting OCR module (Groq/Gemini)."""
    def execute(self, image_b64: str) -> dict:
        import requests
        from app.services.recognition.handwriting_ocr import recognize_handwriting
        try:
            # Pass the actual base64 image to the backend
            text = recognize_handwriting(b64_image=image_b64)
            return {"text": text}
        except requests.exceptions.Timeout as e:
            raise TimeoutError(str(e))
        except RuntimeError as e:
            raise ValueError(str(e))

class VisionRecognizer(Recognizer):
    def __init__(self, client: ProviderClient):
        self.client = client

    def recognize(self, request: RecognitionRequest) -> Union[RecognitionResult, EngineFailure]:
        if not request.image_b64:
            return EngineFailure(
                request_id=request.request_id,
                provider_name="unknown",
                error_code=ErrorCode.INVALID_REQUEST,
                user_message="No image provided for recognition.",
                technical_details="image_b64 is empty.",
                is_retryable=False
            )

        try:
            raw_data = self.client.execute(request.image_b64)
            return self._parse_success(raw_data, request)
        except TimeoutError as e:
            return EngineFailure(
                request_id=request.request_id,
                provider_name="vision_provider",
                error_code=ErrorCode.NETWORK_TIMEOUT,
                user_message="The recognition service timed out. Please try again.",
                technical_details=str(e),
                is_retryable=True
            )
        except ValueError as e:
            return EngineFailure(
                request_id=request.request_id,
                provider_name="vision_provider",
                error_code=ErrorCode.PARSE_FAILED,
                user_message="We couldn't understand the recognition result.",
                technical_details=str(e),
                is_retryable=False
            )
        except Exception as e:
            return EngineFailure(
                request_id=request.request_id,
                provider_name="vision_provider",
                error_code=ErrorCode.INTERNAL_ERROR,
                user_message="An unexpected error occurred during recognition.",
                technical_details=str(e),
                is_retryable=False
            )

    def _parse_success(self, raw_data: dict, request: RecognitionRequest) -> RecognitionResult:
        # Assuming raw_data contains 'text' or 'latex' from the legacy OCR wrapper
        text = raw_data.get('text', '').strip()
        if not text:
            raise ValueError("Provider returned empty text.")

        # For simplicity, treating as successful math equation if it contains math-like chars,
        # or just passing it back. In a real scenario, this would map the provider's specific JSON structure.
        return RecognitionResult(
            request_id=request.request_id,
            status=RecognitionStatus.SUCCESS,
            content_type=ContentType.EQUATION,
            plain_text=text,
            latex=text,
            confidence=1.0, # Placeholder, legacy didn't provide confidence
            source_stroke_ids=request.source_stroke_ids, # Resolved to actual stroke IDs
            provider_name="vision_provider",
            alternatives=[RecognitionAlternative(text=text, confidence=1.0)]
        )
