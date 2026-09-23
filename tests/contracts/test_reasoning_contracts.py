import pytest
from pydantic import ValidationError
from shared.contracts.reasoning import (
    CanvasAnchor, 
    ReasoningStepInput, 
    ValidationResult, 
    ValidationVerdict
)
from shared.contracts.common import CanvasBBox

def test_canvas_anchor_preserves_data():
    bbox = CanvasBBox(x=0, y=0, width=50, height=50)
    anchor = CanvasAnchor(
        item_ids=["stroke_99"],
        board_id="board_main",
        bbox_snapshot=bbox
    )
    assert len(anchor.item_ids) == 1
    assert anchor.item_ids[0] == "stroke_99"
    assert anchor.bbox_snapshot.width == 50
    assert anchor.coordinate_space == "SCENE"

def test_verdict_is_required():
    with pytest.raises(ValidationError):
        ValidationResult(
            step_id="step_1",
            explanation="Failed to parse student handwriting."
        )

def test_verdict_enum_rejection():
    with pytest.raises(ValidationError):
        ValidationResult(step_id="step_2", verdict="KINDA_RIGHT")
        
def test_valid_verdict_accepted():
    result = ValidationResult(step_id="step_3", verdict=ValidationVerdict.VALID)
    assert result.verdict == "VALID"
