"""
Interactive Intent Detector & Spawner
Identifies when a user asks for an interactive widget or mini-app (Clock, Game, Calculator, etc.)
and generates the corresponding in-canvas interactive widget item.
"""

import re
from typing import Optional, Dict, Any

from .base_interactive_widget import InteractiveCanvasItem
from .clock_widget import InteractiveClockWidget
from .flappy_bird_widget import FlappyBirdGameWidget
from .calculator_widget import InteractiveCalculatorWidget
from .tictactoe_widget import TicTacToeWidget
from .counter_widget import InteractiveCounterWidget


INTENT_PATTERNS = [
    # 1. Clock / Time / Stopwatch / Timer
    {
        "type": "clock",
        "title": "Live Clock & Timer",
        "icon": "ri.time-line",
        "patterns": [
            r"\b(time|clock|stopwatch|timer|countdown)\b",
            r"what('?s| is) the time",
            r"gimme (the )?time",
            r"show (the )?time",
            r"current time",
            r"tell (me )?(the )?time",
        ]
    },
    # 2. Flappy Bird / Arcade Game
    {
        "type": "flappy_bird",
        "title": "Flappy Bird Arcade",
        "icon": "ri.gamepad-line",
        "patterns": [
            r"\b(flappy|floppy|bird game)\b",
            r"flappy\s*bird",
            r"floopy\s*bod",
            r"make.*game",
            r"build.*game",
            r"play.*game",
            r"arcade game",
        ]
    },
    # 3. Calculator
    {
        "type": "calculator",
        "title": "Scientific Calculator",
        "icon": "ri.calculator-line",
        "patterns": [
            r"\b(calculator|calc)\b",
            r"open calculator",
            r"show calculator",
            r"math calculator",
        ]
    },
    # 4. Tic-Tac-Toe
    {
        "type": "tictactoe",
        "title": "Tic-Tac-Toe",
        "icon": "ri.grid-line",
        "patterns": [
            r"\b(tic\s*tac\s*toe|tictactoe|xo\s*game)\b",
            r"play\s*(tic\s*tac\s*toe|xo)",
        ]
    },
    # 5. Counter / Tally
    {
        "type": "counter",
        "title": "Tally Counter",
        "icon": "ri.add-circle-line",
        "patterns": [
            r"\b(counter|tally|clicker)\b",
            r"tally\s*counter",
            r"count\s*tracker",
        ]
    },
    # 6. Dice / Coin Flipper
    {
        "type": "dice_coin",
        "title": "Dice & Coin",
        "icon": "ri.copper-coin-line",
        "patterns": [
            r"\b(dice|coin|heads or tails|flip coin|roll dice)\b",
            r"roll (a )?dice",
            r"flip (a )?coin",
        ]
    },
]


def detect_interactive_intent(query: str) -> Optional[Dict[str, Any]]:
    """
    Scans the prompt/query for interactive widget requests.
    Returns matched intent dict or None.
    """
    if not query:
        return None

    q_lower = query.lower().strip()

    for item in INTENT_PATTERNS:
        for pat in item["patterns"]:
            if re.search(pat, q_lower):
                return {
                    "type": item["type"],
                    "title": item["title"],
                    "icon": item["icon"],
                }

    return None


def spawn_interactive_widget(widget_type: str, state_data: dict = None, title: str = None, icon: str = None) -> Optional[InteractiveCanvasItem]:
    """
    Creates an InteractiveCanvasItem for the given widget_type.
    """
    from .dice_coin_widget import InteractiveDiceCoinWidget

    content = None
    default_title = "Widget"
    default_icon = "ri.apps-line"

    if widget_type == "clock":
        content = InteractiveClockWidget()
        default_title = "Live Clock & Timer"
        default_icon = "ri.time-line"
    elif widget_type == "flappy_bird":
        content = FlappyBirdGameWidget()
        default_title = "Flappy Bird Arcade"
        default_icon = "ri.gamepad-line"
    elif widget_type == "calculator":
        content = InteractiveCalculatorWidget()
        default_title = "Calculator"
        default_icon = "ri.calculator-line"
    elif widget_type == "tictactoe":
        content = TicTacToeWidget()
        default_title = "Tic-Tac-Toe"
        default_icon = "ri.grid-line"
    elif widget_type == "counter":
        content = InteractiveCounterWidget()
        default_title = "Tally Counter"
        default_icon = "ri.add-circle-line"
    elif widget_type == "dice_coin":
        content = InteractiveDiceCoinWidget()
        default_title = "Dice & Coin"
        default_icon = "ri.copper-coin-line"
    else:
        return None

    item = InteractiveCanvasItem(
        widget_type=widget_type,
        title=title or default_title,
        icon_name=icon or default_icon,
        content_widget=content,
        state_data=state_data or {}
    )
    return item
