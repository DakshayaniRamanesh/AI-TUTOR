"""
Unit and integration tests for Developer 1: Visual and Audio Canvas Studio.
Tests:
- LaserPointerItem instantiation, properties, bounds, transit animation.
- GhostChalkItem instantiation, modes (ERROR vs VERIFIED), progress property.
- VoiceSpeaker singleton, rate/volume/pitch configuration, non-blocking speak and stop.
- SocraticHintBubble 3-level progressive disclosure logic.
- CanvasScene integration of show_tutor_feedback and clear_tutor_feedback.
"""

import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPointF, QRectF

# Ensure single QApplication exists for tests
app = QApplication.instance() or QApplication([])

from app.ui.items.laser_pointer_item import LaserPointerItem
from app.ui.items.ghost_chalk_item import GhostChalkItem, GhostChalkMode
from app.ui.audio.voice_speaker import VoiceSpeaker
from app.ui.widgets.socratic_hint_bubble import SocraticHintBubble
from app.ui.canvas_scene import CanvasScene


def test_laser_pointer_initialization_and_properties():
    item = LaserPointerItem()
    assert item.zValue() == 1000
    assert item.get_pulse_opacity() == 0.95
    assert item.get_scale_factor() == 1.0

    # Test property setters
    item.set_pulse_opacity(0.7)
    assert item.get_pulse_opacity() == 0.7
    item.set_scale_factor(1.2)
    assert item.get_scale_factor() == 1.2

    # Test bounding rect
    rect = item.boundingRect()
    assert rect.width() > 0 and rect.height() > 0
    assert rect.contains(QPointF(0, 0))


def test_laser_pointer_movement():
    item = LaserPointerItem()
    target = QPointF(400, 300)
    item.move_to(target, duration_ms=10)
    app.processEvents()
    assert item._move_anim is not None


def test_ghost_chalk_initialization_and_modes():
    test_rect = QRectF(200, 150, 120, 50)
    item = GhostChalkItem(test_rect, mode=GhostChalkMode.ERROR)
    assert item._mode == GhostChalkMode.ERROR
    assert item.get_progress() == 0.0

    # Check progress update
    item.set_progress(0.5)
    assert item.get_progress() == 0.5

    # Switch to verified mode
    item.set_target_rect(test_rect, mode=GhostChalkMode.VERIFIED)
    assert item._mode == GhostChalkMode.VERIFIED


def test_voice_speaker_singleton_and_controls():
    speaker = VoiceSpeaker.instance()
    assert speaker is not None
    assert VoiceSpeaker.instance() is speaker

    # Test configuration
    speaker.set_rate(1.0)
    speaker.set_pitch(0.0)
    speaker.set_volume(0.8)

    # Test non-blocking speak & stop
    speaker.speak("Testing voice copilot audio")
    speaker.stop()
    assert not speaker.is_speaking()


def test_socratic_hint_bubble_progressive_disclosure():
    bubble = SocraticHintBubble()
    assert bubble._current_level == 0
    assert bubble.hint_box.isHidden()

    # Click Need a Hint? Level 1
    bubble._on_need_hint_clicked()
    assert bubble._current_level == 1
    assert not bubble.hint_box.isHidden()
    assert "LEVEL 1" in bubble.lbl_hint_badge.text()

    # Click Level 2
    bubble._on_need_hint_clicked()
    assert bubble._current_level == 2
    assert "LEVEL 2" in bubble.lbl_hint_badge.text()

    # Click Level 3
    bubble._on_need_hint_clicked()
    assert bubble._current_level == 3
    assert "LEVEL 3" in bubble.lbl_hint_badge.text()
    assert not bubble.btn_hint.isEnabled()

    # Reset
    bubble.reset_hints()
    assert bubble._current_level == 0
    assert bubble.hint_box.isHidden()
    assert bubble.btn_hint.isEnabled()


def test_canvas_scene_tutor_feedback_lifecycle():
    scene = CanvasScene()
    target_rect = QRectF(100, 100, 120, 40)
    
    scene.show_tutor_feedback(
        target_rect=target_rect,
        spoken_message="Test message",
        citation="Test Book, §1.1, p.10",
        hints=["Hint 1", "Hint 2"],
        mode="error"
    )

    assert scene._laser_pointer_item is not None
    assert scene._ghost_chalk_item is not None
    assert scene._socratic_hint_bubble is not None
    assert scene._laser_pointer_item.isVisible()
    assert scene._ghost_chalk_item.isVisible()

    # Clear feedback
    scene.clear_tutor_feedback()
    assert not scene._laser_pointer_item.isVisible()
    assert not scene._ghost_chalk_item.isVisible()


def test_render_canvas_to_b64():
    from app.ui.penecho_integration.export_utils import render_canvas_to_b64
    from PyQt6.QtWidgets import QGraphicsTextItem

    scene = CanvasScene()
    # Empty canvas returns empty string
    assert render_canvas_to_b64(scene) == ""

    # Canvas with content renders valid base64 PNG
    text_item = QGraphicsTextItem("x + 5 = 10")
    text_item.setPos(50, 50)
    scene.addItem(text_item)

    b64 = render_canvas_to_b64(scene)
    assert b64 != ""
    assert isinstance(b64, str)
    # Validate base64 decode
    import base64
    raw_bytes = base64.b64decode(b64)
    # Check PNG signature: \x89PNG\r\n\x1a\n
    assert raw_bytes.startswith(b"\x89PNG\r\n\x1a\n")
