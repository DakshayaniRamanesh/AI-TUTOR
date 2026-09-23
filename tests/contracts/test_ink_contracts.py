import pytest
from pydantic import ValidationError
from shared.contracts.ink import InkPoint, InkStroke, InkGroup
from shared.contracts.common import CanvasBBox

def test_ink_point_valid():
    point = InkPoint(x=10.0, y=20.0, pressure=0.5, timestamp_ms=1600000000)
    assert point.pressure == 0.5
    assert point.timestamp_ms == 1600000000

def test_ink_point_pressure_constrained():
    with pytest.raises(ValidationError):
        InkPoint(x=0, y=0, pressure=1.5, timestamp_ms=1)
    with pytest.raises(ValidationError):
        InkPoint(x=0, y=0, pressure=-0.1, timestamp_ms=1)

def test_ink_stroke_default_lists_do_not_leak():
    # If a model incorrectly uses `points: List[InkPoint] = []`, appending to one 
    # stroke would append to ALL strokes because the list is evaluated at class-definition time.
    bbox = CanvasBBox(x=0, y=0, width=10, height=10)
    stroke1 = InkStroke(id="stroke_1", board_id="board_1", bbox=bbox, points=[InkPoint(x=0, y=0, timestamp_ms=0)])
    stroke2 = InkStroke(id="stroke_2", board_id="board_1", bbox=bbox, points=[InkPoint(x=0, y=0, timestamp_ms=0)])
    
    stroke1.points.append(InkPoint(x=1, y=1, timestamp_ms=1))
    assert len(stroke1.points) == 2
    assert len(stroke2.points) == 1

def test_ink_stroke_serialization():
    stroke = InkStroke(
        id="stroke_1",
        board_id="board_1",
        points=[InkPoint(x=5.0, y=5.0, timestamp_ms=1)],
        bbox=CanvasBBox(x=0, y=0, width=10, height=10)
    )
    data = stroke.model_dump()
    assert data["points"][0]["x"] == 5.0
    assert data["points"][0]["timestamp_ms"] == 1

def test_ink_group_valid():
    bbox = CanvasBBox(x=0, y=0, width=10, height=10)
    group = InkGroup(id="group_1", board_id="board_1", bbox=bbox, stroke_ids=["stroke_1"])
    assert group.id == "group_1"
