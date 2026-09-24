from app.services.recognition.content_router import ContentRouter, RouteTarget
from shared.contracts.recognition import RecognitionResult, RecognitionStatus, ContentType, RecognitionAlternative

def create_result(content_type: ContentType) -> RecognitionResult:
    return RecognitionResult(
        request_id="test",
        board_id="board",
        group_id="group",
        group_revision=1,
        status=RecognitionStatus.SUCCESS,
        content_type=content_type,
        plain_text="dummy",
        latex="dummy",
        confidence=0.9,
        source_stroke_ids=["stroke1"],
        provider_name="test",
        alternatives=[RecognitionAlternative(text="dummy", confidence=0.9)]
    )

def test_content_router_equation():
    res = create_result(ContentType.EQUATION)
    assert ContentRouter.route(res) == RouteTarget.MATH_ENGINE

def test_content_router_diagram():
    res = create_result(ContentType.DIAGRAM)
    assert ContentRouter.route(res) == RouteTarget.DIAGRAM_BUILDER

def test_content_router_text():
    res = create_result(ContentType.TEXT)
    assert ContentRouter.route(res) == RouteTarget.TEXT_ASSISTANT

def test_content_router_unknown():
    res = create_result(ContentType.UNKNOWN)
    assert ContentRouter.route(res) == RouteTarget.IGNORE
