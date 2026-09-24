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
        # Mock legacy behavior
        return {
            "text": "3x = 12",
            "latex": "3x = 12",
            "content_type": "EQUATION",
            "confidence": 0.9
        }

class RealProviderClient(ProviderClient):
    """Bridge to the real handwriting OCR module (Groq/Gemini)."""
    def execute(self, image_b64: str) -> dict:
        import requests
        from app.services.recognition.handwriting_ocr import recognize_handwriting
        try:
            # Pass the actual base64 image to the backend
            result_dict = recognize_handwriting(b64_image=image_b64)
            return result_dict
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
        text = raw_data.get('text', '').strip()
        latex = raw_data.get('latex', '').strip() or text
        content_type_str = raw_data.get('content_type', 'UNKNOWN')
        confidence = raw_data.get('confidence', 0.8)
        
        try:
            content_type = ContentType(content_type_str)
        except ValueError:
            content_type = ContentType.UNKNOWN

        if not text:
            raise ValueError("Provider returned empty text.")

        return RecognitionResult(
            request_id=request.request_id,
            board_id=request.board_id,
            status=RecognitionStatus.SUCCESS,
            content_type=content_type,
            plain_text=text,
            latex=latex,
            confidence=confidence,
            source_stroke_ids=request.source_stroke_ids,
            group_id=request.group_id,
            group_revision=request.group_revision,
            group_bbox=request.group_bbox,
            provider_name="vision_provider",
            alternatives=[RecognitionAlternative(text=text, latex=latex, confidence=confidence)]
        )
