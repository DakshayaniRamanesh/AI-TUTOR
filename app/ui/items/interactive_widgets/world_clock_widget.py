"""
Interactive Multi-Timezone World Clock Widget (Circular Analog & Digital Modes)
Provides live side-by-side time comparisons across global timezones (UK, NZ, US, Tokyo, etc.)
with interactive switching between Circular Analog Dials and Digital Cards.
"""

import math
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Tuple, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QPointF, QRectF, QTime
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPolygonF

from ...kestrel_theme import MONO_FONT


import re
from typing import List, Tuple, Dict, Any, Optional

CITY_TIMEZONE_MAP = [
    ([r"\blk\b", r"sri\s*lanka", r"colombo"], "Colombo (LK)", "Asia/Colombo", "🇱🇰"),
    ([r"\bnyc\b", r"\bny\b", r"new\s*york(\s*city)?", r"\best\b", r"\bedt\b"], "New York (US)", "America/New_York", "🇺🇸"),
    ([r"\buk\b", r"\blondon\b", r"britain", r"england", r"\bgmt\b", r"\bbst\b"], "London (UK)", "Europe/London", "🇬🇧"),
    ([r"\bnz\b", r"new\s*zealand", r"auckland", r"\bnzst\b", r"\bnzdt\b"], "Auckland (NZ)", "Pacific/Auckland", "🇳🇿"),
    ([r"california", r"\bla\b", r"los\s*angeles", r"\bsf\b", r"san\s*francisco", r"\bpst\b", r"\bpdt\b", r"seattle"], "Los Angeles (US)", "America/Los_Angeles", "🇺🇸"),
    ([r"tokyo", r"japan", r"\bjst\b", r"\bjp\b"], "Tokyo (JP)", "Asia/Tokyo", "🇯🇵"),
    ([r"india", r"delhi", r"mumbai", r"\bist\b", r"\bin\b"], "New Delhi (IN)", "Asia/Kolkata", "🇮🇳"),
    ([r"australia", r"sydney", r"melbourne", r"\baest\b", r"\bau\b"], "Sydney (AU)", "Australia/Sydney", "🇦🇺"),
    ([r"\bparis\b", r"france", r"\bcet\b", r"\bfr\b"], "Paris (FR)", "Europe/Paris", "🇫🇷"),
    ([r"berlin", r"germany", r"\bde\b"], "Berlin (DE)", "Europe/Berlin", "🇩🇪"),
    ([r"dubai", r"\buae\b", r"\bgst\b"], "Dubai (UAE)", "Asia/Dubai", "🇦🇪"),
    ([r"singapore", r"\bsgt\b", r"\bsg\b"], "Singapore (SG)", "Asia/Singapore", "🇸🇬"),
    ([r"toronto", r"canada", r"vancouver"], "Toronto (CA)", "America/Toronto", "🇨🇦"),
    ([r"chicago", r"\bcst\b", r"\bcdt\b"], "Chicago (US)", "America/Chicago", "🇺🇸"),
    ([r"beijing", r"china", r"shanghai", r"\bcn\b"], "Beijing (CN)", "Asia/Shanghai", "🇨🇳"),
    ([r"seoul", r"korea", r"\bkr\b"], "Seoul (KR)", "Asia/Seoul", "🇰🇷"),
]


def parse_timezones_from_prompt(prompt: str) -> List[Tuple[str, str, str]]:
    """
    Extracts requested cities/countries from prompt text.
    Uses regex word boundaries to avoid spurious matches (e.g. 'paris' in 'comparison').
    Supports global city lookup in zoneinfo.available_timezones().
    Returns list of (display_name, zone_identifier, flag_emoji).
    """
    q = prompt.lower()
    selected = []
    seen_zones = set()

    # 1. Check curated aliases with word boundaries
    for patterns, name, zone_id, flag in CITY_TIMEZONE_MAP:
        for pat in patterns:
            if re.search(pat, q):
                if zone_id not in seen_zones:
                    selected.append((name, zone_id, flag))
                    seen_zones.add(zone_id)
                break

    # 2. Dynamic check across all IANA world timezones if less than 2 found
    if len(selected) < 2:
        try:
            import zoneinfo
            words = re.findall(r"\b[a-z]{3,}\b", q)
            # Filter out common stop words
            stops = {"the", "and", "time", "clock", "between", "betwhnn", "coption", "compare", "comparison", "show", "gimme", "what", "diff", "difference", "versus"}
            candidate_words = [w for w in words if w not in stops]
            all_tz = list(zoneinfo.available_timezones())
            for word in candidate_words:
                matches = [tz for tz in all_tz if word in tz.lower()]
                for tz in matches:
                    if tz not in seen_zones:
                        city_name = tz.split("/")[-1].replace("_", " ")
                        selected.append((f"{city_name} ({tz.split('/')[0]})", tz, "🌐"))
                        seen_zones.add(tz)
                        break
        except Exception:
            pass

    # 3. Handle default fallbacks
    if not selected:
        selected = [
            ("London (UK)", "Europe/London", "🇬🇧"),
            ("Auckland (NZ)", "Pacific/Auckland", "🇳🇿"),
        ]
    elif len(selected) == 1:
        # If user asked for only 1 specific place (e.g. 'time in lk'),
        # pair it with New York or London for an immediate comparative reference!
        if selected[0][1] in ("America/New_York", "America/Los_Angeles"):
            selected.append(("London (UK)", "Europe/London", "🇬🇧"))
        else:
            selected.append(("New York (US)", "America/New_York", "🇺🇸"))

    return selected[:3] # Up to 3 for clean card fit


class AnalogClockDial(QWidget):
    """
    Circular analog clock face with live hour, minute, and second hands.
    """
    def __init__(self, city_name: str, zone_id: str, flag: str, parent=None):
        super().__init__(parent)
        self.city_name = city_name
        self.zone_id = zone_id
        self.flag = flag
        self.setFixedSize(130, 155)

        self.current_hour = 0
        self.current_minute = 0
        self.current_second = 0
        self.digital_str = "00:00:00"
        self.date_str = ""

    def update_time(self):
        try:
            tz = ZoneInfo(self.zone_id)
            dt = datetime.now(tz)
        except Exception:
            dt = datetime.now()

        self.current_hour = dt.hour
        self.current_minute = dt.minute
        self.current_second = dt.second
        self.digital_str = dt.strftime("%I:%M:%S %p")
        self.date_str = dt.strftime("%b %d")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Header (Flag + City)
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#f4f4f5"))
        painter.drawText(QRectF(0, 0, self.width(), 16), Qt.AlignmentFlag.AlignCenter, f"{self.flag} {self.city_name}")

        # 2. Clock Dial Center & Radius
        center_x = self.width() / 2.0
        center_y = 66.0
        radius = 44.0

        # Dial Face Background
        painter.setBrush(QColor("#1e1e24"))
        painter.setPen(QPen(QColor("#3f3f46"), 2))
        painter.drawEllipse(QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2))

        # Hour Ticks
        painter.setPen(QPen(QColor("#71717a"), 1.5))
        for i in range(12):
            angle = i * (math.pi / 6.0)
            x1 = center_x + (radius - 2) * math.sin(angle)
            y1 = center_y - (radius - 2) * math.cos(angle)
            x2 = center_x + (radius - 8) * math.sin(angle)
            y2 = center_y - (radius - 8) * math.cos(angle)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # 3. Clock Hands
        # Hour Hand
        h_angle = ((self.current_hour % 12) + self.current_minute / 60.0) * (math.pi / 6.0)
        h_len = radius * 0.52
        hx = center_x + h_len * math.sin(h_angle)
        hy = center_y - h_len * math.cos(h_angle)
        painter.setPen(QPen(QColor("#f4f4f5"), 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(center_x, center_y), QPointF(hx, hy))

        # Minute Hand
        m_angle = (self.current_minute + self.current_second / 60.0) * (math.pi / 30.0)
        m_len = radius * 0.74
        mx = center_x + m_len * math.sin(m_angle)
        my = center_y - m_len * math.cos(m_angle)
        painter.setPen(QPen(QColor("#a855f7"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(center_x, center_y), QPointF(mx, my))

        # Second Hand
        s_angle = self.current_second * (math.pi / 30.0)
        s_len = radius * 0.84
        sx = center_x + s_len * math.sin(s_angle)
        sy = center_y - s_len * math.cos(s_angle)
        painter.setPen(QPen(QColor("#ec4899"), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(center_x, center_y), QPointF(sx, sy))

        # Center Pivot Dot
        painter.setBrush(QColor("#ec4899"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(center_x - 3, center_y - 3, 6, 6))

        # 4. Digital Time & Date Below Dial
        painter.setFont(QFont(MONO_FONT, 8, QFont.Weight.Bold))
        painter.setPen(QColor("#e4e4e7"))
        painter.drawText(QRectF(0, 116, self.width(), 16), Qt.AlignmentFlag.AlignCenter, self.digital_str)

        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Normal))
        painter.setPen(QColor("#a1a1aa"))
        painter.drawText(QRectF(0, 134, self.width(), 16), Qt.AlignmentFlag.AlignCenter, self.date_str)


class DigitalTimeCard(QFrame):
    """
    Sleek digital card displaying timezone time, AM/PM, offset, and relative difference.
    """
    def __init__(self, city_name: str, zone_id: str, flag: str, parent=None):
        super().__init__(parent)
        self.city_name = city_name
        self.zone_id = zone_id
        self.flag = flag

        self.setStyleSheet("""
            DigitalTimeCard {
                background-color: #1e1e24;
                border: 1px solid #3f3f46;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # Header Row
        row_top = QHBoxLayout()
        self.lbl_city = QLabel(f"{flag} {city_name}", self)
        self.lbl_city.setStyleSheet("font-weight: 700; font-size: 11px; color: #f4f4f5;")
        self.lbl_offset = QLabel("UTC", self)
        self.lbl_offset.setStyleSheet(f"font-size: 9px; color: #8b5cf6; font-family: {MONO_FONT}; font-weight: 700;")
        row_top.addWidget(self.lbl_city)
        row_top.addStretch(1)
        row_top.addWidget(self.lbl_offset)
        layout.addLayout(row_top)

        # Big Digital Time
        self.lbl_time = QLabel("00:00:00", self)
        self.lbl_time.setStyleSheet(f"font-size: 20px; font-weight: 800; color: #38bdf8; font-family: {MONO_FONT};")
        layout.addWidget(self.lbl_time)

        # Date & Day Row
        row_btm = QHBoxLayout()
        self.lbl_date = QLabel("Monday, Jan 01", self)
        self.lbl_date.setStyleSheet("font-size: 10px; color: #94a3b8;")
        row_btm.addWidget(self.lbl_date)
        layout.addLayout(row_btm)

    def update_time(self):
        try:
            tz = ZoneInfo(self.zone_id)
            dt = datetime.now(tz)
        except Exception:
            dt = datetime.now()

        self.lbl_time.setText(dt.strftime("%I:%M:%S %p"))
        self.lbl_date.setText(dt.strftime("%A, %b %d"))
        offset = dt.strftime("UTC%z")
        if len(offset) == 8:
            offset_str = f"{offset[:6]}:{offset[6:]}"
        else:
            offset_str = offset
        self.lbl_offset.setText(offset_str)


class WorldClockComparisonWidget(QWidget):
    """
    Main Multi-Timezone Comparison Widget.
    Toggles between Circular Analog Dials and Digital Cards.
    """
    def __init__(self, prompt: str = "", default_mode: str = "circular", parent=None):
        super().__init__(parent)
        self.prompt = prompt

        # Determine mode from prompt if specified
        q = prompt.lower()
        if "digital" in q:
            self.mode = "digital"
        else:
            self.mode = default_mode  # Default to circular analog as requested

        self.timezones = parse_timezones_from_prompt(prompt)

        # Calculate widget dimensions based on number of timezones
        n = len(self.timezones)
        width = max(290, n * 135 + 24) if self.mode == "circular" else 300
        height = 240 if self.mode == "circular" else (n * 85 + 60)
        self.setFixedSize(width, height)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 8, 10, 8)
        self.main_layout.setSpacing(8)

        # Top Control Bar (Title + Mode Switcher)
        top_bar = QHBoxLayout()
        title_text = "World Time Comparison"
        self.title_lbl = QLabel(f"🌐 {title_text}", self)
        self.title_lbl.setStyleSheet(f"font-weight: 700; font-size: 11px; color: #8b5cf6; font-family: {MONO_FONT};")
        top_bar.addWidget(self.title_lbl)
        top_bar.addStretch(1)

        self.btn_toggle = QPushButton("🔢 Digital" if self.mode == "circular" else "🕒 Circular", self)
        self.btn_toggle.setFixedHeight(22)
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.setStyleSheet("""
            QPushButton {
                background: #27272a;
                color: #e4e4e7;
                font-size: 10px;
                font-weight: 700;
                border-radius: 4px;
                padding: 2px 8px;
            }
            QPushButton:hover { background: #3f3f46; color: #ffffff; }
        """)
        self.btn_toggle.clicked.connect(self._toggle_mode)
        top_bar.addWidget(self.btn_toggle)
        self.main_layout.addLayout(top_bar)

        # Content Container
        self.content_container = QWidget(self)
        self.content_layout = QHBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)
        self.main_layout.addWidget(self.content_container, stretch=1)

        self.clock_items = []
        self._build_clocks()

        # Live Update Timer (every 1 second)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)

        # Immediate first tick
        self._tick()

    def _build_clocks(self):
        # Clear existing
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.clock_items.clear()

        if self.mode == "circular":
            self.content_layout.setDirection(QHBoxLayout.Direction.LeftToRight)
            for name, zone_id, flag in self.timezones:
                dial = AnalogClockDial(city_name=name, zone_id=zone_id, flag=flag, parent=self)
                self.content_layout.addWidget(dial)
                self.clock_items.append(dial)
        else:
            # Digital mode: vertical stack
            self.content_layout.setDirection(QHBoxLayout.Direction.TopToBottom)
            for name, zone_id, flag in self.timezones:
                card = DigitalTimeCard(city_name=name, zone_id=zone_id, flag=flag, parent=self)
                self.content_layout.addWidget(card)
                self.clock_items.append(card)

    def _toggle_mode(self):
        self.mode = "digital" if self.mode == "circular" else "circular"
        self.btn_toggle.setText("🔢 Digital" if self.mode == "circular" else "🕒 Circular")

        # Adjust height
        n = len(self.timezones)
        width = max(290, n * 135 + 24) if self.mode == "circular" else 300
        height = 240 if self.mode == "circular" else (n * 85 + 60)
        self.setFixedSize(width, height)

        self._build_clocks()
        self._tick()

    def _tick(self):
        for clock in self.clock_items:
            clock.update_time()

    def get_state(self) -> dict:
        return {
            "mode": self.mode,
            "prompt": self.prompt,
            "timezones": self.timezones
        }
