"""
Interactive Canvas Widgets Package
Embedded mini-apps, tools, and games that live directly on the Kestrel whiteboard canvas.
"""

from .base_interactive_widget import InteractiveCanvasItem, InteractiveCardContainer
from .clock_widget import InteractiveClockWidget
from .flappy_bird_widget import FlappyBirdGameWidget
from .snake_game_widget import SnakeGameWidget
from .calculator_widget import InteractiveCalculatorWidget
from .tictactoe_widget import TicTacToeWidget
from .counter_widget import InteractiveCounterWidget
from .dice_coin_widget import InteractiveDiceCoinWidget
from .physics_sim_widget import PhysicsSimWidget
from .unit_converter_widget import UnitConverterWidget
from .dynamic_builder import (
    match_instant_interactive_preset,
    create_instant_widget_item,
    is_interactive_build_request,
    DynamicWidgetPlaceholder,
    DynamicWidgetBuilderWorker
)

__all__ = [
    "InteractiveCanvasItem",
    "InteractiveCardContainer",
    "InteractiveClockWidget",
    "FlappyBirdGameWidget",
    "SnakeGameWidget",
    "InteractiveCalculatorWidget",
    "TicTacToeWidget",
    "InteractiveCounterWidget",
    "InteractiveDiceCoinWidget",
    "PhysicsSimWidget",
    "UnitConverterWidget",
    "match_instant_interactive_preset",
    "create_instant_widget_item",
    "is_interactive_build_request",
    "DynamicWidgetPlaceholder",
    "DynamicWidgetBuilderWorker",
]
