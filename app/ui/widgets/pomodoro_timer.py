"""
Pomodoro Study Timer Floating Widget for Kestrel AI Notebook
- Floating draggable card docked at top-right of central window
- Header row with NO redundant 'POMODORO' text (clean minimal icon controls: ▾ presets, ─ minimize, ✕ close)
- Circular progress track with active completion arc
- Large digital countdown display (MM:SS) + progress percentage in JetBrains Mono font
- Preset duration selection (25m Focus, 15m Short Break, 5m Quick Break, Custom)
- START / PAUSE primary action button + circular Reset button
- Real-time countdown loop with tick signal for compact top bar badge
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGraphicsDropShadowEffect, QMenu, QInputDialog, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont
import qtawesome as qta

from ..theme_manager import ThemeManager

MONO_JETBRAINS = '"JetBrains Mono", "Space Mono", ui-monospace, "Consolas", monospace'


class CircularTimerGauge(QWidget):
    """
    Renders the circular progress ring with center digital countdown and percentage in JetBrains Mono.
    """
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(160, 160)
        self.total_seconds = 25 * 60
        self.remaining_seconds = 25 * 60
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_time(self, remaining: int, total: int):
        self.remaining_seconds = max(0, remaining)
        self.total_seconds = max(1, total)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
        else:
            super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        c = ThemeManager.instance().get_colors()
        is_dark = ThemeManager.instance().is_dark()

        rect = QRectF(14, 14, self.width() - 28, self.height() - 28)
        pen_width = 7.0

        # Background Track
        track_color = QColor("#26262c") if is_dark else QColor("#e5e5ea")
        track_pen = QPen(track_color, pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect)

        # Active Progress Arc
        progress = 1.0 - (self.remaining_seconds / self.total_seconds) if self.total_seconds > 0 else 0.0
        if progress > 0.0:
            arc_color = QColor(c["accent"])
            arc_pen = QPen(arc_color, pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(arc_pen)
            start_angle = 90 * 16
            span_angle = -int(progress * 360 * 16)
            painter.drawArc(rect, start_angle, span_angle)

        # Center Text: Time (MM:SS) in JetBrains Mono
        mins = self.remaining_seconds // 60
        secs = self.remaining_seconds % 60
        time_str = f"{mins:02d}:{secs:02d}"

        painter.setPen(QColor(c["text_primary"]))
        font_time = QFont("JetBrains Mono", 20, QFont.Weight.Bold)
        font_time.setStyleHint(QFont.StyleHint.Monospace)
        painter.setFont(font_time)
        painter.drawText(QRectF(0, 50, self.width(), 32), Qt.AlignmentFlag.AlignCenter, time_str)

        # Center Text: Percentage
        pct_str = f"{int(progress * 100)}%"
        painter.setPen(QColor(c["text_secondary"]))
        font_pct = QFont("JetBrains Mono", 10, QFont.Weight.Bold)
        font_pct.setStyleHint(QFont.StyleHint.Monospace)
        painter.setFont(font_pct)
        painter.drawText(QRectF(0, 84, self.width(), 20), Qt.AlignmentFlag.AlignCenter, pct_str)


class PomodoroTimerWidget(QWidget):
    """
    Floating Pomodoro Study Timer card docked at top of the app.
    """
    time_updated = pyqtSignal(str, bool)  # (time_str, is_running)
    minimized = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(240, 290)

        self._duration_seconds = 25 * 60
        self._remaining_seconds = 25 * 60
        self._is_running = False
        self._drag_pos = None

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

        self._setup_ui()
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme(ThemeManager.instance().current_theme)

    def _setup_ui(self):
        self.setObjectName("PomodoroCard")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

        self.layout_main = QVBoxLayout(self)
        self.layout_main.setContentsMargins(14, 10, 14, 12)
        self.layout_main.setSpacing(8)

        # ── 1. Minimal Header (No redundant text label) ──
        self.header_bar = QWidget(self)
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        # Timer Icon & Preset selector
        self.btn_presets = QPushButton(self.header_bar)
        self.btn_presets.setIcon(qta.icon("ri.timer-line", color="#888888"))
        self.btn_presets.setText("")
        self.btn_presets.setFixedHeight(24)
        self.btn_presets.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_presets.setToolTip("Select duration presets")
        self.btn_presets.clicked.connect(self._show_preset_menu)
        header_layout.addWidget(self.btn_presets)

        header_layout.addStretch()

        # Minimize Button
        self.btn_minimize = QPushButton(self.header_bar)
        self.btn_minimize.setIcon(qta.icon("ri.subtract-line", color="#888888"))
        self.btn_minimize.setFixedSize(22, 22)
        self.btn_minimize.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_minimize.setToolTip("Minimize to top bar badge")
        self.btn_minimize.clicked.connect(self._on_minimize_clicked)
        header_layout.addWidget(self.btn_minimize)

        # Close Button
        self.btn_close = QPushButton(self.header_bar)
        self.btn_close.setIcon(qta.icon("ri.close-line", color="#888888"))
        self.btn_close.setFixedSize(22, 22)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setToolTip("Close timer")
        self.btn_close.clicked.connect(self._on_close_clicked)
        header_layout.addWidget(self.btn_close)

        self.layout_main.addWidget(self.header_bar)

        # ── 2. Timer Body (Gauge + Controls) ──
        self.body_widget = QWidget(self)
        b_layout = QVBoxLayout(self.body_widget)
        b_layout.setContentsMargins(0, 0, 0, 0)
        b_layout.setSpacing(8)
        b_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Circular Gauge
        self.gauge = CircularTimerGauge(self.body_widget)
        self.gauge.clicked.connect(self._show_preset_menu)
        b_layout.addWidget(self.gauge, alignment=Qt.AlignmentFlag.AlignCenter)

        # Status Label (Shows on session complete)
        self.lbl_status = QLabel("", self.body_widget)
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setVisible(False)
        b_layout.addWidget(self.lbl_status)

        # Controls Row: [ START ] [ ⟳ ]
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_start = QPushButton("START", self.body_widget)
        self.btn_start.setFixedHeight(34)
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.clicked.connect(self._toggle_start_pause)
        btn_row.addWidget(self.btn_start, stretch=1)

        self.btn_reset = QPushButton(self.body_widget)
        self.btn_reset.setIcon(qta.icon("ri.restart-line", color="#888888"))
        self.btn_reset.setFixedSize(34, 34)
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.setToolTip("Reset timer")
        self.btn_reset.clicked.connect(self.reset_timer)
        btn_row.addWidget(self.btn_reset)

        b_layout.addLayout(btn_row)
        self.layout_main.addWidget(self.body_widget)

    def _apply_theme(self, theme_name: str = "light"):
        c = ThemeManager.instance().get_colors()

        self.setStyleSheet(f"""
            QWidget#PomodoroCard {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border_color']};
                border-radius: 8px;
            }}
            QPushButton {{
                border: none;
                background: transparent;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {c['panel_card_bg']};
            }}
        """)

        self.btn_presets.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {c['border_color']};
                border-radius: 3px;
                padding: 2px 6px;
                font-family: {MONO_JETBRAINS};
                font-size: 11px;
                color: {c['text_secondary']};
            }}
            QPushButton:hover {{
                color: {c['text_primary']};
                border-color: {c['accent']};
            }}
        """)

        self.btn_start.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['accent']};
                color: {c['accent_text']};
                border-radius: 4px;
                font-family: {MONO_JETBRAINS};
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{
                background-color: {c['accent_hover']};
            }}
        """)

        self.btn_reset.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['panel_card_bg']};
                border: 1px solid {c['border_color']};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border-color: {c['accent']};
            }}
        """)

        self.lbl_status.setStyleSheet(f"""
            font-family: {MONO_JETBRAINS};
            font-size: 11px;
            font-weight: 700;
            color: {c['text_primary']};
            background: transparent;
        """)

        self.gauge.update()

    def get_time_string(self) -> str:
        mins = self._remaining_seconds // 60
        secs = self._remaining_seconds % 60
        return f"{mins:02d}:{secs:02d}"

    def _on_tick(self):
        if self._remaining_seconds > 0:
            self._remaining_seconds -= 1
            self.gauge.set_time(self._remaining_seconds, self._duration_seconds)
            self.time_updated.emit(self.get_time_string(), self._is_running)
            if self._remaining_seconds == 0:
                self._timer.stop()
                self._is_running = False
                self.btn_start.setText("START")
                self.lbl_status.setText("SESSION COMPLETE")
                self.lbl_status.setVisible(True)
                self.time_updated.emit(self.get_time_string(), False)

    def _toggle_start_pause(self):
        if self._is_running:
            self._timer.stop()
            self._is_running = False
            self.btn_start.setText("RESUME")
        else:
            if self._remaining_seconds == 0:
                self._remaining_seconds = self._duration_seconds
            self._timer.start()
            self._is_running = True
            self.btn_start.setText("PAUSE")
            self.lbl_status.setVisible(False)
        self.gauge.set_time(self._remaining_seconds, self._duration_seconds)
        self.time_updated.emit(self.get_time_string(), self._is_running)

    def reset_timer(self):
        self._timer.stop()
        self._is_running = False
        self._remaining_seconds = self._duration_seconds
        self.btn_start.setText("START")
        self.lbl_status.setVisible(False)
        self.gauge.set_time(self._remaining_seconds, self._duration_seconds)
        self.time_updated.emit(self.get_time_string(), False)

    def set_duration(self, minutes: int):
        self._duration_seconds = max(1, minutes) * 60
        self.reset_timer()

    def _show_preset_menu(self):
        menu = QMenu(self)
        c = ThemeManager.instance().get_colors()
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border_color']};
                font-family: {MONO_JETBRAINS};
                font-size: 11px;
                color: {c['text_primary']};
                padding: 4px;
                border-radius: 4px;
            }}
            QMenu::item {{
                padding: 6px 14px;
                border-radius: 2px;
            }}
            QMenu::item:selected {{
                background-color: {c['panel_card_bg']};
            }}
        """)

        act_25 = menu.addAction("25m  Focus Session")
        act_15 = menu.addAction("15m  Short Break")
        act_5 = menu.addAction("5m   Quick Break")
        menu.addSeparator()
        act_custom = menu.addAction("Custom Duration...")

        action = menu.exec(self.btn_presets.mapToGlobal(QPoint(0, self.btn_presets.height())))
        if action == act_25:
            self.set_duration(25)
        elif action == act_15:
            self.set_duration(15)
        elif action == act_5:
            self.set_duration(5)
        elif action == act_custom:
            val, ok = QInputDialog.getInt(self, "Custom Duration", "Minutes:", value=self._duration_seconds // 60, min=1, max=180)
            if ok:
                self.set_duration(val)

    def _on_minimize_clicked(self):
        self.hide()
        self.minimized.emit()

    def _on_close_clicked(self):
        self.hide()
        self.closed.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.header_bar.geometry().contains(event.position().toPoint()):
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)
