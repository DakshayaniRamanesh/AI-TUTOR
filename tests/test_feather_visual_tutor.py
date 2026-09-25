import pytest
import time
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPointF
from app.ui.main_window import MainWindow
from app.ui.items.answer_bubble import AnswerBubble
from app.ui.items.video_float_item import VideoFloatItem
from app.ui.widgets.feather_ai_button import FeatherAIButton
from shared.ai_client import ai_client

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

@pytest.fixture
def main_window(qapp):
    win = MainWindow()
    win.show()
    return win

def test_explicit_feather_no_longer_calls_dirty_ink(main_window, monkeypatch):
    main_window.scene.trigger_ai_on_dirty_ink = MagicMock(return_value=False)
    main_window._capture_visible_canvas_for_feather = MagicMock(return_value=None)
    main_window._on_magic_orb_triggered()
    main_window.scene.trigger_ai_on_dirty_ink.assert_not_called()

def test_visual_feather_viewport_rendering_and_overlays(main_window, monkeypatch):
    bubble = AnswerBubble(title="Test", full_text="Test Text")
    main_window.scene.addItem(bubble)
    assert bubble.isVisible()
    b64_img = main_window._capture_visible_canvas_for_feather()
    assert b64_img is not None
    assert len(b64_img) > 100
    assert bubble.isVisible()

def test_visual_feather_fake_client_and_bubble_creation(main_window, monkeypatch):
    main_window.current_subject_id = "sub1"
    main_window._current_notebook_id = "nb1"
    main_window.current_attempt_id = "att1"
    main_window.scene.revision = 1
    
    main_window._capture_visible_canvas_for_feather = MagicMock(return_value="dummy_b64")
    
    mock_generate = MagicMock(return_value="This is a test response.")
    monkeypatch.setattr(ai_client, "generate_content", mock_generate)
    
    initial_bubbles = [item for item in main_window.scene.items() if isinstance(item, AnswerBubble)]
    
    main_window._on_magic_orb_triggered()
    worker = main_window._visual_feather_worker
    assert worker is not None
    
    while worker.isRunning():
        QApplication.processEvents()
        time.sleep(0.01)
    QApplication.processEvents()
    
    mock_generate.assert_called_once()
    args, kwargs = mock_generate.call_args
    assert "image_b64" in kwargs
    assert kwargs["image_b64"] is not None
    assert "system_instruction" in kwargs
    assert "You are Kestrel" in kwargs["system_instruction"]
    
    final_bubbles = [item for item in main_window.scene.items() if isinstance(item, AnswerBubble)]
    assert len(final_bubbles) == len(initial_bubbles) + 1
    new_bubble = [b for b in final_bubbles if b not in initial_bubbles][0]
    assert "This is a test response." in new_bubble.bubble.full_solution

def test_visual_feather_second_click_ignored(main_window, monkeypatch):
    def slow_generate(*args, **kwargs):
        time.sleep(0.1)
        return "Slow response"
    
    main_window._capture_visible_canvas_for_feather = MagicMock(return_value="dummy_b64")
    monkeypatch.setattr(ai_client, "generate_content", slow_generate)
    main_window._on_magic_orb_triggered()
    worker1 = main_window._visual_feather_worker
    assert worker1 is not None
    
    main_window._on_magic_orb_triggered()
    worker2 = main_window._visual_feather_worker
    assert worker1 is worker2
    while worker1.isRunning():
        QApplication.processEvents()
        time.sleep(0.01)
    QApplication.processEvents()

def test_visual_feather_stale_result_discarded(main_window, monkeypatch):
    main_window.current_subject_id = "sub1"
    main_window.scene.revision = 1
    
    main_window._capture_visible_canvas_for_feather = MagicMock(return_value="dummy_b64")
    
    mock_generate = MagicMock(return_value="This is a test response.")
    monkeypatch.setattr(ai_client, "generate_content", mock_generate)
    
    initial_bubbles_count = len([item for item in main_window.scene.items() if isinstance(item, AnswerBubble)])
    
    main_window._on_magic_orb_triggered()
    worker = main_window._visual_feather_worker
    
    main_window.scene.revision = 2
    
    while worker.isRunning():
        QApplication.processEvents()
        time.sleep(0.01)
    QApplication.processEvents()
    
    final_bubbles_count = len([item for item in main_window.scene.items() if isinstance(item, AnswerBubble)])
    assert final_bubbles_count == initial_bubbles_count
    assert main_window._visual_feather_worker is None

def test_visual_feather_failure_restores_state(main_window, monkeypatch):
    main_window.current_subject_id = "sub1"
    
    main_window._capture_visible_canvas_for_feather = MagicMock(return_value="dummy_b64")
    
    def failing_generate(*args, **kwargs):
        raise ValueError("API Error")
    monkeypatch.setattr(ai_client, "generate_content", failing_generate)
    
    main_window.magic_orb.set_state = MagicMock()
    
    main_window._on_magic_orb_triggered()
    worker = main_window._visual_feather_worker
    
    while worker.isRunning():
        QApplication.processEvents()
        time.sleep(0.01)
    QApplication.processEvents()
    
    assert main_window._visual_feather_worker is None
    main_window.magic_orb.set_state.assert_called_with("error", "Kestrel could not analyze the canvas. Check the AI connection and try again.")

def test_automatic_timeout_still_calls_auto_check(main_window):
    main_window.scene.trigger_ai_on_dirty_ink = MagicMock()
    main_window.scene._on_auto_ai_timeout()
    main_window.scene.trigger_ai_on_dirty_ink.assert_called_once_with(is_auto_check=True)
