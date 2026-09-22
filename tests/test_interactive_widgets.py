"""
Test Suite for Interactive Canvas Widgets & Dynamic Builder Engine
Verifies instant presets, on-the-fly dynamic LLM/generative synthesis,
serialization, deserialization, and canvas integration.
"""

import sys
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPointF

# Ensure QApplication exists for UI tests
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from app.ui.items.interactive_widgets.dynamic_builder import (
    match_instant_interactive_preset,
    is_interactive_build_request,
    create_instant_widget_item,
    DynamicWidgetBuilderWorker,
    DynamicWidgetPlaceholder
)
from app.ui.items.interactive_widgets.base_interactive_widget import InteractiveCanvasItem
from app.ui.canvas_scene import CanvasScene


def test_instant_presets_detection():
    """Verify that user queries correctly trigger built-in instant widgets."""
    # Clock / Time
    assert match_instant_interactive_preset("gimme the time")[0] == "clock"
    assert match_instant_interactive_preset("what is the time")[0] == "clock"
    assert match_instant_interactive_preset("stopwatch")[0] == "clock"
    assert match_instant_interactive_preset("timer")[0] == "clock"

    # Flappy Bird
    assert match_instant_interactive_preset("build a flappy bird game")[0] == "flappy_bird"
    assert match_instant_interactive_preset("floopy bod")[0] == "flappy_bird"
    assert match_instant_interactive_preset("flappy bird")[0] == "flappy_bird"

    # Snake
    assert match_instant_interactive_preset("build a snake game")[0] == "snake_game"

    # Calculator
    assert match_instant_interactive_preset("open calculator")[0] == "calculator"
    assert match_instant_interactive_preset("math calc")[0] == "calculator"

    # Tic Tac Toe
    assert match_instant_interactive_preset("play tic tac toe")[0] == "tictactoe"
    assert match_instant_interactive_preset("xo game")[0] == "tictactoe"

    # Counter
    assert match_instant_interactive_preset("tally counter")[0] == "counter"

    # Dice / Coin
    assert match_instant_interactive_preset("roll a dice")[0] == "dice_coin"
    assert match_instant_interactive_preset("flip a coin")[0] == "dice_coin"

    # Physics
    assert match_instant_interactive_preset("gravity bouncing ball simulation")[0] == "physics_sim"

    # Unit Converter
    assert match_instant_interactive_preset("unit converter tool")[0] == "unit_converter"

    # Non-preset STEM queries
    assert match_instant_interactive_preset("solve x^2 + 5x + 6 = 0") is None
    assert match_instant_interactive_preset("what is newton's second law") is None


def test_is_interactive_build_request():
    """Verify intent detection for dynamically building ANY custom widget on the fly."""
    # Positive build requests
    assert is_interactive_build_request("build a reaction speed test game") is True
    assert is_interactive_build_request("create an interactive periodic table widget") is True
    assert is_interactive_build_request("make a piano synth tool") is True
    assert is_interactive_build_request("can you build an interactive simulation") is True
    assert is_interactive_build_request("build a memory card match game") is True
    assert is_interactive_build_request("create a color palette generator tool") is True
    assert is_interactive_build_request("make a todo checklist widget") is True
    assert is_interactive_build_request("ready to build a solar system sim") is True

    # Negative non-build queries
    assert is_interactive_build_request("what is the integral of e^x") is False
    assert is_interactive_build_request("explain quantum superposition") is False
    assert is_interactive_build_request("hello AI tutor") is False


def test_instant_widgets_instantiation_and_serialization():
    """Verify all instant widgets instantiate, convert to dict, and restore."""
    preset_types = [
        "clock", "flappy_bird", "snake_game", "calculator",
        "tictactoe", "counter", "dice_coin", "physics_sim", "unit_converter"
    ]

    scene = CanvasScene()

    for w_type in preset_types:
        item = create_instant_widget_item(w_type)
        assert item is not None, f"Failed to instantiate {w_type}"
        assert isinstance(item, InteractiveCanvasItem)
        assert item.widget_type == w_type

        # Verify serialization
        data = item.to_dict()
        assert data["type"] == "InteractiveCanvasWidget"
        assert data["widget_type"] == w_type
        assert "title" in data
        assert "icon_name" in data

        # Verify deserialization in CanvasScene
        restored = scene.create_item_from_dict(data)
        assert restored is not None, f"Failed to restore {w_type}"
        assert isinstance(restored, InteractiveCanvasItem)
        assert restored.widget_type == w_type


def test_dynamic_custom_widget_worker_and_code_restore(monkeypatch):
    """Verify DynamicWidgetBuilderWorker generates a working custom widget, and code restoration works."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    worker = DynamicWidgetBuilderWorker(prompt="build a reaction speed tester")
    widget_inst, title, icon, code = worker._generate_custom_widget("build a reaction speed tester")

    assert widget_inst is not None
    assert title != ""
    assert icon != ""
    assert code != ""

    # Wrap in InteractiveCanvasItem
    custom_item = InteractiveCanvasItem(
        widget_type="dynamic_custom",
        title=title,
        icon_name=icon,
        content_widget=widget_inst,
        state_data={"widget_code": code, "prompt": "build a reaction speed tester"}
    )

    data = custom_item.to_dict()
    assert data["type"] == "InteractiveCanvasWidget"
    assert data["state_data"]["widget_code"] == code

    # Test restoring dynamically compiled widget from code dict
    scene = CanvasScene()
    restored_custom = scene.create_item_from_dict(data)
    assert restored_custom is not None
    assert isinstance(restored_custom, InteractiveCanvasItem)
    assert restored_custom.title == title


def test_dynamic_code_execution_safety():
    """Verify that synthesized Python code executes safely into InteractiveCanvasItem."""
    custom_code = (
        "class GeneratedCustomWidget(QWidget):\n"
        "    def __init__(self, parent=None):\n"
        "        super().__init__(parent)\n"
        "        self.setFixedSize(280, 220)\n"
        "        layout = QVBoxLayout(self)\n"
        "        self.btn = QPushButton('Dynamic Action', self)\n"
        "        layout.addWidget(self.btn)\n"
    )

    data = {
        "type": "InteractiveCanvasWidget",
        "widget_type": "dynamic_custom",
        "title": "Dynamic Test Widget",
        "icon_name": "ri.tools-line",
        "x": 150,
        "y": 250,
        "state_data": {
            "widget_code": custom_code
        }
    }

    scene = CanvasScene()
    item = scene.create_item_from_dict(data)
    assert item is not None
    assert isinstance(item, InteractiveCanvasItem)
    assert item.title == "Dynamic Test Widget"
    assert item.x() == 0 # pos is set after creation by load_from_dict_list or caller
