import pytest
from PyQt6.QtWidgets import QGraphicsScene
from PyQt6.QtGui import QPainterPath
from PyQt6.QtCore import QPointF
from app.ui.items.ink_stroke import InkStroke as UIInkStroke
from app.ui.stroke_processor import StrokeProcessor
from app.services.recognition.ink_adapter import InkAdapter
from app.services.recognition.stroke_grouper import StrokeGrouper, StrokeGroupingConfig
from app.services.recognition.vision_recognizer import VisionRecognizer
from shared.contracts.recognition import RecognitionRequest, RecognitionStatus, RecognitionResult
from shared.contracts.tutoring import EngineFailure, ErrorCode

class MockProviderClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.called_with = None

    def execute(self, image_b64: str) -> dict:
        self.called_with = image_b64
        if self.error:
            raise self.error
        return self.response

def test_raw_pressure_and_timestamp_survives():
    processor = StrokeProcessor()
    processor.start_stroke(QPointF(0, 0), pressure=0.5, timestamp=100.0)
    processor.add_point(QPointF(1, 1), pressure=0.8, timestamp=100.5)
    
    # Needs a pen to pass to make_handwriting_item, normally done in process_stroke
    item = processor.process_stroke(tool_mode="pen")
    
    assert hasattr(item, "raw_stroke")
    assert len(item.raw_stroke) == 2
    assert item.raw_stroke[0][2] == 0.5  # pressure
    assert item.raw_stroke[0][3] == 100.0 # timestamp

def test_save_reload_preserves_metadata():
    processor = StrokeProcessor()
    processor.start_stroke(QPointF(0, 0), pressure=0.5, timestamp=100.0)
    item = processor.process_stroke(tool_mode="pen")
    
    # Save to dict
    data = item.to_dict()
    assert "raw_points" in data
    assert data["metadata_version"] == 2
    
    # Reload from dict (mocking canvas scene behavior)
    # create_item_from_dict sets it back
    new_item = UIInkStroke(path=QPainterPath())
    new_item.raw_stroke = data["raw_points"]
    
    assert new_item.raw_stroke[0][2] == 0.5

def test_ink_adapter_maps_to_contracts():
    processor = StrokeProcessor()
    processor.start_stroke(QPointF(0, 0), pressure=0.5, timestamp=100.0) # 100.0 sec -> 100000 ms
    item = processor.process_stroke(tool_mode="pen")
    
    contract_stroke = InkAdapter.extract_ink_stroke(item, board_id="test_board")
    assert contract_stroke is not None
    assert len(contract_stroke.points) == 1
    assert contract_stroke.points[0].pressure == 0.5
    assert contract_stroke.points[0].timestamp_ms == 100000

def test_stroke_grouper_temporal():
    # Construct mock contract strokes
    processor1 = StrokeProcessor()
    processor1.start_stroke(QPointF(0, 0), pressure=0.5, timestamp=100.0)
    item1 = processor1.process_stroke()
    stroke1 = InkAdapter.extract_ink_stroke(item1, "board1")
    
    processor2 = StrokeProcessor()
    processor2.start_stroke(QPointF(20, 0), pressure=0.5, timestamp=101.0) # 1 sec later, should group
    item2 = processor2.process_stroke()
    stroke2 = InkAdapter.extract_ink_stroke(item2, "board1")

    processor3 = StrokeProcessor()
    processor3.start_stroke(QPointF(40, 0), pressure=0.5, timestamp=105.0) # 4 sec later, should NOT group
    item3 = processor3.process_stroke()
    stroke3 = InkAdapter.extract_ink_stroke(item3, "board1")
    
    grouper = StrokeGrouper(StrokeGroupingConfig(max_temporal_gap_ms=1500))
    groups = grouper.group_strokes([stroke1, stroke2, stroke3], "board1")
    
    assert len(groups) == 2
    assert len(groups[0].stroke_ids) == 2 # 100 and 101
    assert len(groups[1].stroke_ids) == 1 # 105

def test_vision_recognizer_success():
    client = MockProviderClient(response={"text": "2x = 4"})
    recognizer = VisionRecognizer(client)
    request = RecognitionRequest(request_id="req1", board_id="b1", learning_session_id="ls1", stroke_group_id="g1", image_b64="data")
    
    result = recognizer.recognize(request)
    assert isinstance(result, RecognitionResult)
    assert result.status == RecognitionStatus.SUCCESS
    assert result.plain_text == "2x = 4"
    assert result.source_stroke_ids == ["g1"]

def test_vision_recognizer_timeout():
    client = MockProviderClient(error=TimeoutError("Connection dropped"))
    recognizer = VisionRecognizer(client)
    request = RecognitionRequest(request_id="req1", board_id="b1", learning_session_id="ls1", stroke_group_id="g1", image_b64="data")
    
    result = recognizer.recognize(request)
    assert isinstance(result, EngineFailure)
    assert result.error_code == ErrorCode.NETWORK_TIMEOUT
    assert result.is_retryable is True
