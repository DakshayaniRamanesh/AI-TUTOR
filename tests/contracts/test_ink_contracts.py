import pytest
from pydantic import ValidationError
from shared.contracts.ink import InkPoint, InkStroke, InkGroup
from shared.contracts.common import CanvasBBox, CoordinateSpace

def test_ink_point_valid():
    point = InkPoint(x=10.0, y=20.0, pressure=0.5, timestamp=1600000000.0)
    assert point.pressure == 0.5
    assert point.x == 10.0

def test_ink_point_pressure_constrained():
    with pytest.raises(ValidationError):
        InkPoint(x=10.0, y=20.0, pressure=1.5, timestamp=1600000000.0)
    with pytest.raises(ValidationError):
        InkPoint(x=10.0, y=20.0, pressure=-0.1, timestamp=1600000000.0)

def test_ink_stroke_default_lists_do_not_leak():
    # If a model incorrectly uses `points: List[InkPoint] = []`, appending to one 
    # stroke would append to ALL strokes because the list is evaluated at class-definition time.
    bbox = CanvasBBox(x=0, y=0, width=10, height=10)
    stroke1 = InkStroke(id="stroke_1", board_id="board_1", bbox=bbox)
    stroke2 = InkStroke(id="stroke_2", board_id="board_1", bbox=bbox)
    
    stroke1.points.append(InkPoint(x=0, y=0, timestamp=0))
    assert len(stroke1.points) == 1
    assert len(stroke2.points) == 0

def test_ink_stroke_serialization():
    stroke = InkStroke(
        id="stroke_1",
        board_id="board_1",
        points=[InkPoint(x=5.0, y=5.0, timestamp=1.0)],
        bbox=CanvasBBox(x=0, y=0, width=10, height=10)
    )
    json_data = stroke.model_dump_json()
    assert "stroke_1" in json_data
    
    restored = InkStroke.model_validate_json(json_data)
    assert restored.id == "stroke_1"
    assert len(restored.points) == 1
    assert restored.bbox.coordinate_space == CoordinateSpace.SCENE

def test_ink_group_valid():
    group = InkGroup(
        id="group_1",
        board_id="board_1",
        stroke_ids=["stroke_1", "stroke_2"],
        bbox=CanvasBBox(x=0, y=0, width=20, height=20)
    )
    assert len(group.stroke_ids) == 2
