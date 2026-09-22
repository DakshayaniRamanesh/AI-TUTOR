"""
Interactive Live Clock & Stopwatch Canvas Widget
Displays real-time digital clock, date, timezone, active stopwatch, and countdown timer.
"""

from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QFrame
)
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt, QTimer, QTime
from ...theme_manager import ThemeManager
from ...kestrel_theme import MONO_FONT


class InteractiveClockWidget(QWidget):
    """
    Live real-time clock, stopwatch, and countdown timer widget.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(290)

        self._mode = "clock" # "clock", "stopwatch", "timer"

        # Stopwatch state
        self._stopwatch_time = 0 # tenths of a second
        self._stopwatch_running = False
        self._stopwatch_timer = QTimer(self)
        self._stopwatch_timer.setInterval(100) # 100ms
        self._stopwatch_timer.timeout.connect(self._on_stopwatch_tick)

        # Countdown Timer state
        self._timer_seconds_left = 300 # 5 min default
        self._timer_running = False
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._on_countdown_tick)

        # Clock master 1-second ticker
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._update_clock_display)

        self._init_ui()
        self._clock_timer.start()
        self._update_clock_display()

    def _init_ui(self):
        c = ThemeManager.instance().get_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(8)

        # Mode Selector Buttons
        mode_row = QHBoxLayout()
        mode_row.setSpacing(4)
        
        self.btn_mode_clock = self._create_tab_btn("Clock", True)
        self.btn_mode_clock.clicked.connect(lambda: self._set_mode("clock"))
        mode_row.addWidget(self.btn_mode_clock)

        self.btn_mode_sw = self._create_tab_btn("Stopwatch", False)
        self.btn_mode_sw.clicked.connect(lambda: self._set_mode("stopwatch"))
        mode_row.addWidget(self.btn_mode_sw)

        self.btn_mode_tm = self._create_tab_btn("Timer", False)
        self.btn_mode_tm.clicked.connect(lambda: self._set_mode("timer"))
        mode_row.addWidget(self.btn_mode_tm)

        layout.addLayout(mode_row)

        # Stack container
        self.stack = QStackedWidget(self)

        # ── Page 0: Live Clock ──
        page_clock = QWidget()
        pc_layout = QVBoxLayout(page_clock)
        pc_layout.setContentsMargins(0, 8, 0, 8)
        pc_layout.setSpacing(4)
        pc_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_time = QLabel("00:00:00", page_clock)
        self.lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_time.setStyleSheet(f"""
            font-size: 32px;
            font-weight: 800;
            font-family: {MONO_FONT};
            color: #8b5cf6;
            letter-spacing: 2px;
        """)
        pc_layout.addWidget(self.lbl_time)

        self.lbl_date = QLabel("", page_clock)
        self.lbl_date.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_date.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {c['text_secondary']};")
        pc_layout.addWidget(self.lbl_date)

        self.stack.addWidget(page_clock)

        # ── Page 1: Stopwatch ──
        page_sw = QWidget()
        psw_layout = QVBoxLayout(page_sw)
        psw_layout.setContentsMargins(0, 8, 0, 8)
        psw_layout.setSpacing(8)
        psw_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_sw_time = QLabel("00:00.0", page_sw)
        self.lbl_sw_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_sw_time.setStyleSheet(f"""
            font-size: 30px;
            font-weight: 800;
            font-family: {MONO_FONT};
            color: #10b981;
        """)
        psw_layout.addWidget(self.lbl_sw_time)

        sw_btn_row = QHBoxLayout()
        self.btn_sw_toggle = QPushButton("Start", page_sw)
        self.btn_sw_toggle.setFixedHeight(28)
        self.btn_sw_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sw_toggle.setStyleSheet("background: #10b981; color: #fff; border-radius: 4px; font-weight: 700; font-size: 11px;")
        self.btn_sw_toggle.clicked.connect(self._toggle_stopwatch)
        sw_btn_row.addWidget(self.btn_sw_toggle)

        self.btn_sw_reset = QPushButton("Reset", page_sw)
        self.btn_sw_reset.setFixedHeight(28)
        self.btn_sw_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sw_reset.setStyleSheet(f"background: {c['panel_card_bg']}; color: {c['text_primary']}; border: 1px solid {c['border_color']}; border-radius: 4px; font-size: 11px;")
        self.btn_sw_reset.clicked.connect(self._reset_stopwatch)
        sw_btn_row.addWidget(self.btn_sw_reset)

        psw_layout.addLayout(sw_btn_row)
        self.stack.addWidget(page_sw)

        # ── Page 2: Countdown Timer ──
        page_tm = QWidget()
        ptm_layout = QVBoxLayout(page_tm)
        ptm_layout.setContentsMargins(0, 8, 0, 8)
        ptm_layout.setSpacing(8)
        ptm_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_tm_time = QLabel("05:00", page_tm)
        self.lbl_tm_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_tm_time.setStyleSheet(f"""
            font-size: 30px;
            font-weight: 800;
            font-family: {MONO_FONT};
            color: #f59e0b;
        """)
        ptm_layout.addWidget(self.lbl_tm_time)

        # Presets row
        preset_row = QHBoxLayout()
        preset_row.setSpacing(4)
        for label, secs in [("1m", 60), ("5m", 300), ("10m", 600), ("25m", 1500)]:
            b = QPushButton(label, page_tm)
            b.setFixedHeight(20)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"font-size: 10px; background: {c['panel_card_bg']}; border: 1px solid {c['border_color']}; border-radius: 3px; color: {c['text_secondary']};")
            b.clicked.connect(lambda _, s=secs: self._set_timer_seconds(s))
            preset_row.addWidget(b)
        ptm_layout.addLayout(preset_row)

        tm_btn_row = QHBoxLayout()
        self.btn_tm_toggle = QPushButton("Start", page_tm)
        self.btn_tm_toggle.setFixedHeight(28)
        self.btn_tm_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_tm_toggle.setStyleSheet("background: #f59e0b; color: #fff; border-radius: 4px; font-weight: 700; font-size: 11px;")
        self.btn_tm_toggle.clicked.connect(self._toggle_countdown)
        tm_btn_row.addWidget(self.btn_tm_toggle)

        self.btn_tm_reset = QPushButton("Reset", page_tm)
        self.btn_tm_reset.setFixedHeight(28)
        self.btn_tm_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_tm_reset.setStyleSheet(f"background: {c['panel_card_bg']}; color: {c['text_primary']}; border: 1px solid {c['border_color']}; border-radius: 4px; font-size: 11px;")
        self.btn_tm_reset.clicked.connect(self._reset_countdown)
        tm_btn_row.addWidget(self.btn_tm_reset)

        ptm_layout.addLayout(tm_btn_row)
        self.stack.addWidget(page_tm)

        layout.addWidget(self.stack)

    def _create_tab_btn(self, text: str, is_active: bool) -> QPushButton:
        c = ThemeManager.instance().get_colors()
        btn = QPushButton(text, self)
        btn.setFixedHeight(24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_tab_btn_style(btn, is_active)
        return btn

    def _update_tab_btn_style(self, btn: QPushButton, is_active: bool):
        c = ThemeManager.instance().get_colors()
        if is_active:
            btn.setStyleSheet("""
                QPushButton {
                    background: #8b5cf6;
                    color: #ffffff;
                    border: none;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 700;
                }
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {c['text_secondary']};
                    border: 1px solid {c['border_color']};
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {c['panel_card_bg']};
                    color: {c['text_primary']};
                }}
            """)

    def _set_mode(self, mode: str):
        self._mode = mode
        self._update_tab_btn_style(self.btn_mode_clock, mode == "clock")
        self._update_tab_btn_style(self.btn_mode_sw, mode == "stopwatch")
        self._update_tab_btn_style(self.btn_mode_tm, mode == "timer")
        idx = 0 if mode == "clock" else (1 if mode == "stopwatch" else 2)
        self.stack.setCurrentIndex(idx)

    def _update_clock_display(self):
        now = datetime.now()
        self.lbl_time.setText(now.strftime("%I:%M:%S %p"))
        self.lbl_date.setText(now.strftime("%A, %b %d, %Y"))

    # ── Stopwatch logic ──
    def _toggle_stopwatch(self):
        if self._stopwatch_running:
            self._stopwatch_timer.stop()
            self._stopwatch_running = False
            self.btn_sw_toggle.setText("Resume")
            self.btn_sw_toggle.setStyleSheet("background: #3b82f6; color: #fff; border-radius: 4px; font-weight: 700; font-size: 11px;")
        else:
            self._stopwatch_timer.start()
            self._stopwatch_running = True
            self.btn_sw_toggle.setText("Pause")
            self.btn_sw_toggle.setStyleSheet("background: #ef4444; color: #fff; border-radius: 4px; font-weight: 700; font-size: 11px;")

    def _on_stopwatch_tick(self):
        self._stopwatch_time += 1
        mins = (self._stopwatch_time // 600)
        secs = (self._stopwatch_time // 10) % 60
        tenths = self._stopwatch_time % 10
        self.lbl_sw_time.setText(f"{mins:02d}:{secs:02d}.{tenths}")

    def _reset_stopwatch(self):
        self._stopwatch_timer.stop()
        self._stopwatch_running = False
        self._stopwatch_time = 0
        self.lbl_sw_time.setText("00:00.0")
        self.btn_sw_toggle.setText("Start")
        self.btn_sw_toggle.setStyleSheet("background: #10b981; color: #fff; border-radius: 4px; font-weight: 700; font-size: 11px;")

    # ── Countdown logic ──
    def _set_timer_seconds(self, secs: int):
        self._countdown_timer.stop()
        self._timer_running = False
        self._timer_seconds_left = secs
        self._update_timer_label()
        self.btn_tm_toggle.setText("Start")
        self.btn_tm_toggle.setStyleSheet("background: #f59e0b; color: #fff; border-radius: 4px; font-weight: 700; font-size: 11px;")

    def _toggle_countdown(self):
        if self._timer_running:
            self._countdown_timer.stop()
            self._timer_running = False
            self.btn_tm_toggle.setText("Resume")
        else:
            self._countdown_timer.start()
            self._timer_running = True
            self.btn_tm_toggle.setText("Pause")

    def _on_countdown_tick(self):
        if self._timer_seconds_left > 0:
            self._timer_seconds_left -= 1
            self._update_timer_label()
        else:
            self._countdown_timer.stop()
            self._timer_running = False
            self.btn_tm_toggle.setText("Done!")
            self.lbl_tm_time.setText("⏰ 00:00")

    def _update_timer_label(self):
        mins = self._timer_seconds_left // 60
        secs = self._timer_seconds_left % 60
        self.lbl_tm_time.setText(f"{mins:02d}:{secs:02d}")

    def _reset_countdown(self):
        self._countdown_timer.stop()
        self._timer_running = False
        self._timer_seconds_left = 300
        self._update_timer_label()
        self.btn_tm_toggle.setText("Start")

    def get_state(self) -> dict:
        return {"mode": self._mode}
