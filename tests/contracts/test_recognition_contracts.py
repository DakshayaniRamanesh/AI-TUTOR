import pytest
from pydantic import ValidationError
from shared.contracts.recognition import (
    RecognitionResult, 
    RecognitionStatus, 
    ContentType, 
    RecognitionAlternative
)

def test_valid_recognition_result():
    res = RecognitionResult(
        request_id="req_123",
        board_id="board",
        group_id="group",
        group_revision=1,
        status=RecognitionStatus.SUCCESS,
        content_type=ContentType.EQUATION,
        latex="x^2 + y = 10",
        confidence=0.95,
        provider_name="groq_vision",
        source_stroke_ids=["stroke_1"]
    )
    assert res.status == "SUCCESS"
    assert res.latex == "x^2 + y = 10"

def test_confidence_constrained():
    with pytest.raises(ValidationError):
        RecognitionResult(
            request_id="req_1",
            status=RecognitionStatus.SUCCESS,
            provider_name="groq",
            confidence=1.5
        )

    with pytest.raises(ValidationError):
        RecognitionAlternative(text="5", confidence=-0.1)

def test_enum_rejection():
    with pytest.raises(ValidationError):
        RecognitionResult(
            request_id="req_1",
            status="KINDA_WORKED", 
            provider_name="groq"
        )

def test_ambiguous_result_with_alternatives():
    res = RecognitionResult(
        request_id="req_2",
        board_id="board",
        group_id="group",
        group_revision=1,
        source_stroke_ids=["stroke_1"],
        status=RecognitionStatus.AMBIGUOUS,
        content_type=ContentType.UNKNOWN,
        provider_name="gemini",
        alternatives=[
            RecognitionAlternative(text="S", confidence=0.55),
            RecognitionAlternative(text="5", confidence=0.45)
        ]
    )
    assert len(res.alternatives) == 2
    assert res.alternatives[0].text == "S"
