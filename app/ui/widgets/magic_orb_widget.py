"""
PenEcho Magic Orb Widget for AI-TUTOR.
Ported from PenEcho's iconic Magic Orb and Auto-AI control bar.

Provides:
1. Animated glowing multi-state Magic Orb (Idle, Thinking, Draft Ready, Error).
2. Auto-AI vs Manual AI mode toggle with debounced post-stroke delay (0.5s - 5.0s).
3. Direct single-click AI trigger for canvas handwriting, math, and lasso selections.
"""

import math
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QMenu,
    QSlider, QGraphicsDropShadowEffect, QFrame
)
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QRadialGradient
from PyQt6.QtCore import Qt, QSize, QTimer, QRectF, QPointF, pyqtSignal


class MagicOrbWidget(QWidget):
    """
    PenEcho Magic Orb HUD Widget.
    """
    trigger_ai_requested = pyqtSignal()
    auto_ai_toggled = pyqtSignal(bool)
    delay_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._state = "idle"  # "idle", "thinking", "draft", "error"
        self._is_auto_ai = True
        self._auto_delay_sec = 2.0
        self._pulse_phase = 0.0

        # Pulse animation timer
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._on_pulse_tick)
        self._timer.start()

        self._init_ui()

    def _on_pulse_tick(self):
        self._pulse_phase = (self._pulse_phase + 0.08) % (math.pi * 2)
        if self._state in ("thinking", "draft"):
            self.orb_btn.update()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(8)

        # Pill Container
        self.container = QFrame(self)
        self.container.setStyleSheet("""
            QFrame {
                background: #0f172a;
                border: 1px solid #334155;
                border-radius: 18px;
            }
        """)

        c_layout = QHBoxLayout(self.container)
        c_layout.setContentsMargins(8, 2, 10, 2)
        c_layout.setSpacing(6)

        # 1. Glowing Orb Button
        self.orb_btn = OrbCanvasButton(magic_orb=self, parent=self.container)
        self.orb_btn.clicked.connect(self._on_orb_clicked)
        c_layout.addWidget(self.orb_btn)

        # 2. Mode Label & Status
        self.status_label = QLabel("Auto AI (2s)", self.container)
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold;")
        c_layout.addWidget(self.status_label)

        # 3. Settings / Mode Dropdown Button
        self.btn_mode_toggle = QPushButton("⚙", self.container)
        self.btn_mode_toggle.setFixedSize(22, 22)
        self.btn_mode_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_toggle.setToolTip("PenEcho AI Mode & Delay Settings")
        self.btn_mode_toggle.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748b;
                border: none;
                font-size: 13px;
            }
            QPushButton:hover { color: #38bdf8; }
        """)
        self.btn_mode_toggle.clicked.connect(self._show_settings_menu)
        c_layout.addWidget(self.btn_mode_toggle)

        layout.addWidget(self.container)

    def set_state(self, state: str, message: str = ""):
        self._state = state
        self.orb_btn._state = state
        self.orb_btn.update()

        if state == "thinking":
            self.status_label.setText(message or "Thinking...")
            self.status_label.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold;")
        elif state == "draft":
            self.status_label.setText(message or "Draft Ready ✓")
            self.status_label.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold;")
            # Return to idle label after 4s
            QTimer.singleShot(4000, lambda: self.set_state("idle"))
        elif state == "error":
            self.status_label.setText("AI Error")
            self.status_label.setStyleSheet("color: #f87171; font-size: 11px; font-weight: bold;")
            QTimer.singleShot(4000, lambda: self.set_state("idle"))
        else: # idle
            mode_text = f"Auto AI ({self._auto_delay_sec:.1f}s)" if self._is_auto_ai else "Manual AI"
            self.status_label.setText(mode_text)
            self.status_label.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold;")

    def _on_orb_clicked(self):
        self.trigger_ai_requested.emit()

    def _show_settings_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2563eb;
            }
        """)

        # Auto vs Manual Mode
        act_auto = menu.addAction("⚡ Auto AI Mode (Post-Stroke)" if not self._is_auto_ai else "✓ Auto AI Mode Active")
        act_manual = menu.addAction("🎯 Manual Mode (Click to Trigger)" if self._is_auto_ai else "✓ Manual Mode Active")

        menu.addSeparator()
        act_1s = menu.addAction("⏱ Delay: 1.0s (Fast)")
        act_2s = menu.addAction("⏱ Delay: 2.0s (Default)")
        act_3s = menu.addAction("⏱ Delay: 3.5s (Relaxed)")

        pos = self.btn_mode_toggle.mapToGlobal(self.btn_mode_toggle.rect().bottomLeft())
        selected = menu.exec(pos)

        if selected == act_auto:
            self._is_auto_ai = True
            self.auto_ai_toggled.emit(True)
            self.set_state("idle")
        elif selected == act_manual:
            self._is_auto_ai = False
            self.auto_ai_toggled.emit(False)
            self.set_state("idle")
        elif selected == act_1s:
            self._auto_delay_sec = 1.0
            self.delay_changed.emit(1.0)
            self.set_state("idle")
        elif selected == act_2s:
            self._auto_delay_sec = 2.0
            self.delay_changed.emit(2.0)
            self.set_state("idle")
        elif selected == act_3s:
            self._auto_delay_sec = 3.5
            self.delay_changed.emit(3.5)
            self.set_state("idle")


class OrbCanvasButton(QPushButton):
    """
    Renders the dynamic spherical pulsing gradient Magic Orb.
    """

    def __init__(self, magic_orb=None, parent=None):
        super().__init__(parent)
        self._magic_orb = magic_orb
        self.setFixedSize(26, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("PenEcho Magic Orb (Click to solve canvas / trigger AI)")
        self._state = "idle"

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        cx, cy = 13.0, 13.0
        base_r = 9.0

        pulse_phase = self._magic_orb._pulse_phase if self._magic_orb else 0.0
        is_auto = self._magic_orb._is_auto_ai if self._magic_orb else True
        pulse = math.sin(pulse_phase)

        if self._state == "thinking":
            r = base_r + pulse * 2.0
            color1 = QColor("#38bdf8")
            color2 = QColor("#6366f1")
        elif self._state == "draft":
            r = base_r + pulse * 1.5
            color1 = QColor("#4ade80")
            color2 = QColor("#059669")
        elif self._state == "error":
            r = base_r
            color1 = QColor("#f87171")
            color2 = QColor("#b91c1c")
        else: # idle
            r = base_r + (pulse * 0.8 if is_auto else 0.0)
            color1 = QColor("#818cf8")
            color2 = QColor("#4338ca")

        # Outer Glow Ring
        grad = QRadialGradient(QPointF(cx, cy), r + 4.0)
        grad.setColorAt(0.0, QColor(color1.red(), color1.green(), color1.blue(), 140))
        grad.setColorAt(1.0, QColor(color2.red(), color2.green(), color2.blue(), 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(QPointF(cx, cy), r + 4.0, r + 4.0)

        # Core Sphere Gradient
        core_grad = QRadialGradient(QPointF(cx - 2, cy - 2), r)
        core_grad.setColorAt(0.0, QColor("#ffffff"))
        core_grad.setColorAt(0.3, color1)
        core_grad.setColorAt(1.0, color2)

        painter.setPen(QPen(color1.lighter(130), 1.0))
        painter.setBrush(QBrush(core_grad))
        painter.drawEllipse(QPointF(cx, cy), r, r)
