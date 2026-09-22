import sys
import pytest
from pydantic import ValidationError, BaseModel
from shared.contracts.common import (
    CanvasBBox,
    CoordinateSpace,
    CURRENT_SCHEMA_VERSION,
    StableId,
)

def test_valid_canvas_bbox():
    bbox = CanvasBBox(x=10.5, y=-5.0, width=100.0, height=50.0)
    assert bbox.x == 10.5
    assert bbox.y == -5.0
    assert bbox.width == 100.0
    assert bbox.height == 50.0
    assert bbox.coordinate_space == "SCENE"
    assert bbox.schema_version == CURRENT_SCHEMA_VERSION

def test_default_coordinate_space():
    bbox = CanvasBBox(x=0, y=0, width=10, height=10)
    assert bbox.coordinate_space == "SCENE"

def test_negative_dimensions_rejected():
    with pytest.raises(ValidationError):
        CanvasBBox(x=0, y=0, width=-1.0, height=10.0)
    with pytest.raises(ValidationError):
        CanvasBBox(x=0, y=0, width=10.0, height=-5.0)

def test_nan_rejected():
    with pytest.raises(ValidationError):
        CanvasBBox(x=float('nan'), y=0, width=10, height=10)

def test_inf_rejected():
    with pytest.raises(ValidationError):
        CanvasBBox(x=0, y=float('inf'), width=10, height=10)

def test_unsupported_coordinate_space():
    with pytest.raises(ValidationError):
        CanvasBBox(x=0, y=0, width=10, height=10, coordinate_space="UNIVERSE")

def test_unknown_fields_rejected():
    with pytest.raises(ValidationError):
        CanvasBBox(x=0, y=0, width=10, height=10, color="red")

def test_assignment_validation():
    bbox = CanvasBBox(x=0, y=0, width=10, height=10)
    with pytest.raises(ValidationError):
        bbox.width = -5.0

def test_json_serialization_round_trip():
    bbox = CanvasBBox(x=10, y=20, width=30, height=40, coordinate_space=CoordinateSpace.SCREEN)
    json_data = bbox.model_dump_json()
    
    assert CURRENT_SCHEMA_VERSION in json_data
    assert "SCREEN" in json_data
    
    restored = CanvasBBox.model_validate_json(json_data)
    assert restored.x == 10
    assert restored.width == 30
    assert restored.coordinate_space == "SCREEN"
    assert restored.schema_version == CURRENT_SCHEMA_VERSION

def test_stable_id_validation():
    class TestModel(BaseModel):
        id: StableId
    
    # Valid prefixed IDs
    assert TestModel(id="nb_12345").id == "nb_12345"
    assert TestModel(id="board_main").id == "board_main"
    
    # Empty or whitespace only rejected
    with pytest.raises(ValidationError):
        TestModel(id="")
    with pytest.raises(ValidationError):
        TestModel(id="   ")

def test_no_forbidden_imports():
    import shared.contracts.common
    assert "PyQt6" not in sys.modules, "PyQt6 leaked into shared contracts!"
    assert "sqlalchemy" not in sys.modules, "SQLAlchemy leaked into shared contracts!"
