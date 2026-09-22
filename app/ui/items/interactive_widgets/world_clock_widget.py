"""
Interactive Multi-Timezone World Clock Widget (Circular Analog & Digital Modes)
Clean, professional light theme matching Kestrel design system and academic workstations.
No emojis or neon styling — uses crisp typography, Remix icons, and high-contrast palettes.
"""

import math
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Tuple, Dict, Any, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont, QPen
import qtawesome as qta

from ...kestrel_theme import MONO_FONT


CITY_TIMEZONE_MAP = [
    ([r"\blk\b", r"sri\s*lanka", r"colombo"], "Colombo", "Asia/Colombo", "LK"),
    ([r"\bnyc\b", r"\bny\b", r"new\s*york(\s*city)?", r"\best\b", r"\bedt\b"], "New York", "America/New_York", "US"),
    ([r"\buk\b", r"\blondon\b", r"britain", r"england", r"\bgmt\b", r"\bbst\b"], "London", "Europe/London", "GB"),
    ([r"\bnz\b", r"new\s*zealand", r"auckland", r"\bnzst\b", r"\bnzdt\b"], "Auckland", "Pacific/Auckland", "NZ"),
    ([r"california", r"\bla\b", r"los\s*angeles", r"\bsf\b", r"san\s*francisco", r"\bpst\b", r"\bpdt\b", r"seattle"], "Los Angeles", "America/Los_Angeles", "US"),
    ([r"tokyo", r"japan", r"\bjst\b", r"\bjp\b"], "Tokyo", "Asia/Tokyo", "JP"),
    ([r"india", r"delhi", r"mumbai", r"\bist\b", r"\bin\b"], "New Delhi", "Asia/Kolkata", "IN"),
    ([r"australia", r"sydney", r"melbourne", r"\baest\b", r"\bau\b"], "Sydney", "Australia/Sydney", "AU"),
    ([r"\bparis\b", r"france", r"\bcet\b", r"\bfr\b"], "Paris", "Europe/Paris", "FR"),
    ([r"berlin", r"germany", r"\bde\b"], "Berlin", "Europe/Berlin", "DE"),
    ([r"dubai", r"\buae\b", r"\bgst\b"], "Dubai", "Asia/Dubai", "AE"),
    ([r"singapore", r"\bsgt\b", r"\bsg\b"], "Singapore", "Asia/Singapore", "SG"),
    ([r"toronto", r"canada", r"vancouver"], "Toronto", "America/Toronto", "CA"),
    ([r"chicago", r"\bcst\b", r"\bcdt\b"], "Chicago", "America/Chicago", "US"),
    ([r"beijing", r"china", r"shanghai", r"\bcn\b"], "Beijing", "Asia/Shanghai", "CN"),
    ([r"seoul", r"korea", r"\bkr\b"], "Seoul", "Asia/Seoul", "KR"),
]


def parse_timezones_from_prompt(prompt: str) -> List[Tuple[str, str, str]]:
    """
    Extracts requested cities/countries from prompt text.
    Uses regex word boundaries to avoid spurious matches.
    Returns list of (display_name, zone_identifier, country_code).
    """
    q = prompt.lower()
    selected = []
    seen_zones = set()

    # 1. Check curated aliases with word boundaries
    for patterns, name, zone_id, code in CITY_TIMEZONE_MAP:
        for pat in patterns:
            if re.search(pat, q):
                if zone_id not in seen_zones:
                    selected.append((name, zone_id, code))
                    seen_zones.add(zone_id)
                break

    # 2. Dynamic check across all IANA world timezones if less than 2 found
    if len(selected) < 2:
        try:
            import zoneinfo
            words = re.findall(r"\b[a-z]{3,}\b", q)
            stops = {"the", "and", "time", "clock", "between", "betwhnn", "coption", "compare", "comparison", "show", "gimme", "what", "diff", "difference", "versus"}
            candidate_words = [w for w in words if w not in stops]
            all_tz = list(zoneinfo.available_timezones())
            for word in candidate_words:
                matches = [tz for tz in all_tz if word in tz.lower()]
                for tz in matches:
                    if tz not in seen_zones:
                        city_name = tz.split("/")[-1].replace("_", " ")
                        code = tz.split("/")[0][:2].upper()
                        selected.append((city_name, tz, code))
                        seen_zones.add(tz)
                        break
        except Exception:
            pass

    # 3. Handle default fallbacks
    if not selected:
        selected = [
            ("London", "Europe/London", "GB"),
            ("Auckland", "Pacific/Auckland", "NZ"),
        ]
    elif len(selected) == 1:
        if selected[0][1] in ("America/New_York", "America/Los_Angeles"):
            selected.append(("London", "Europe/London", "GB"))
        else:
            selected.append(("New York", "America/New_York", "US"))

    return selected[:3]


class AnalogClockDial(QWidget):
    """
    Circular analog clock face with live hour, minute, and second hands.
    Clean academic light theme with slate ticks and royal blue/red hands.
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

        # 1. Header (City + Country Code)
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#0f172a"))
        title_text = f"{self.city_name} ({self.flag})" if self.flag else self.city_name
        painter.drawText(QRectF(0, 0, self.width(), 16), Qt.AlignmentFlag.AlignCenter, title_text)

        # 2. Clock Dial Center & Radius
        center_x = self.width() / 2.0
        center_y = 66.0
        radius = 44.0

        # Dial Face Background (Pure White + Slate Border)
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(QColor("#cbd5e1"), 1.5))
        painter.drawEllipse(QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2))

        # Hour Ticks
        painter.setPen(QPen(QColor("#94a3b8"), 1.5))
        for i in range(12):
            angle = i * (math.pi / 6.0)
            x1 = center_x + (radius - 2) * math.sin(angle)
            y1 = center_y - (radius - 2) * math.cos(angle)
            x2 = center_x + (radius - 7) * math.sin(angle)
            y2 = center_y - (radius - 7) * math.cos(angle)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # 3. Clock Hands
        # Hour Hand
        h_angle = ((self.current_hour % 12) + self.current_minute / 60.0) * (math.pi / 6.0)
        h_len = radius * 0.52
        hx = center_x + h_len * math.sin(h_angle)
        hy = center_y - h_len * math.cos(h_angle)
        painter.setPen(QPen(QColor("#0f172a"), 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(center_x, center_y), QPointF(hx, hy))

        # Minute Hand
        m_angle = (self.current_minute + self.current_second / 60.0) * (math.pi / 30.0)
        m_len = radius * 0.74
        mx = center_x + m_len * math.sin(m_angle)
        my = center_y - m_len * math.cos(m_angle)
        painter.setPen(QPen(QColor("#2563eb"), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(center_x, center_y), QPointF(mx, my))

        # Second Hand
        s_angle = self.current_second * (math.pi / 30.0)
        s_len = radius * 0.84
        sx = center_x + s_len * math.sin(s_angle)
        sy = center_y - s_len * math.cos(s_angle)
        painter.setPen(QPen(QColor("#dc2626"), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(center_x, center_y), QPointF(sx, sy))

        # Center Pivot Dot
        painter.setBrush(QColor("#dc2626"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(center_x - 3, center_y - 3, 6, 6))

        # 4. Digital Time & Date Below Dial
        painter.setFont(QFont(MONO_FONT, 8, QFont.Weight.Bold))
        painter.setPen(QColor("#0f172a"))
        painter.drawText(QRectF(0, 116, self.width(), 16), Qt.AlignmentFlag.AlignCenter, self.digital_str)

        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Normal))
        painter.setPen(QColor("#64748b"))
        painter.drawText(QRectF(0, 134, self.width(), 16), Qt.AlignmentFlag.AlignCenter, self.date_str)


class DigitalTimeCard(QFrame):
    """
    Clean digital card displaying timezone time, AM/PM, offset, and relative difference.
    """
    def __init__(self, city_name: str, zone_id: str, flag: str, parent=None):
        super().__init__(parent)
        self.city_name = city_name
        self.zone_id = zone_id
        self.flag = flag

        self.setStyleSheet("""
            DigitalTimeCard {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # Header Row
        row_top = QHBoxLayout()
        title_text = f"{city_name} ({flag})" if flag else city_name
        self.lbl_city = QLabel(title_text, self)
        self.lbl_city.setStyleSheet("font-weight: 700; font-size: 11px; color: #0f172a;")
        self.lbl_offset = QLabel("UTC", self)
        self.lbl_offset.setStyleSheet(f"font-size: 9px; color: #2563eb; font-family: {MONO_FONT}; font-weight: 700;")
        row_top.addWidget(self.lbl_city)
        row_top.addStretch(1)
        row_top.addWidget(self.lbl_offset)
        layout.addLayout(row_top)

        # Big Digital Time
        self.lbl_time = QLabel("00:00:00", self)
        self.lbl_time.setStyleSheet(f"font-size: 20px; font-weight: 700; color: #0f172a; font-family: {MONO_FONT};")
        layout.addWidget(self.lbl_time)

        # Date & Day Row
        row_btm = QHBoxLayout()
        self.lbl_date = QLabel("Monday, Jan 01", self)
        self.lbl_date.setStyleSheet("font-size: 10px; color: #64748b;")
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
    Professional light theme with Remix icons.
    """
    def __init__(self, prompt: str = "", default_mode: str = "circular", parent=None):
        super().__init__(parent)
        self.prompt = prompt
        self.setStyleSheet("background-color: #ffffff;")

        q = prompt.lower()
        if "digital" in q:
            self.mode = "digital"
        else:
            self.mode = default_mode

        self.timezones = parse_timezones_from_prompt(prompt)

        n = len(self.timezones)
        width = max(290, n * 135 + 24) if self.mode == "circular" else 300
        height = 240 if self.mode == "circular" else (n * 85 + 60)
        self.setFixedSize(width, height)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 8, 10, 8)
        self.main_layout.setSpacing(8)

        # Top Control Bar (Title + Mode Switcher)
        top_bar = QHBoxLayout()
        icon_lbl = QLabel(self)
        icon_lbl.setPixmap(qta.icon("ri.global-line", color="#0f172a").pixmap(14, 14))
        top_bar.addWidget(icon_lbl)

        self.title_lbl = QLabel("Time Comparison", self)
        self.title_lbl.setStyleSheet(f"font-weight: 700; font-size: 11px; color: #0f172a; font-family: {MONO_FONT};")
        top_bar.addWidget(self.title_lbl)
        top_bar.addStretch(1)

        self.btn_toggle = QPushButton(self)
        self.btn_toggle.setFixedHeight(24)
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.setStyleSheet("""
            QPushButton {
                background: #f1f5f9;
                color: #334155;
                font-size: 10px;
                font-weight: 600;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 2px 8px;
            }
            QPushButton:hover { background: #e2e8f0; color: #0f172a; }
        """)
        self._update_toggle_btn()
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

        self._tick()

    def _update_toggle_btn(self):
        if self.mode == "circular":
            self.btn_toggle.setText("Digital View")
            self.btn_toggle.setIcon(qta.icon("ri.dashboard-line", color="#334155"))
        else:
            self.btn_toggle.setText("Analog Dial")
            self.btn_toggle.setIcon(qta.icon("ri.time-line", color="#334155"))

    def _build_clocks(self):
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
            self.content_layout.setDirection(QHBoxLayout.Direction.TopToBottom)
            for name, zone_id, flag in self.timezones:
                card = DigitalTimeCard(city_name=name, zone_id=zone_id, flag=flag, parent=self)
                self.content_layout.addWidget(card)
                self.clock_items.append(card)

    def _toggle_mode(self):
        self.mode = "digital" if self.mode == "circular" else "circular"
        self._update_toggle_btn()

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
