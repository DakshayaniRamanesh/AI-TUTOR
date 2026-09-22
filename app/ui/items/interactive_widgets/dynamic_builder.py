"""
Dynamic On-The-Fly Interactive Widget Builder
Constructs built-in instant widgets OR dynamically synthesizes custom interactive PyQt mini-apps
at runtime based on any user query.
"""

import os
import re
import math
import time
import random
import requests
from typing import Optional, Tuple, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QSlider, QProgressBar,
    QCheckBox, QRadioButton, QComboBox, QSpinBox, QFrame,
    QScrollArea, QApplication
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer, QPoint, QPointF, QRect, QRectF
from PyQt6.QtGui import QColor, QFont, QPen, QBrush, QPainter, QPainterPath

from .base_interactive_widget import InteractiveCanvasItem
from .clock_widget import InteractiveClockWidget
from .flappy_bird_widget import FlappyBirdGameWidget
from .snake_game_widget import SnakeGameWidget
from .calculator_widget import InteractiveCalculatorWidget
from .tictactoe_widget import TicTacToeWidget
from .counter_widget import InteractiveCounterWidget
from .dice_coin_widget import InteractiveDiceCoinWidget
from .physics_sim_widget import PhysicsSimWidget
from .unit_converter_widget import UnitConverterWidget
from .world_clock_widget import WorldClockComparisonWidget, parse_timezones_from_prompt
from .procedural_sim_widget import ProceduralSimulationWidget
from ...kestrel_theme import MONO_FONT


TIMEZONE_PATTERNS = [
    r"\blk\b", r"sri\s*lanka", r"colombo",
    r"\bnyc\b", r"\bny\b", r"new\s*york",
    r"\buk\b", r"\blondon\b", r"britain", r"england",
    r"\bnz\b", r"new\s*zealand", r"auckland",
    r"california", r"\bla\b", r"los\s*angeles", r"\bsf\b", r"san\s*francisco",
    r"tokyo", r"japan",
    r"india", r"delhi", r"mumbai",
    r"australia", r"sydney", r"melbourne",
    r"\bparis\b", r"france", r"berlin", r"germany",
    r"dubai", r"uae",
    r"singapore",
    r"toronto", r"canada", r"vancouver",
    r"chicago",
    r"beijing", r"china", r"shanghai",
    r"seoul", r"korea",
]


def is_world_clock_request(query: str) -> bool:
    """
    Detects if query is asking for world clock, timezone comparisons, or circular/digital clocks.
    Handles typos like 'coption' (comparison), 'betwhnn' (between), and short codes (lk, nyc, nz, uk).
    """
    if not query or not query.strip():
        return False
    q = query.lower().strip()

    # Explicit world clock / multi-clock phrases
    if any(k in q for k in ["world clock", "timezone", "timezones", "circular clock", "digital clock", "analog clock", "clocks"]):
        return True

    has_time_term = bool(re.search(r"\b(time|times|clock|clocks|hour|hours|gmt|utc)\b", q))
    has_comparison = bool(re.search(r"\b(compare|comparing|comparison|coption|comption|difference|diff|between|betwhnn|btwn|versus|vs|all\s*the)\b", q))

    # Count how many locations are mentioned
    matched_locations = sum(1 for pat in TIMEZONE_PATTERNS if re.search(pat, q))

    if matched_locations >= 2:
        return True
    if matched_locations >= 1 and (has_time_term or has_comparison):
        return True
    if has_time_term and has_comparison:
        return True
    if ("circular" in q or "circlar" in q or "digital" in q) and has_time_term:
        return True

    return False


def match_instant_interactive_preset(query: str) -> Optional[Tuple[str, str, str]]:
    """
    Returns (widget_type, title, icon_name) if query matches an instant built-in widget.
    Instantly mounts world clocks, procedural simulations, arcade games, and utilities.
    """
    q = query.lower().strip()

    # 1. World Clock & Multi-Timezone Comparison (Circular or Digital)
    if is_world_clock_request(q):
        mode_title = "World Clock (Digital)" if "digital" in q else "World Clock (Circular)"
        return ("world_clock", mode_title, "ri.global-line")

    # 2. PenEcho-style Procedural Simulations
    if any(k in q for k in ["orbit", "planetary", "gravity simulator", "planet orbit"]):
        return ("procedural_sim:orbit", "Planetary Orbit Simulator", "ri.earth-line")
    if any(k in q for k in ["pendulum", "harmonic pendulum"]):
        return ("procedural_sim:pendulum", "Harmonic Pendulum", "ri.timer-flash-line")
    if any(k in q for k in ["wave propagation", "sine wave", "wave simulator"]):
        return ("procedural_sim:wave", "Wave Propagation Simulator", "ri.water-flash-line")
    if any(k in q for k in ["lemniscate", "rose curve", "superellipse", "golden spiral", "deltoid", "penecho summon", "math curve"]):
        return ("procedural_sim:curve", "Lemniscate Math Curve", "ri.sparkling-line")

    # 3. Clock / Time / Stopwatch / Timer (Only basic single clock requests)
    if q in ["time", "clock", "stopwatch", "timer", "countdown", "what is the time", "what's the time", "gimme the time", "show time", "current time"]:
        return ("clock", "Live Clock & Timer", "ri.time-line")
    if any(k in q for k in ["stopwatch", "countdown timer", "open timer", "start timer"]):
        return ("clock", "Live Clock & Timer", "ri.time-line")

    # 4. Flappy Bird / Bird game (handles typos like 'floopy', 'floppy')
    if any(k in q for k in ["flappy", "floppy", "floopy", "bird game", "flappy bird"]):
        return ("flappy_bird", "Flappy Bird Arcade", "ri.gamepad-line")

    # 5. Snake Game
    if "snake" in q:
        return ("snake_game", "Snake Arcade", "ri.gamepad-line")

    # 6. Calculator
    if any(k in q for k in ["calculator", "calc", "calculate"]):
        return ("calculator", "Calculator", "ri.calculator-line")

    # 7. Tic-Tac-Toe
    if any(k in q for k in ["tic tac toe", "tictactoe", "xo game", "x and o"]):
        return ("tictactoe", "Tic-Tac-Toe", "ri.grid-line")

    # 8. Counter
    if any(k in q for k in ["counter", "tally", "clicker"]):
        return ("counter", "Tally Counter", "ri.add-circle-line")

    # 9. Dice / Coin
    if any(k in q for k in ["dice", "coin", "heads or tails", "flip a coin", "roll dice"]):
        return ("dice_coin", "Dice & Coin", "ri.copper-coin-line")

    # 10. Physics Sandbox / Bouncing balls
    if any(k in q for k in ["bouncing ball", "particle sim"]):
        return ("physics_sim", "Physics Sandbox", "ri.bubble-chart-line")

    # 11. Unit Converter
    if any(k in q for k in ["unit converter", "convert unit", "celsius to fahrenheit"]):
        return ("unit_converter", "Unit Converter", "ri.exchange-line")

    return None


def is_interactive_build_request(query: str) -> bool:
    """
    Detects if the user prompt is asking to build, create, or spawn an interactive
    tool, widget, game, simulation, or app dynamically on the canvas.
    Handles casual phrasing and common phonetic typos (bulid, buid, intetive, gimme).
    """
    if not query or not query.strip():
        return False

    q = query.lower().strip()

    if is_world_clock_request(q):
        return True
    if match_instant_interactive_preset(q) is not None:
        return True

    build_verbs = r"\b(build|bulid|buid|make|create|creat|construct|spawn|generate|gimme|give\s*me|show\s*me|ready\s*to\s*build)\b"
    interactive_nouns = r"\b(game|widget|tool|app|sim|simulation|simulator|clock|clocks|board|tester|synth|piano|counter|calc|calculator|match|quiz|card|curve|wave|pendulum|orbit|floopy|flappy|snake)\b"
    interactive_modifiers = r"\b(interactive|intetive|interative|playable|realtime)\b"

    if re.search(interactive_modifiers, q) and (re.search(build_verbs, q) or re.search(interactive_nouns, q)):
        return True
    if re.search(build_verbs, q) and re.search(interactive_nouns, q):
        return True

    # Regex patterns for natural language prompts
    patterns = [
        r"\b(build|bulid|buid|make|create|construct|spawn|generate)\b.*\b(game|widget|tool|app|sim|simulation|tester|pad|board|card)\b",
        r"\b(can you|please|ready to)\b\s*(build|bulid|make|create)\b",
        r"\b(interactive|intetive|playable|realtime)\b\s*(game|tool|sim|app|widget|element)",
        r"\b(reaction|reflex)\s*(test|game)",
        r"\b(memory|flashcard|quiz)\s*(game|card|widget)",
        r"\b(piano|synth|music)\s*(keyboard|widget|tool)",
        r"\b(scratchpad|sketch|whiteboard)\s*(pad|widget)",
        r"\b(color|palette)\s*(picker|generator|mixer)",
        r"\b(todo|task)\s*(list|widget|tracker)",
    ]

    for pat in patterns:
        if re.search(pat, q):
            return True

    # Check words combination
    has_action = any(w in q for w in ["build", "bulid", "buid", "make", "create", "spawn", "generate", "play", "gimme", "give", "show", "tell", "compare"])
    has_target = any(w in q for w in ["game", "widget", "tool", "app", "sim", "interactive", "board", "clock", "simulator"])
    if has_action and has_target:
        return True

    return False


def create_instant_widget_item(
    widget_type: str,
    title: str = None,
    icon: str = None,
    state_data: dict = None,
    prompt: str = ""
) -> Optional[InteractiveCanvasItem]:
    """Instantiates a built-in interactive widget."""
    content = None
    default_title = "Interactive Widget"
    default_icon = "ri.apps-line"

    if widget_type == "world_clock":
        p = prompt or (state_data.get("prompt", "") if state_data else "")
        default_mode = "digital" if "digital" in p.lower() else "circular"
        content = WorldClockComparisonWidget(prompt=p, default_mode=default_mode)
        default_title = "World Clock (Digital)" if default_mode == "digital" else "World Clock (Circular)"
        default_icon = "ri.global-line"
        if not state_data:
            state_data = {}
        state_data["prompt"] = p
    elif widget_type.startswith("procedural_sim"):
        sim_type = widget_type.split(":")[-1] if ":" in widget_type else "pendulum"
        content = ProceduralSimulationWidget(sim_type=sim_type)
        name_map = {
            "orbit": ("Planetary Orbit Simulator", "ri.earth-line"),
            "pendulum": ("Harmonic Pendulum", "ri.timer-flash-line"),
            "wave": ("Wave Propagation Simulator", "ri.water-flash-line"),
            "curve": ("Lemniscate Math Curve", "ri.sparkling-line")
        }
        default_title, default_icon = name_map.get(sim_type, ("Procedural Simulation", "ri.sparkling-line"))
        if not state_data:
            state_data = {}
        state_data["sim_type"] = sim_type
    elif widget_type == "clock":
        content = InteractiveClockWidget()
        default_title = "Live Clock & Timer"
        default_icon = "ri.time-line"
    elif widget_type == "flappy_bird":
        content = FlappyBirdGameWidget()
        default_title = "Flappy Bird Arcade"
        default_icon = "ri.gamepad-line"
    elif widget_type == "snake_game":
        content = SnakeGameWidget()
        default_title = "Snake Arcade"
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
    elif widget_type == "physics_sim":
        content = PhysicsSimWidget()
        default_title = "Physics Sandbox"
        default_icon = "ri.bubble-chart-line"
    elif widget_type == "unit_converter":
        content = UnitConverterWidget()
        default_title = "Unit Converter"
        default_icon = "ri.exchange-line"
    else:
        return None

    return InteractiveCanvasItem(
        widget_type=widget_type,
        title=title or default_title,
        icon_name=icon or default_icon,
        content_widget=content,
        state_data=state_data or {}
    )


# ── Sleek Loading Placeholder ──────────────────────────────────────────────────

class DynamicWidgetPlaceholder(QWidget):
    """
    Temporary loading card displayed on the canvas while the custom interactive widget
    is synthesized and mounted.
    """
    def __init__(self, prompt: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 115)
        self.setStyleSheet("""
            QWidget {
                background: #18181b;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        header_lbl = QLabel("⚡ Synthesizing Interactive Widget...", self)
        header_lbl.setStyleSheet(f"font-weight: 700; font-size: 12px; color: #a855f7; font-family: {MONO_FONT};")
        layout.addWidget(header_lbl)

        clean_p = prompt[:38] + "..." if len(prompt) > 38 else prompt
        prompt_lbl = QLabel(f"\"{clean_p}\"", self)
        prompt_lbl.setStyleSheet("font-size: 11px; color: #a1a1aa; font-style: italic;")
        prompt_lbl.setWordWrap(True)
        layout.addWidget(prompt_lbl)

        layout.addSpacing(4)
        self.pbar = QProgressBar(self)
        self.pbar.setRange(0, 0)
        self.pbar.setFixedHeight(4)
        self.pbar.setTextVisible(False)
        self.pbar.setStyleSheet("""
            QProgressBar {
                background: #27272a;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #ec4899);
                border-radius: 2px;
            }
        """)
        layout.addWidget(self.pbar)


# ── Rich Generative Fallback Widgets ───────────────────────────────────────────

class ReactionSpeedWidget(QWidget):
    """Interactive reaction time speed tester."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 240)
        self.state = "idle" # idle, waiting, ready, result
        self.start_time = 0.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.btn = QPushButton("⚡ Click to Start Test", self)
        self.btn.setFixedHeight(140)
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.clicked.connect(self._on_btn_clicked)
        layout.addWidget(self.btn)

        self.status_lbl = QLabel("Test your reflexes! Click Start.", self)
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet(f"font-size: 11px; color: #94a3b8; font-family: {MONO_FONT};")
        layout.addWidget(self.status_lbl)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._on_green_flash)

        self._set_idle_style()

    def _set_idle_style(self):
        self.state = "idle"
        self.btn.setText("⚡ Click to Start")
        self.btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: #ffffff;
                font-weight: 700;
                font-size: 15px;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)

    def _on_btn_clicked(self):
        if self.state == "idle":
            self.state = "waiting"
            self.btn.setText("⏳ Wait for GREEN...")
            self.btn.setStyleSheet("""
                QPushButton {
                    background-color: #dc2626;
                    color: #ffffff;
                    font-weight: 700;
                    font-size: 14px;
                    border-radius: 8px;
                }
            """)
            self.status_lbl.setText("Do not click yet! Wait for green...")
            delay_ms = random.randint(1400, 3800)
            self.timer.start(delay_ms)

        elif self.state == "waiting":
            self.timer.stop()
            self.state = "early"
            self.btn.setText("⚠️ Too Early!")
            self.btn.setStyleSheet("QPushButton { background: #b91c1c; color: #fff; font-weight: 700; font-size: 14px; border-radius: 8px; }")
            self.status_lbl.setText("Clicked before green! Click to retry.")
            self.state = "idle"

        elif self.state == "ready":
            elapsed_ms = int((time.time() - self.start_time) * 1000)
            self.state = "result"
            rank = "⚡ Godlike" if elapsed_ms < 200 else ("🐆 Fast" if elapsed_ms < 280 else "🐢 Average")
            self.btn.setText(f"🎉 {elapsed_ms} ms!\n{rank}")
            self.btn.setStyleSheet("""
                QPushButton {
                    background-color: #8b5cf6;
                    color: #ffffff;
                    font-weight: 700;
                    font-size: 16px;
                    border-radius: 8px;
                }
            """)
            self.status_lbl.setText(f"Your reaction: {elapsed_ms}ms. Click to retry.")
            self.state = "idle"

    def _on_green_flash(self):
        self.state = "ready"
        self.start_time = time.time()
        self.btn.setText("💥 CLICK NOW!")
        self.btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: #ffffff;
                font-weight: 900;
                font-size: 18px;
                border-radius: 8px;
            }
        """)


class MemoryMatchWidget(QWidget):
    """Interactive 4x4 card matching memory mini-game."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 270)
        self.moves = 0
        self.matches = 0
        self.first_card = None
        self.second_card = None

        symbols = ["🍎", "🍌", "🍇", "🍓", "🥑", "🍕", "🚀", "⭐"] * 2
        random.shuffle(symbols)
        self.cards_symbols = symbols

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        grid = QGridLayout()
        grid.setSpacing(6)
        self.buttons = []

        for i in range(16):
            btn = QPushButton("❓", self)
            btn.setFixedSize(58, 48)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #27272a;
                    color: #e4e4e7;
                    font-size: 16px;
                    border-radius: 6px;
                }
                QPushButton:hover { background-color: #3f3f46; }
            """)
            btn.clicked.connect(lambda _, idx=i: self._on_card_clicked(idx))
            grid.addWidget(btn, i // 4, i % 4)
            self.buttons.append(btn)

        layout.addLayout(grid)

        self.info_lbl = QLabel("Matches: 0/8 | Moves: 0", self)
        self.info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_lbl.setStyleSheet(f"font-size: 11px; color: #a1a1aa; font-family: {MONO_FONT};")
        layout.addWidget(self.info_lbl)

    def _on_card_clicked(self, idx: int):
        if self.first_card is not None and self.second_card is not None:
            return
        btn = self.buttons[idx]
        if btn.text() != "❓":
            return

        btn.setText(self.cards_symbols[idx])
        btn.setStyleSheet("QPushButton { background-color: #8b5cf6; color: #fff; font-size: 16px; border-radius: 6px; }")

        if self.first_card is None:
            self.first_card = idx
        else:
            self.second_card = idx
            self.moves += 1
            if self.cards_symbols[self.first_card] == self.cards_symbols[self.second_card]:
                self.matches += 1
                self.first_card = None
                self.second_card = None
                self.info_lbl.setText(f"Matches: {self.matches}/8 | Moves: {self.moves}")
                if self.matches == 8:
                    self.info_lbl.setText(f"🏆 Victory in {self.moves} moves!")
            else:
                QTimer.singleShot(600, self._reset_unmatched)

    def _reset_unmatched(self):
        if self.first_card is not None and self.second_card is not None:
            self.buttons[self.first_card].setText("❓")
            self.buttons[self.first_card].setStyleSheet("QPushButton { background: #27272a; color: #e4e4e7; font-size: 16px; border-radius: 6px; }")
            self.buttons[self.second_card].setText("❓")
            self.buttons[self.second_card].setStyleSheet("QPushButton { background: #27272a; color: #e4e4e7; font-size: 16px; border-radius: 6px; }")
            self.first_card = None
            self.second_card = None


class ColorPaletteWidget(QWidget):
    """Interactive RGB & HEX color mixer tool."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 260)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.preview = QFrame(self)
        self.preview.setFixedHeight(75)
        self.preview.setStyleSheet("border-radius: 6px; background-color: #8b5cf6;")
        layout.addWidget(self.preview)

        self.hex_lbl = QLabel("#8B5CF6", self)
        self.hex_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hex_lbl.setStyleSheet(f"font-weight: 700; font-size: 14px; color: #f4f4f5; font-family: {MONO_FONT};")
        layout.addWidget(self.hex_lbl)

        # Sliders
        self.r_slider = self._make_slider(139)
        self.g_slider = self._make_slider(92)
        self.b_slider = self._make_slider(246)

        layout.addLayout(self._make_slider_row("R", self.r_slider))
        layout.addLayout(self._make_slider_row("G", self.g_slider))
        layout.addLayout(self._make_slider_row("B", self.b_slider))

        self.btn_copy = QPushButton("📋 Copy Hex Code", self)
        self.btn_copy.setFixedHeight(28)
        self.btn_copy.clicked.connect(self._copy_hex)
        self.btn_copy.setStyleSheet("QPushButton { background: #27272a; color: #fff; border-radius: 4px; font-size: 11px; } QPushButton:hover { background: #3f3f46; }")
        layout.addWidget(self.btn_copy)

    def _make_slider(self, val: int):
        s = QSlider(Qt.Orientation.Horizontal, self)
        s.setRange(0, 255)
        s.setValue(val)
        s.valueChanged.connect(self._update_color)
        return s

    def _make_slider_row(self, label: str, slider: QSlider):
        row = QHBoxLayout()
        lbl = QLabel(label, self)
        lbl.setFixedWidth(16)
        lbl.setStyleSheet(f"font-weight: 700; color: #a1a1aa; font-family: {MONO_FONT};")
        row.addWidget(lbl)
        row.addWidget(slider)
        return row

    def _update_color(self):
        r, g, b = self.r_slider.value(), self.g_slider.value(), self.b_slider.value()
        hex_str = f"#{r:02X}{g:02X}{b:02X}"
        self.hex_lbl.setText(hex_str)
        self.preview.setStyleSheet(f"border-radius: 6px; background-color: {hex_str};")

    def _copy_hex(self):
        cb = QApplication.clipboard()
        if cb:
            cb.setText(self.hex_lbl.text())
            self.btn_copy.setText("✓ Copied!")
            QTimer.singleShot(1200, lambda: self.btn_copy.setText("📋 Copy Hex Code"))


class FlashcardQuizWidget(QWidget):
    """Interactive study flashcards / quiz card widget."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 250)
        self.idx = 0
        self.is_flipped = False

        self.cards = [
            ("What is Newton's 2nd Law?", "F = m * a (Force = mass × acceleration)"),
            ("What is the speed of light?", "c ≈ 3.0 × 10⁸ m/s in vacuum"),
            ("Derivative of sin(x)?", "cos(x)"),
            ("Integral of 1/x dx?", "ln|x| + C"),
            ("Euler's Identity?", "e^(iπ) + 1 = 0"),
        ]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.card_btn = QPushButton(self.cards[0][0], self)
        self.card_btn.setFixedHeight(140)
        self.card_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.card_btn.clicked.connect(self._toggle_flip)
        self.card_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e1e24;
                color: #f4f4f5;
                font-size: 13px;
                font-weight: 600;
                padding: 12px;
                border: 1px solid #3f3f46;
                border-radius: 8px;
            }
            QPushButton:hover { border-color: #8b5cf6; }
        """)
        layout.addWidget(self.card_btn)

        row = QHBoxLayout()
        btn_prev = QPushButton("◀ Prev", self)
        btn_prev.clicked.connect(self._prev)
        btn_prev.setStyleSheet("QPushButton { background: #27272a; color: #fff; border-radius: 4px; padding: 6px; }")
        
        self.page_lbl = QLabel(f"1/{len(self.cards)}", self)
        self.page_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_lbl.setStyleSheet(f"color: #a1a1aa; font-size: 11px; font-family: {MONO_FONT};")

        btn_next = QPushButton("Next ▶", self)
        btn_next.clicked.connect(self._next)
        btn_next.setStyleSheet("QPushButton { background: #27272a; color: #fff; border-radius: 4px; padding: 6px; }")

        row.addWidget(btn_prev)
        row.addWidget(self.page_lbl)
        row.addWidget(btn_next)
        layout.addLayout(row)

    def _toggle_flip(self):
        self.is_flipped = not self.is_flipped
        q, a = self.cards[self.idx]
        if self.is_flipped:
            self.card_btn.setText(f"💡 Answer:\n\n{a}")
            self.card_btn.setStyleSheet("QPushButton { background-color: #064e3b; color: #6ee7b7; font-size: 13px; font-weight: 700; border-radius: 8px; padding: 12px; }")
        else:
            self.card_btn.setText(q)
            self.card_btn.setStyleSheet("QPushButton { background-color: #1e1e24; color: #f4f4f5; font-size: 13px; font-weight: 600; border: 1px solid #3f3f46; border-radius: 8px; padding: 12px; }")

    def _next(self):
        self.idx = (self.idx + 1) % len(self.cards)
        self.is_flipped = False
        self.card_btn.setText(self.cards[self.idx][0])
        self.card_btn.setStyleSheet("QPushButton { background-color: #1e1e24; color: #f4f4f5; font-size: 13px; font-weight: 600; border: 1px solid #3f3f46; border-radius: 8px; padding: 12px; }")
        self.page_lbl.setText(f"{self.idx + 1}/{len(self.cards)}")

    def _prev(self):
        self.idx = (self.idx - 1) % len(self.cards)
        self.is_flipped = False
        self.card_btn.setText(self.cards[self.idx][0])
        self.card_btn.setStyleSheet("QPushButton { background-color: #1e1e24; color: #f4f4f5; font-size: 13px; font-weight: 600; border: 1px solid #3f3f46; border-radius: 8px; padding: 12px; }")
        self.page_lbl.setText(f"{self.idx + 1}/{len(self.cards)}")


class ToneSynthWidget(QWidget):
    """Interactive mini piano / musical notes keyboard."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 220)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.display_lbl = QLabel("🎵 Play a note!", self)
        self.display_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display_lbl.setFixedHeight(50)
        self.display_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: #a855f7; background: #18181b; border-radius: 6px; font-family: {MONO_FONT};")
        layout.addWidget(self.display_lbl)

        notes = [("C", "261 Hz"), ("D", "293 Hz"), ("E", "329 Hz"), ("F", "349 Hz"),
                 ("G", "392 Hz"), ("A", "440 Hz"), ("B", "493 Hz"), ("C5", "523 Hz")]

        row1 = QHBoxLayout()
        row1.setSpacing(4)
        for note, freq in notes:
            btn = QPushButton(note, self)
            btn.setFixedHeight(85)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #27272a;
                    color: #ffffff;
                    font-weight: 700;
                    font-size: 13px;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #8b5cf6; }
                QPushButton:pressed { background-color: #ec4899; }
            """)
            btn.clicked.connect(lambda _, n=note, f=freq: self._play_note(n, f))
            row1.addWidget(btn)

        layout.addLayout(row1)

    def _play_note(self, note: str, freq: str):
        self.display_lbl.setText(f"🎶 Note {note}  ({freq})")
        # Try OS beep if on Windows
        try:
            import winsound
            f_num = int(freq.split()[0])
            winsound.Beep(f_num, 120)
        except Exception:
            pass


class MiniSketchWidget(QWidget):
    """Interactive mini scratchpad / whiteboard drawing tool."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 250)
        self.drawing = False
        self.last_point = QPoint()
        self.color = QColor("#8b5cf6")
        self.lines = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Canvas surface
        self.canvas_area = QFrame(self)
        self.canvas_area.setStyleSheet("background: #0f172a; border-radius: 6px;")
        layout.addWidget(self.canvas_area, stretch=1)

        # Toolbar
        row = QHBoxLayout()
        colors = [("#8b5cf6", "Purple"), ("#10b981", "Green"), ("#ef4444", "Red"), ("#f59e0b", "Gold")]
        for hex_val, name in colors:
            btn = QPushButton(self)
            btn.setFixedSize(22, 22)
            btn.setStyleSheet(f"background-color: {hex_val}; border-radius: 11px; border: 1px solid #fff;")
            btn.clicked.connect(lambda _, c=hex_val: setattr(self, "color", QColor(c)))
            row.addWidget(btn)

        btn_clear = QPushButton("🗑️ Clear", self)
        btn_clear.setFixedHeight(24)
        btn_clear.clicked.connect(self._clear)
        btn_clear.setStyleSheet("QPushButton { background: #27272a; color: #fff; font-size: 11px; border-radius: 4px; padding: 2px 8px; }")
        row.addWidget(btn_clear)
        layout.addLayout(row)

    def _clear(self):
        self.lines.clear()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drawing = True
            self.last_point = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self.drawing and event.buttons() & Qt.MouseButton.LeftButton:
            new_point = event.position().toPoint()
            self.lines.append((self.last_point, new_point, self.color))
            self.last_point = new_point
            self.update()

    def mouseReleaseEvent(self, event):
        self.drawing = False

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for p1, p2, col in self.lines:
            painter.setPen(QPen(col, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(p1, p2)


class QuickTasksWidget(QWidget):
    """Interactive checklist / task tracker widget."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 260)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Input row
        row = QHBoxLayout()
        self.inp = QLineEdit(self)
        self.inp.setPlaceholderText("New task...")
        self.inp.setStyleSheet("QLineEdit { background: #1e1e24; color: #fff; border: 1px solid #3f3f46; border-radius: 4px; padding: 4px 8px; }")
        self.inp.returnPressed.connect(self._add_task)
        row.addWidget(self.inp)

        btn_add = QPushButton("➕", self)
        btn_add.setFixedSize(30, 28)
        btn_add.clicked.connect(self._add_task)
        btn_add.setStyleSheet("QPushButton { background: #8b5cf6; color: #fff; border-radius: 4px; font-weight: 700; }")
        row.addWidget(btn_add)
        layout.addLayout(row)

        # Scroll area for tasks
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.task_container = QWidget()
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setContentsMargins(0, 0, 0, 0)
        self.task_layout.setSpacing(4)
        self.task_layout.addStretch(1)
        self.scroll.setWidget(self.task_container)
        layout.addWidget(self.scroll)

        # Initial tasks
        for t in ["Review lecture notes", "Practice STEM problems", "Check collaborative board"]:
            self._add_item_ui(t)

    def _add_task(self):
        text = self.inp.text().strip()
        if text:
            self._add_item_ui(text)
            self.inp.clear()

    def _add_item_ui(self, text: str):
        cb = QCheckBox(text, self.task_container)
        cb.setStyleSheet("""
            QCheckBox { color: #e4e4e7; font-size: 12px; }
            QCheckBox::indicator { width: 15px; height: 15px; border-radius: 3px; border: 1px solid #71717a; }
            QCheckBox::indicator:checked { background-color: #10b981; }
        """)
        self.task_layout.insertWidget(self.task_layout.count() - 1, cb)


# ── Dynamic Code Generator Worker ─────────────────────────────────────────────

class DynamicWidgetBuilderWorker(QThread):
    """
    Background worker that calls LLM (Groq / Gemini) to synthesize custom interactive
    PyQt widget code on-the-fly, compiles it safely, or uses smart generative fallbacks.
    """
    widget_built = pyqtSignal(str, object, str, str, str) # (prompt, widget_instance, title, icon, code)
    build_failed = pyqtSignal(str, str)                  # (prompt, error_msg)

    def __init__(self, prompt: str, parent=None):
        super().__init__(parent)
        self.prompt = prompt

    def run(self):
        try:
            widget_instance, title, icon, code = self._generate_custom_widget(self.prompt)
            if widget_instance:
                self.widget_built.emit(self.prompt, widget_instance, title, icon, code)
            else:
                self.build_failed.emit(self.prompt, "Could not synthesize widget.")
        except Exception as err:
            self.build_failed.emit(self.prompt, str(err))

    def _generate_custom_widget(self, prompt: str) -> Tuple[Optional[QWidget], str, str, str]:
        # 1. Prompt-Aware World Clock & Multi-Timezone Comparison (Circular or Digital)
        if is_world_clock_request(prompt):
            default_mode = "digital" if "digital" in prompt.lower() else "circular"
            widget_inst = WorldClockComparisonWidget(prompt=prompt, default_mode=default_mode)
            title = "World Clock (Digital)" if default_mode == "digital" else "World Clock (Circular)"
            icon = "ri.global-line"
            code = (
                f"class GeneratedCustomWidget(WorldClockComparisonWidget):\n"
                f"    def __init__(self, parent=None):\n"
                f"        super().__init__(prompt={repr(prompt)}, default_mode={repr(default_mode)}, parent=parent)\n"
            )
            return widget_inst, title, icon, code

        # 2. PenEcho-style Procedural Physics & Math Simulators
        q = prompt.lower()
        if any(w in q for w in ["orbit", "planetary", "gravity simulator", "planet orbit"]):
            widget_inst = ProceduralSimulationWidget(sim_type="orbit")
            return widget_inst, "Planetary Orbit Simulator", "ri.earth-line", "class GeneratedCustomWidget(ProceduralSimulationWidget):\n    def __init__(self, parent=None):\n        super().__init__(sim_type='orbit', parent=parent)\n"
        elif any(w in q for w in ["pendulum", "harmonic pendulum"]):
            widget_inst = ProceduralSimulationWidget(sim_type="pendulum")
            return widget_inst, "Harmonic Pendulum", "ri.timer-flash-line", "class GeneratedCustomWidget(ProceduralSimulationWidget):\n    def __init__(self, parent=None):\n        super().__init__(sim_type='pendulum', parent=parent)\n"
        elif any(w in q for w in ["wave", "sine wave", "wave propagation"]):
            widget_inst = ProceduralSimulationWidget(sim_type="wave")
            return widget_inst, "Wave Propagation", "ri.water-flash-line", "class GeneratedCustomWidget(ProceduralSimulationWidget):\n    def __init__(self, parent=None):\n        super().__init__(sim_type='wave', parent=parent)\n"
        elif any(w in q for w in ["curve", "lemniscate", "math curve", "spiral", "rose curve"]):
            widget_inst = ProceduralSimulationWidget(sim_type="curve")
            return widget_inst, "Lemniscate Math Curve", "ri.sparkling-line", "class GeneratedCustomWidget(ProceduralSimulationWidget):\n    def __init__(self, parent=None):\n        super().__init__(sim_type='curve', parent=parent)\n"

        # 3. Attempt LLM generation via Groq or Gemini
        if not os.environ.get("GROQ_API_KEY"):
            from dotenv import load_dotenv
            backend_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "backend", ".env"))
            if os.path.exists(backend_env):
                load_dotenv(backend_env)
        groq_key = os.environ.get("GROQ_API_KEY", "").strip()
        gemini_key = os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip()

        sys_prompt = (
            "You are an expert PyQt6 developer. Write a compact, self-contained, interactive QWidget class.\n"
            "Requirements:\n"
            "- Name the class exactly `GeneratedCustomWidget(QWidget)`.\n"
            "- Must be fully interactive (e.g. click buttons, sliders, text inputs, paint canvas, or timers).\n"
            "- Set fixed width between 260 and 320, and height between 220 and 340.\n"
            "- Use clean, dark-mode friendly modern styling (dark backgrounds like #18181b, #1e1e24, purple/emerald/amber buttons).\n"
            "- Do NOT import anything from PyQt6 outside QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QLineEdit, QSlider, QProgressBar, QTimer, Qt, QColor, QFont, QPen, QBrush, QPainter.\n"
            "- Output ONLY executable Python code inside a ```python ``` block without conversational filler."
        )
        user_msg = f"Build an interactive widget for: {prompt}"

        code_text = ""

        # Groq Models
        if groq_key:
            for model_name in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "openai/gpt-oss-120b"]:
                try:
                    r = requests.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {groq_key}"},
                        json={
                            "model": model_name,
                            "messages": [
                                {"role": "system", "content": sys_prompt},
                                {"role": "user", "content": user_msg}
                            ],
                            "temperature": 0.2
                        },
                        timeout=7.0
                    )
                    if r.status_code == 200:
                        code_text = r.json()["choices"][0]["message"]["content"]
                        break
                except Exception:
                    pass

        # Gemini Models
        if not code_text and gemini_key:
            for g_model in ["gemini-2.5-flash", "gemini-flash-latest", "gemini-1.5-flash"]:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={gemini_key}"
                    r = requests.post(
                        url,
                        json={"contents": [{"parts": [{"text": f"{sys_prompt}\n\n{user_msg}"}]}]},
                        timeout=7.0
                    )
                    if r.status_code == 200:
                        code_text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                        break
                except Exception:
                    pass

        # If LLM returned code, compile and instantiate
        if code_text:
            m = re.search(r"```python\s*(.*?)\s*```", code_text, re.DOTALL)
            clean_code = m.group(1) if m else code_text
            try:
                scope = {
                    "__builtins__": __builtins__,
                    "QWidget": QWidget,
                    "QVBoxLayout": QVBoxLayout,
                    "QHBoxLayout": QHBoxLayout,
                    "QGridLayout": QGridLayout,
                    "QLabel": QLabel,
                    "QPushButton": QPushButton,
                    "QLineEdit": QLineEdit,
                    "QTextEdit": QTextEdit,
                    "QSlider": QSlider,
                    "QProgressBar": QProgressBar,
                    "QTimer": QTimer,
                    "QCheckBox": QCheckBox,
                    "QRadioButton": QRadioButton,
                    "QComboBox": QComboBox,
                    "QSpinBox": QSpinBox,
                    "QFrame": QFrame,
                    "QScrollArea": QScrollArea,
                    "Qt": Qt,
                    "QPoint": QPoint,
                    "QPointF": QPointF,
                    "QRect": QRect,
                    "QRectF": QRectF,
                    "QColor": QColor,
                    "QFont": QFont,
                    "QPen": QPen,
                    "QBrush": QBrush,
                    "QPainter": QPainter,
                    "QPainterPath": QPainterPath,
                    "WorldClockComparisonWidget": WorldClockComparisonWidget,
                    "ProceduralSimulationWidget": ProceduralSimulationWidget,
                    "ReactionSpeedWidget": ReactionSpeedWidget,
                    "MemoryMatchWidget": MemoryMatchWidget,
                    "ColorPaletteWidget": ColorPaletteWidget,
                    "FlashcardQuizWidget": FlashcardQuizWidget,
                    "ToneSynthWidget": ToneSynthWidget,
                    "MiniSketchWidget": MiniSketchWidget,
                    "QuickTasksWidget": QuickTasksWidget,
                    "random": random,
                    "math": math,
                    "time": time,
                    "MONO_FONT": MONO_FONT,
                }
                exec(clean_code, scope)
                if "GeneratedCustomWidget" in scope:
                    widget_inst = scope["GeneratedCustomWidget"]()
                    title = prompt[:22].title()
                    return widget_inst, title, "ri.apps-line", clean_code
            except Exception as compile_err:
                print(f"[DynamicWidgetBuilder] Compilation failed: {compile_err}")

        # 2. Rich Generative Fallbacks based on user keywords
        q = prompt.lower()
        if any(w in q for w in ["reaction", "reflex", "speed test", "click speed"]):
            return ReactionSpeedWidget(), "Reaction Speed Test", "ri.flashlight-line", "class GeneratedCustomWidget(ReactionSpeedWidget): pass"
        elif any(w in q for w in ["memory", "card match", "flip card"]):
            return MemoryMatchWidget(), "Memory Match Game", "ri.brain-line", "class GeneratedCustomWidget(MemoryMatchWidget): pass"
        elif any(w in q for w in ["color", "palette", "picker", "hex"]):
            return ColorPaletteWidget(), "Color Palette Tool", "ri.palette-line", "class GeneratedCustomWidget(ColorPaletteWidget): pass"
        elif any(w in q for w in ["quiz", "flashcard", "trivia", "study card"]):
            return FlashcardQuizWidget(), "STEM Flashcards", "ri.questionnaire-line", "class GeneratedCustomWidget(FlashcardQuizWidget): pass"
        elif any(w in q for w in ["piano", "synth", "music", "sound", "note", "tone"]):
            return ToneSynthWidget(), "Music Synth Keys", "ri.music-2-line", "class GeneratedCustomWidget(ToneSynthWidget): pass"
        elif any(w in q for w in ["draw", "sketch", "whiteboard", "paint", "pad"]):
            return MiniSketchWidget(), "Mini Sketchpad", "ri.brush-line", "class GeneratedCustomWidget(MiniSketchWidget): pass"
        elif any(w in q for w in ["task", "todo", "list", "checklist"]):
            return QuickTasksWidget(), "Tasks Checklist", "ri.checkbox-line", "class GeneratedCustomWidget(QuickTasksWidget): pass"

        # Universal Generative Fallback: Reaction speed tester with prompt title
        return ReactionSpeedWidget(), f"{prompt[:18].title()} Tool", "ri.tools-line", "class GeneratedCustomWidget(ReactionSpeedWidget): pass"
