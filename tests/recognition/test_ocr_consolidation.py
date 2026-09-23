import pytest
from unittest.mock import MagicMock
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication

from app.ui.canvas_scene import CanvasScene
from app.ui.main_window import MainWindow
from app.ui.items.ink_stroke import InkStroke
from shared.contracts.recognition import RecognitionRequest, RecognitionResult
from shared.contracts.tutoring import EngineFailure

@pytest.fixture
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_empty_recognition_returns_failure(qt_app):
    from app.workers.recognition_worker import RecognitionWorker
    from app.services.recognition.recognizer import Recognizer
    
    mock_recognizer = MagicMock(spec=Recognizer)
    # Return empty plain_text to simulate whitespace-only success
    mock_recognizer.recognize.return_value = RecognitionResult(
        request_id="test",
        status="SUCCESS",
        provider_name="groq",
        plain_text="   ",
        source_stroke_ids=["s1"]
    )
    
    req = RecognitionRequest(
        request_id="test", board_id="b", learning_session_id="s", stroke_group_id="g", image_b64="img"
    )
    
    worker = RecognitionWorker(mock_recognizer, req)
    
    success_spy = MagicMock()
    failure_spy = MagicMock()
    
    worker.success_emitted.connect(success_spy)
    worker.failure_emitted.connect(failure_spy)
    
    worker.run() # call synchronously
    
    success_spy.assert_not_called()
    assert failure_spy.call_count == 1
    failure_obj = failure_spy.call_args[0][0]
    assert isinstance(failure_obj, EngineFailure)
    assert failure_obj.technical_details == "Empty or whitespace-only response from provider."

def test_valid_recognition_returns_success(qt_app):
    from app.workers.recognition_worker import RecognitionWorker
    from app.services.recognition.recognizer import Recognizer
    
    mock_recognizer = MagicMock(spec=Recognizer)
    mock_recognizer.recognize.return_value = RecognitionResult(
        request_id="test",
        status="SUCCESS",
        provider_name="groq",
        plain_text="x = 2",
        source_stroke_ids=["s1"]
    )
    
    req = RecognitionRequest(
        request_id="test", board_id="b", learning_session_id="s", stroke_group_id="g", image_b64="img"
    )
    
    worker = RecognitionWorker(mock_recognizer, req)
    
    success_spy = MagicMock()
    failure_spy = MagicMock()
    
    worker.success_emitted.connect(success_spy)
    worker.failure_emitted.connect(failure_spy)
    
    worker.run()
    
    failure_spy.assert_not_called()
    assert success_spy.call_count == 1
    success_obj = success_spy.call_args[0][0]
    assert isinstance(success_obj, RecognitionResult)
    assert success_obj.plain_text == "x = 2"

def test_canvas_scene_exactly_once_submission(qt_app):
    scene = CanvasScene()
    scene._ocr_in_flight = False
    
    stroke = InkStroke()
    scene.addItem(stroke)
    scene._recent_ink_strokes.append(stroke)
    
    spy = MagicMock()
    scene.recognition_requested.connect(spy)
    
    # First trigger should succeed and emit
    res1 = scene.trigger_ai_on_dirty_ink()
    assert res1 is True
    assert spy.call_count == 1
    
    # Second trigger should fail because in_flight is True
    res2 = scene.trigger_ai_on_dirty_ink()
    assert res2 is False
    assert spy.call_count == 1 # still 1
    
    # Original strokes must remain in the scene array or at least not be deleted from the QGraphicsScene.
    # trigger_ai_on_dirty_ink clears the recent array, but not the items themselves.
    assert len(scene._recent_ink_strokes) == 0

