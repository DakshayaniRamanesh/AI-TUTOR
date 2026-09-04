"""
FeatherAIButton — Feather-in-circle AI Trigger Button for AI-TUTOR.
Matches the monochrome technical aesthetic and exact feather line-art reference.

Provides:
- Circular 28x28 button with feather line-art icon
- Idle state: feather icon centered in circle, no label, no animation
- Active state ("Feathering…"): breathing pulse opacity animation + "Feathering…" label
- Zero layout shift: status label space is consistently reserved so sibling widgets never move
- Same public interface as MagicOrbWidget (trigger_ai_requested, set_state)
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel,
    QGraphicsOpacityEffect, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QSize, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer
)
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtSvg import QSvgRenderer

from ..theme_manager import ThemeManager
from ..kestrel_theme import MONO_FONT


class FeatherAIButton(QWidget):
    """
    Circular feather-icon AI trigger button.
    Replaces the Auto AI (2s) purple orb with a feather-in-circle trigger.
    """
    trigger_ai_requested = pyqtSignal()
    auto_ai_toggled = pyqtSignal(bool)
    delay_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._state = "idle"
        self._is_auto_ai = False
        self._auto_delay_sec = 2.0
        self._pulse_anim: QPropertyAnimation | None = None
        self._opacity_effect: QGraphicsOpacityEffect | None = None
        self._safety_timer: QTimer | None = None

        self._init_ui()
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme(ThemeManager.instance().current_theme)

    # ── UI Construction ────────────────────────────────────────────────────

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 1. Circular feather button (28x28, border-radius: 14px, matches mic button size & aesthetic)
        self.btn_feather = QPushButton(self)
        self.btn_feather.setObjectName("BtnFeather")
        self.btn_feather.setFixedSize(28, 28)
        self.btn_feather.setIconSize(QSize(18, 18))
        self.btn_feather.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_feather.setToolTip("Feather AI — Solve canvas math / handwriting")
        self.btn_feather.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_feather.clicked.connect(self._on_feather_clicked)
        layout.addWidget(self.btn_feather)

        # 2. Status label — fixed width reserved at all times to guarantee ZERO layout shift
        self.lbl_status = QLabel("", self)
        self.lbl_status.setObjectName("FeatherStatusLabel")
        self.lbl_status.setFixedWidth(82)  # reserved constant space for "Feathering…"
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.status_label = self.lbl_status  # alias for backward compatibility
        layout.addWidget(self.lbl_status)

    # ── Public API (matches MagicOrbWidget interface) ──────────────────────

    def set_state(self, state: str, message: str = ""):
        """
        Updates the visual state of the feather trigger:
        - "thinking": Starts pulse animation, displays "Feathering…"
        - "draft" / "idle" / "error": Stops pulse, clears label, returns to idle
        """
        self._state = state
        c = ThemeManager.instance().get_colors()

        if self._safety_timer is not None:
            self._safety_timer.stop()
            self._safety_timer = None

        if state == "thinking":
            self._start_pulse()
            self.lbl_status.setText(message or "Feathering…")
            self.lbl_status.setStyleSheet(
                f"font-family: {MONO_FONT}; font-size: 11px; font-weight: 600; "
                f"color: {c['text_secondary']}; background: transparent; padding-left: 2px;"
            )
            # Safety timeout: if no AI response returns after 10s, gracefully reset to idle
            self._safety_timer = QTimer(self)
            self._safety_timer.setSingleShot(True)
            self._safety_timer.timeout.connect(lambda: self.set_state("idle"))
            self._safety_timer.start(10000)

        elif state in ("draft", "error"):
            self._stop_pulse()
            self.lbl_status.setText("")
            self._state = state
            # Reset to idle after a brief moment
            QTimer.singleShot(1500, lambda: setattr(self, '_state', 'idle'))

        else:  # idle
            self._stop_pulse()
            self.lbl_status.setText("")
            self._state = "idle"

    # ── Click Handler ─────────────────────────────────────────────────────

    def _on_feather_clicked(self):
        if self._state == "idle":
            self.set_state("thinking", "Feathering…")
            self.trigger_ai_requested.emit()

    # ── Pulse Animation (matches mic button recording pattern) ────────────

    def _start_pulse(self):
        self._stop_pulse()
        self._opacity_effect = QGraphicsOpacityEffect(self.btn_feather)
        self._opacity_effect.setOpacity(1.0)
        self.btn_feather.setGraphicsEffect(self._opacity_effect)
        anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        anim.setDuration(900)
        anim.setStartValue(1.0)
        anim.setKeyValueAt(0.5, 0.45)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        anim.setLoopCount(-1)  # infinite continuous breathing pulse
        anim.start()
        self._pulse_anim = anim

    def _stop_pulse(self):
        if self._pulse_anim is not None:
            self._pulse_anim.stop()
            self._pulse_anim = None
        if self._opacity_effect is not None:
            self.btn_feather.setGraphicsEffect(None)
            self._opacity_effect = None

    # ── Theme Application ─────────────────────────────────────────────────

    def _apply_theme(self, theme_name: str = "light"):
        is_dark = ThemeManager.instance().is_dark()
        c = ThemeManager.instance().get_colors()

        # Load feather SVG/PNG icon asset matching reference
        assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
        svg_filename = "feather_icon_dark.svg" if is_dark else "feather_icon_light.svg"
        svg_path = os.path.join(assets_dir, svg_filename)

        if os.path.exists(svg_path):
            self.btn_feather.setIcon(QIcon(svg_path))
        else:
            png_filename = "feather_icon_dark.png" if is_dark else "feather_icon_light.png"
            png_path = os.path.join(assets_dir, png_filename)
            if os.path.exists(png_path):
                self.btn_feather.setIcon(QIcon(png_path))

        # Circular button styling consistent with monochrome theme & mic button
        bg_col = "#1a1a1f" if is_dark else "#f0f0f0"
        border_col = "#666666" if is_dark else "#888888"
        hover_bg = "#282830" if is_dark else "#e0e0e0"

        self.btn_feather.setStyleSheet(f"""
            QPushButton#BtnFeather {{
                background-color: {bg_col};
                border: 1px solid {border_col};
                border-radius: 14px;
                padding: 0px;
            }}
            QPushButton#BtnFeather:hover {{
                background-color: {hover_bg};
                border-color: {c['accent']};
            }}
            QPushButton#BtnFeather:pressed {{
                background-color: {c['accent']};
            }}
        """)

        self.lbl_status.setStyleSheet(f"""
            QLabel#FeatherStatusLabel {{
                font-family: {MONO_FONT};
                font-size: 11px;
                font-weight: 600;
                color: {c['text_secondary']};
                background: transparent;
                padding-left: 2px;
            }}
        """)


# Compatibility Alias
MagicOrbWidget = FeatherAIButton