from enum import Enum
from shared.contracts.recognition import RecognitionResult, ContentType
from shared.contracts.tutoring import EngineFailure, ErrorCode

class RouteTarget(Enum):
    MATH_ENGINE = "MATH_ENGINE"
    DIAGRAM_BUILDER = "DIAGRAM_BUILDER"
    TEXT_ASSISTANT = "TEXT_ASSISTANT"
    IGNORE = "IGNORE"

class ContentRouter:
    """Deterministically routes recognized content to the appropriate engine."""
    
    @staticmethod
    def route(result: RecognitionResult) -> RouteTarget:
        if result.content_type == ContentType.EQUATION:
            return RouteTarget.MATH_ENGINE
        elif result.content_type == ContentType.DIAGRAM:
            return RouteTarget.DIAGRAM_BUILDER
        elif result.content_type == ContentType.TEXT:
            return RouteTarget.TEXT_ASSISTANT
        else:
            return RouteTarget.IGNORE
