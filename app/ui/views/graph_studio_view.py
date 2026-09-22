"""
Desmos-Style Interactive Graphing Studio View (2D Curves, 3D Surfaces, Complex Analysis)
Clean, professional light theme matching Kestrel design system and academic workstations.
No emojis or neon styling — uses crisp typography, Remix icons, and high-contrast palettes.
"""

import os
import re
import math
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from mpl_toolkits.mplot3d import Axes3D

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QSlider, QFrame, QSplitter, QScrollArea, QCheckBox,
    QFileDialog, QMessageBox, QSizePolicy, QToolButton
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFont, QColor
import qtawesome as qta

from ..kestrel_theme import MONO_FONT


# ── Math Sanitization & Evaluation Helpers ─────────────────────────────────────

def sanitize_math_expression(expr_str: str) -> str:
    """Prepares user formula for safe evaluation with numpy."""
    s = expr_str.strip().replace("^", "**")
    s = re.sub(r"(\d)([a-zA-Z\(])", r"\1*\2", s)
    s = re.sub(r"\)([a-zA-Z0-9\(])", r")*\1", s)
    return s


def eval_2d_function(expr: str, x: np.ndarray, a: float = 1.0, b: float = 0.0) -> np.ndarray:
    """Evaluates 1D array y = f(x, a, b) safely."""
    prep = sanitize_math_expression(expr)
    scope = {
        "x": x, "a": a, "b": b, "t": x,
        "sin": np.sin, "cos": np.cos, "tan": np.tan,
        "asin": np.arcsin, "acos": np.arccos, "atan": np.arctan,
        "arcsin": np.arcsin, "arccos": np.arccos, "arctan": np.arctan,
        "sinh": np.sinh, "cosh": np.cosh, "tanh": np.tanh,
        "exp": np.exp, "log": np.log, "ln": np.log, "log10": np.log10,
        "sqrt": np.sqrt, "abs": np.abs,
        "pi": np.pi, "e": np.e,
    }
    y = eval(prep, {"__builtins__": {}}, scope)
    if isinstance(y, (int, float)):
        y = np.full_like(x, float(y))
    return np.asarray(y, dtype=float)


def eval_3d_surface(expr: str, X: np.ndarray, Y: np.ndarray, a: float = 1.0, b: float = 0.0) -> np.ndarray:
    """Evaluates 2D grid z = f(x, y, a, b) safely."""
    prep = sanitize_math_expression(expr)
    scope = {
        "x": X, "y": Y, "a": a, "b": b,
        "sin": np.sin, "cos": np.cos, "tan": np.tan,
        "asin": np.arcsin, "acos": np.arccos, "atan": np.arctan,
        "sinh": np.sinh, "cosh": np.cosh, "tanh": np.tanh,
        "exp": np.exp, "log": np.log, "ln": np.log, "log10": np.log10,
        "sqrt": np.sqrt, "abs": np.abs,
        "pi": np.pi, "e": np.e,
    }
    z = eval(prep, {"__builtins__": {}}, scope)
    if isinstance(z, (int, float)):
        z = np.full_like(X, float(z))
    return np.asarray(z, dtype=float)


def eval_complex_function(expr: str, Z: np.ndarray, a: float = 1.0) -> np.ndarray:
    """Evaluates complex mapping w = f(z, a) safely."""
    prep = sanitize_math_expression(expr)
    scope = {
        "z": Z, "a": a,
        "sin": np.sin, "cos": np.cos, "tan": np.tan,
        "exp": np.exp, "log": np.log, "ln": np.log,
        "sqrt": np.sqrt, "abs": np.abs,
        "pi": np.pi, "e": np.e,
    }
    w = eval(prep, {"__builtins__": {}}, scope)
    if isinstance(w, (int, float, complex)):
        w = np.full_like(Z, complex(w))
    return np.asarray(w, dtype=complex)


# ── Built-In Math Presets ──────────────────────────────────────────────────────

PRESETS_2D = [
    ("Polynomial & Extrema", "x^3 - 3*x + a"),
    ("Fourier Harmonic Series", "sin(x) + (1/3)*sin(3*x)"),
    ("Damped Harmonic Oscillation", "exp(-0.2*x) * cos(a*x)"),
    ("Gaussian Normal Distribution", "exp(-x^2 / (2*a^2)) / (sqrt(2*pi)*a)"),
    ("Rational Hyperbola", "1 / (x^2 - a^2 + 1e-6)"),
    ("Logistic Sigmoid Function", "1 / (1 + exp(-a*x))"),
    ("Chirp Waveform", "sin(a * x^2)"),
]

PRESETS_3D = [
    ("Sombrero Ripple Surface", "sin(sqrt(x^2 + y^2) * a) / (sqrt(x^2 + y^2) + 0.05)"),
    ("Hyperbolic Paraboloid (Saddle)", "a * (x^2 - y^2)"),
    ("Monkey Saddle (Cubic)", "x^3 - 3*x*y^2"),
    ("Paraboloid Basin", "a * (x^2 + y^2)"),
    ("Gaussian Surface Peak", "exp(-a * (x^2 + y^2))"),
    ("Egg Crate Wave", "cos(a*x) * sin(a*y)"),
]

PRESETS_COMPLEX = [
    ("Roots of Unity", "z^3 - 1"),
    ("Complex Exponential", "exp(a * z)"),
    ("Inversion / Simple Pole", "1 / (z + 1e-9)"),
    ("Poles & Zeros Rational", "(z - a) / (z^2 + 1)"),
    ("Complex Sine Wave", "sin(a * z)"),
    ("Essential Singularity", "exp(1 / (z + 1e-9))"),
    ("Möbius Mapping", "(z - 1) / (z + 1)"),
]

# High-contrast, clean academic color palette for 2D curves
COLOR_PALETTE_2D = ["#2563eb", "#dc2626", "#059669", "#7c3aed", "#d97706", "#0891b2"]


# ── Main GraphStudioView ───────────────────────────────────────────────────────

class GraphStudioView(QWidget):
    """
    Desmos-inspired Graphing Studio in clean, academic light theme.
    Supports:
    - 2D Function & Multi-Curve Plotting
    - 3D Interactive Surfaces & Manifolds
    - Complex Domain Coloring Phase Portraits & 3D Riemann Surfaces
    - Live parameter slider animation
    - Whiteboard canvas insertion & PNG export
    """

    insert_to_canvas_requested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GraphStudioView")
        self.setStyleSheet("background-color: #f8fafc;")

        # State
        self.current_mode = "2d" # '2d', '3d', 'complex_2d', 'complex_3d'
        self.slider_a_val = 1.0
        self.slider_b_val = 0.0
        self.equations_2d = [
            {"expr": "sin(x) + 0.3*sin(3*x)", "color": "#2563eb", "visible": True},
            {"expr": "exp(-0.2*x) * cos(x)", "color": "#dc2626", "visible": True}
        ]
        self.expr_3d = "sin(sqrt(x^2 + y^2)) / (sqrt(x^2 + y^2) + 0.05)"
        self.expr_complex = "z^3 - 1"
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(35)
        self.anim_timer.timeout.connect(self._on_anim_step)
        self.anim_direction = 1

        self._init_ui()
        self._plot_current()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #e2e8f0;
                width: 1px;
            }
        """)

        left_panel = self._create_left_controls()
        splitter.addWidget(left_panel)

        right_canvas = self._create_plot_canvas()
        splitter.addWidget(right_canvas)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([330, 820])

        main_layout.addWidget(splitter)

    def _create_left_controls(self) -> QWidget:
        panel = QWidget(self)
        panel.setFixedWidth(330)
        panel.setStyleSheet("background-color: #ffffff; border-right: 1px solid #e2e8f0;")

        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(16, 16, 16, 16)
        vbox.setSpacing(12)

        # 1. Header with Remix Icon & Title
        hdr_row = QHBoxLayout()
        icon_lbl = QLabel(panel)
        icon_lbl.setPixmap(qta.icon("ri.function-line", color="#0f172a").pixmap(18, 18))
        hdr_row.addWidget(icon_lbl)

        lbl_title = QLabel("Graph Studio", panel)
        lbl_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: #0f172a; font-family: {MONO_FONT};")
        hdr_row.addWidget(lbl_title)
        hdr_row.addStretch()

        badge = QLabel("2D / 3D / Complex", panel)
        badge.setStyleSheet("font-size: 10px; font-weight: 600; color: #475569; background: #f1f5f9; padding: 2px 8px; border-radius: 4px; border: 1px solid #e2e8f0;")
        hdr_row.addWidget(badge)
        vbox.addLayout(hdr_row)

        # 2. Segmented Mode Control
        mode_box = QHBoxLayout()
        mode_box.setSpacing(4)
        self.btn_mode_2d = QPushButton("2D Curves", panel)
        self.btn_mode_3d = QPushButton("3D Surface", panel)
        self.btn_mode_comp2d = QPushButton("Complex 2D", panel)
        self.btn_mode_comp3d = QPushButton("Riemann 3D", panel)

        self.mode_buttons = [self.btn_mode_2d, self.btn_mode_3d, self.btn_mode_comp2d, self.btn_mode_comp3d]
        mode_keys = ["2d", "3d", "complex_2d", "complex_3d"]

        for btn, key in zip(self.mode_buttons, mode_keys):
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda ch, k=key: self._set_mode(k))
            mode_box.addWidget(btn)

        self._update_mode_button_styles()
        vbox.addLayout(mode_box)

        # 3. Presets Dropdown Row
        preset_row = QHBoxLayout()
        lbl_preset = QLabel("Preset:", panel)
        lbl_preset.setStyleSheet("font-size: 11px; color: #475569; font-weight: 600;")
        self.preset_combo = QComboBox(panel)
        self.preset_combo.setFixedHeight(28)
        self.preset_combo.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #ffffff; color: #0f172a; selection-background-color: #2563eb; selection-color: #ffffff; }
        """)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        preset_row.addWidget(lbl_preset)
        preset_row.addWidget(self.preset_combo, stretch=1)
        vbox.addLayout(preset_row)

        # 4. Scrollable Container for Equations
        scroll = QScrollArea(panel)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.eq_container = QWidget()
        self.eq_layout = QVBoxLayout(self.eq_container)
        self.eq_layout.setContentsMargins(0, 0, 0, 0)
        self.eq_layout.setSpacing(8)
        scroll.setWidget(self.eq_container)
        vbox.addWidget(scroll, stretch=1)

        # 5. Parameter Slider `a` (Desmos Style Variable)
        slider_box = QVBoxLayout()
        slider_box.setSpacing(4)
        slider_hdr = QHBoxLayout()
        self.lbl_slider_a = QLabel("Parameter a = 1.00", panel)
        self.lbl_slider_a.setStyleSheet(f"font-size: 11px; color: #0f172a; font-family: {MONO_FONT}; font-weight: 700;")
        
        self.btn_play_anim = QPushButton(panel)
        self.btn_play_anim.setIcon(qta.icon("ri.play-line", color="#334155"))
        self.btn_play_anim.setText("Animate")
        self.btn_play_anim.setFixedSize(80, 24)
        self.btn_play_anim.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play_anim.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #334155;
                font-size: 10px;
                font-weight: 600;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #e2e8f0; color: #0f172a; }
        """)
        self.btn_play_anim.clicked.connect(self._toggle_animation)
        slider_hdr.addWidget(self.lbl_slider_a)
        slider_hdr.addStretch()
        slider_hdr.addWidget(self.btn_play_anim)
        slider_box.addLayout(slider_hdr)

        self.slider_a = QSlider(Qt.Orientation.Horizontal, panel)
        self.slider_a.setRange(-500, 500)
        self.slider_a.setValue(100)
        self.slider_a.setStyleSheet("""
            QSlider::groove:horizontal { height: 4px; background: #e2e8f0; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #2563eb; border-radius: 2px; }
            QSlider::handle:horizontal { background: #ffffff; border: 2px solid #2563eb; width: 14px; margin: -5px 0; border-radius: 7px; }
        """)
        self.slider_a.valueChanged.connect(self._on_slider_a_changed)
        slider_box.addWidget(self.slider_a)
        vbox.addLayout(slider_box)

        # 6. Action Buttons
        btn_plot = QPushButton(panel)
        btn_plot.setIcon(qta.icon("ri.refresh-line", color="#ffffff"))
        btn_plot.setText("Plot Graph")
        btn_plot.setFixedHeight(32)
        btn_plot.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_plot.setStyleSheet("""
            QPushButton {
                background-color: #0f172a;
                color: #ffffff;
                font-weight: 600;
                font-size: 12px;
                border-radius: 4px;
                padding: 4px 12px;
            }
            QPushButton:hover { background-color: #1e293b; }
        """)
        btn_plot.clicked.connect(self._plot_current)
        vbox.addWidget(btn_plot)

        btn_row = QHBoxLayout()
        btn_canvas = QPushButton(panel)
        btn_canvas.setIcon(qta.icon("ri.add-box-line", color="#0f172a"))
        btn_canvas.setText("Insert to Canvas")
        btn_canvas.setFixedHeight(30)
        btn_canvas.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_canvas.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #0f172a;
                font-weight: 600;
                font-size: 11px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        btn_canvas.clicked.connect(self._insert_to_canvas)

        btn_export = QPushButton(panel)
        btn_export.setIcon(qta.icon("ri.download-line", color="#0f172a"))
        btn_export.setText("Save PNG")
        btn_export.setFixedHeight(30)
        btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #0f172a;
                font-weight: 600;
                font-size: 11px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        btn_export.clicked.connect(self._export_png)

        btn_row.addWidget(btn_canvas)
        btn_row.addWidget(btn_export)
        vbox.addLayout(btn_row)

        self._populate_presets()
        self._refresh_equation_inputs()
        return panel

    def _create_plot_canvas(self) -> QWidget:
        container = QWidget(self)
        container.setStyleSheet("background-color: #ffffff;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        # Light Matplotlib Figure
        self.figure = Figure(figsize=(7, 6), dpi=100, facecolor="#ffffff")
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas.mpl_connect("motion_notify_event", self._on_canvas_mouse_move)
        layout.addWidget(self.canvas)

        # Coordinate status footer
        self.status_bar = QLabel("Coordinates: X = 0.00, Y = 0.00", container)
        self.status_bar.setStyleSheet(f"font-size: 10px; color: #64748b; font-family: {MONO_FONT}; padding-left: 4px;")
        layout.addWidget(self.status_bar)

        return container

    def _set_mode(self, mode: str):
        self.current_mode = mode
        self._update_mode_button_styles()
        self._populate_presets()
        self._refresh_equation_inputs()
        self._plot_current()

    def _update_mode_button_styles(self):
        modes = ["2d", "3d", "complex_2d", "complex_3d"]
        for btn, m in zip(self.mode_buttons, modes):
            if m == self.current_mode:
                btn.setChecked(True)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #0f172a;
                        color: #ffffff;
                        font-weight: 700;
                        font-size: 10px;
                        border-radius: 4px;
                        border: 1px solid #0f172a;
                    }
                """)
            else:
                btn.setChecked(False)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #f8fafc;
                        color: #475569;
                        font-weight: 600;
                        font-size: 10px;
                        border-radius: 4px;
                        border: 1px solid #e2e8f0;
                    }
                    QPushButton:hover { background-color: #f1f5f9; color: #0f172a; }
                """)

    def _populate_presets(self):
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem("-- Presets --", "")

        if self.current_mode == "2d":
            for name, expr in PRESETS_2D:
                self.preset_combo.addItem(name, expr)
        elif self.current_mode == "3d":
            for name, expr in PRESETS_3D:
                self.preset_combo.addItem(name, expr)
        else:
            for name, expr in PRESETS_COMPLEX:
                self.preset_combo.addItem(name, expr)

        self.preset_combo.blockSignals(False)

    def _on_preset_selected(self, index: int):
        expr = self.preset_combo.currentData()
        if not expr:
            return
        if self.current_mode == "2d":
            if self.equations_2d:
                self.equations_2d[0]["expr"] = expr
            else:
                self.equations_2d.append({"expr": expr, "color": "#2563eb", "visible": True})
        elif self.current_mode == "3d":
            self.expr_3d = expr
        else:
            self.expr_complex = expr

        self._refresh_equation_inputs()
        self._plot_current()

    def _refresh_equation_inputs(self):
        while self.eq_layout.count():
            item = self.eq_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self.current_mode == "2d":
            lbl_info = QLabel("Functions (y = f(x)):", self.eq_container)
            lbl_info.setStyleSheet("font-size: 11px; color: #475569; font-weight: 700;")
            self.eq_layout.addWidget(lbl_info)

            for i, eq in enumerate(self.equations_2d):
                row = QHBoxLayout()
                row.setSpacing(6)

                # Color swatch indicator
                swatch = QFrame(self.eq_container)
                swatch.setFixedSize(12, 12)
                swatch.setStyleSheet(f"background-color: {eq['color']}; border-radius: 6px; border: 1px solid #cbd5e1;")
                row.addWidget(swatch)

                inp = QLineEdit(eq["expr"], self.eq_container)
                inp.setStyleSheet("QLineEdit { background: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; font-family: monospace; font-size: 11px; }")
                inp.textChanged.connect(lambda txt, idx=i: self._on_eq_text_changed(idx, txt))
                inp.returnPressed.connect(self._plot_current)
                row.addWidget(inp, stretch=1)

                btn_vis = QPushButton(self.eq_container)
                btn_vis.setFixedSize(24, 24)
                btn_vis.setCheckable(True)
                btn_vis.setChecked(eq["visible"])
                icon_name = "ri.eye-line" if eq["visible"] else "ri.eye-off-line"
                btn_vis.setIcon(qta.icon(icon_name, color="#64748b"))
                btn_vis.setToolTip("Toggle visibility")
                btn_vis.clicked.connect(lambda ch, idx=i: self._toggle_eq_vis(idx))
                btn_vis.setStyleSheet("QPushButton { background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 4px; } QPushButton:hover { background: #e2e8f0; }")
                row.addWidget(btn_vis)

                if len(self.equations_2d) > 1:
                    btn_del = QPushButton(self.eq_container)
                    btn_del.setFixedSize(24, 24)
                    btn_del.setIcon(qta.icon("ri.delete-bin-line", color="#dc2626"))
                    btn_del.setToolTip("Remove function")
                    btn_del.clicked.connect(lambda _, idx=i: self._remove_eq(idx))
                    btn_del.setStyleSheet("QPushButton { background: #fef2f2; border: 1px solid #fecaca; border-radius: 4px; } QPushButton:hover { background: #fee2e2; }")
                    row.addWidget(btn_del)

                self.eq_layout.addLayout(row)

            btn_add = QPushButton("Add Expression", self.eq_container)
            btn_add.setIcon(qta.icon("ri.add-line", color="#2563eb"))
            btn_add.setFixedHeight(26)
            btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_add.setStyleSheet("QPushButton { background: #ffffff; color: #2563eb; border: 1px dashed #2563eb; border-radius: 4px; font-weight: 600; font-size: 11px; } QPushButton:hover { background: #eff6ff; }")
            btn_add.clicked.connect(self._add_equation)
            self.eq_layout.addWidget(btn_add)

        elif self.current_mode == "3d":
            lbl_info = QLabel("Surface (z = f(x, y)):", self.eq_container)
            lbl_info.setStyleSheet("font-size: 11px; color: #475569; font-weight: 700;")
            self.eq_layout.addWidget(lbl_info)

            self.inp_3d = QLineEdit(self.expr_3d, self.eq_container)
            self.inp_3d.setStyleSheet("QLineEdit { background: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 6px 8px; font-family: monospace; font-size: 12px; }")
            self.inp_3d.textChanged.connect(lambda txt: setattr(self, 'expr_3d', txt))
            self.inp_3d.returnPressed.connect(self._plot_current)
            self.eq_layout.addWidget(self.inp_3d)

            tip = QLabel("Click and drag on the 3D plot to rotate elevation and azimuth.", self.eq_container)
            tip.setWordWrap(True)
            tip.setStyleSheet("font-size: 10px; color: #64748b; padding: 4px;")
            self.eq_layout.addWidget(tip)

        else:
            title = "Complex Mapping f(z):" if self.current_mode == "complex_2d" else "Riemann Surface |f(z)|:"
            lbl_info = QLabel(title, self.eq_container)
            lbl_info.setStyleSheet("font-size: 11px; color: #475569; font-weight: 700;")
            self.eq_layout.addWidget(lbl_info)

            self.inp_complex = QLineEdit(self.expr_complex, self.eq_container)
            self.inp_complex.setStyleSheet("QLineEdit { background: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 6px 8px; font-family: monospace; font-size: 12px; }")
            self.inp_complex.textChanged.connect(lambda txt: setattr(self, 'expr_complex', txt))
            self.inp_complex.returnPressed.connect(self._plot_current)
            self.eq_layout.addWidget(self.inp_complex)

            tip_desc = (
                "Domain Coloring: Hue corresponds to phase angle Arg(f(z)); concentric contours show magnitude |f(z)|."
                if self.current_mode == "complex_2d" else
                "Riemann Surface: Height represents magnitude |f(z)|, colored by phase angle."
            )
            tip = QLabel(tip_desc, self.eq_container)
            tip.setWordWrap(True)
            tip.setStyleSheet("font-size: 10px; color: #475569; background: #f1f5f9; border-radius: 4px; padding: 8px; border: 1px solid #e2e8f0;")
            self.eq_layout.addWidget(tip)

        self.eq_layout.addStretch(1)

    def _on_eq_text_changed(self, idx: int, text: str):
        if 0 <= idx < len(self.equations_2d):
            self.equations_2d[idx]["expr"] = text

    def _toggle_eq_vis(self, idx: int):
        if 0 <= idx < len(self.equations_2d):
            self.equations_2d[idx]["visible"] = not self.equations_2d[idx]["visible"]
            self._refresh_equation_inputs()
            self._plot_current()

    def _remove_eq(self, idx: int):
        if 0 <= idx < len(self.equations_2d):
            self.equations_2d.pop(idx)
            self._refresh_equation_inputs()
            self._plot_current()

    def _add_equation(self):
        col = COLOR_PALETTE_2D[len(self.equations_2d) % len(COLOR_PALETTE_2D)]
        self.equations_2d.append({"expr": "cos(x)", "color": col, "visible": True})
        self._refresh_equation_inputs()
        self._plot_current()

    def _on_slider_a_changed(self, val: int):
        self.slider_a_val = val / 100.0
        self.lbl_slider_a.setText(f"Parameter a = {self.slider_a_val:.2f}")
        self._plot_current()

    def _toggle_animation(self):
        if self.anim_timer.isActive():
            self.anim_timer.stop()
            self.btn_play_anim.setIcon(qta.icon("ri.play-line", color="#334155"))
            self.btn_play_anim.setText("Animate")
            self.btn_play_anim.setStyleSheet("QPushButton { background-color: #f1f5f9; color: #334155; font-size: 10px; font-weight: 600; border: 1px solid #cbd5e1; border-radius: 4px; }")
        else:
            self.anim_timer.start()
            self.btn_play_anim.setIcon(qta.icon("ri.pause-line", color="#ffffff"))
            self.btn_play_anim.setText("Pause")
            self.btn_play_anim.setStyleSheet("QPushButton { background-color: #dc2626; color: #ffffff; font-size: 10px; font-weight: 600; border: 1px solid #b91c1c; border-radius: 4px; }")

    def _on_anim_step(self):
        val = self.slider_a.value() + self.anim_direction * 8
        if val >= 400:
            self.anim_direction = -1
        elif val <= -400:
            self.anim_direction = 1
        self.slider_a.setValue(val)

    # ── Rendering Engines ─────────────────────────────────────────────────────

    def _plot_current(self):
        self.figure.clear()

        try:
            if self.current_mode == "2d":
                self._render_2d_plot()
            elif self.current_mode == "3d":
                self._render_3d_plot()
            elif self.current_mode == "complex_2d":
                self._render_complex_2d()
            elif self.current_mode == "complex_3d":
                self._render_complex_3d()
        except Exception as err:
            ax = self.figure.add_subplot(111)
            ax.set_facecolor("#ffffff")
            ax.text(0.5, 0.5, f"Syntax Error:\n{err}",
                    color="#dc2626", fontsize=10, ha="center", va="center", transform=ax.transAxes)

        self.canvas.draw_idle()

    def _render_2d_plot(self):
        ax = self.figure.add_subplot(111)
        ax.set_facecolor("#ffffff")
        self.figure.patch.set_facecolor("#ffffff")

        x_min, x_max = -10.0, 10.0
        x = np.linspace(x_min, x_max, 1000)

        # Crisp light grid & coordinate axes
        ax.axhline(0, color="#64748b", linewidth=1.0, linestyle="-")
        ax.axvline(0, color="#64748b", linewidth=1.0, linestyle="-")
        ax.grid(True, color="#e2e8f0", linestyle="--", linewidth=0.6, alpha=0.8)

        plotted_any = False
        for eq in self.equations_2d:
            if not eq["visible"] or not eq["expr"].strip():
                continue
            try:
                y = eval_2d_function(eq["expr"], x, a=self.slider_a_val, b=self.slider_b_val)
                y_clean = np.copy(y)
                y_clean[np.abs(y_clean) > 80] = np.nan
                ax.plot(x, y_clean, color=eq["color"], linewidth=2.0, label=f"y = {eq['expr']}")
                plotted_any = True
            except Exception:
                pass

        ax.set_xlim(x_min, x_max)
        ax.set_ylim(-8.0, 8.0)

        ax.tick_params(colors="#334155", labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#cbd5e1")

        if plotted_any:
            leg = ax.legend(facecolor="#ffffff", edgecolor="#e2e8f0", fontsize=8)
            for text in leg.get_texts():
                text.set_color("#0f172a")

        self.figure.tight_layout()

    def _render_3d_plot(self):
        ax = self.figure.add_subplot(111, projection="3d")
        ax.set_facecolor("#ffffff")
        self.figure.patch.set_facecolor("#ffffff")

        x = np.linspace(-4, 4, 75)
        y = np.linspace(-4, 4, 75)
        X, Y = np.meshgrid(x, y)

        Z = eval_3d_surface(self.expr_3d, X, Y, a=self.slider_a_val)
        Z = np.clip(Z, -20, 20)

        surf = ax.plot_surface(
            X, Y, Z,
            cmap="viridis",
            edgecolor="none",
            alpha=0.92,
            antialiased=True
        )

        try:
            ax.contour(X, Y, Z, zdir="z", offset=np.nanmin(Z) - 1.0, cmap="viridis", alpha=0.3)
        except Exception:
            pass

        ax.xaxis.pane.fill = False
        ax.yaxis.pane.fill = False
        ax.zaxis.pane.fill = False
        ax.xaxis.pane.set_edgecolor("#e2e8f0")
        ax.yaxis.pane.set_edgecolor("#e2e8f0")
        ax.zaxis.pane.set_edgecolor("#e2e8f0")

        ax.tick_params(colors="#475569", labelsize=7)
        ax.set_title(f"z = {self.expr_3d}", color="#0f172a", fontsize=9, pad=8)

        self.figure.tight_layout()

    def _render_complex_2d(self):
        ax = self.figure.add_subplot(111)
        ax.set_facecolor("#ffffff")
        self.figure.patch.set_facecolor("#ffffff")

        res = 240
        x = np.linspace(-3.5, 3.5, res)
        y = np.linspace(-3.5, 3.5, res)
        X, Y = np.meshgrid(x, y)
        Z = X + 1j * Y

        W = eval_complex_function(self.expr_complex, Z, a=self.slider_a_val)

        H = (np.angle(W) + np.pi) / (2.0 * np.pi)
        S = np.ones_like(H) * 0.85
        mod = np.abs(W)
        V = 0.85 + 0.15 * np.sin(2.0 * np.pi * np.log(mod + 1e-9))
        V = np.clip(V, 0.0, 1.0)

        HSV = np.dstack((H, S, V))
        RGB = mcolors.hsv_to_rgb(HSV)

        ax.imshow(RGB, extent=[-3.5, 3.5, -3.5, 3.5], origin="lower")
        ax.axhline(0, color="#ffffff", linewidth=0.8, alpha=0.6)
        ax.axvline(0, color="#ffffff", linewidth=0.8, alpha=0.6)

        ax.set_xlabel("Re(z)", color="#475569", fontsize=8)
        ax.set_ylabel("Im(z)", color="#475569", fontsize=8)
        ax.tick_params(colors="#475569", labelsize=7)
        ax.set_title(f"Complex Phase Portrait: f(z) = {self.expr_complex}", color="#0f172a", fontsize=9, pad=8)

        for spine in ax.spines.values():
            spine.set_color("#cbd5e1")

        self.figure.tight_layout()

    def _render_complex_3d(self):
        ax = self.figure.add_subplot(111, projection="3d")
        ax.set_facecolor("#ffffff")
        self.figure.patch.set_facecolor("#ffffff")

        res = 80
        x = np.linspace(-2.5, 2.5, res)
        y = np.linspace(-2.5, 2.5, res)
        X, Y = np.meshgrid(x, y)
        Z_grid = X + 1j * Y

        W = eval_complex_function(self.expr_complex, Z_grid, a=self.slider_a_val)
        Height = np.clip(np.abs(W), 0, 12)
        Phase = np.angle(W)

        norm_phase = (Phase + np.pi) / (2.0 * np.pi)
        colors = plt.cm.twilight(norm_phase)

        surf = ax.plot_surface(
            X, Y, Height,
            facecolors=colors,
            shade=False,
            alpha=0.92,
            antialiased=True
        )

        ax.xaxis.pane.fill = False
        ax.yaxis.pane.fill = False
        ax.zaxis.pane.fill = False
        ax.xaxis.pane.set_edgecolor("#e2e8f0")
        ax.yaxis.pane.set_edgecolor("#e2e8f0")
        ax.zaxis.pane.set_edgecolor("#e2e8f0")

        ax.tick_params(colors="#475569", labelsize=7)
        ax.set_title(f"Riemann Surface: |f(z)| = |{self.expr_complex}|", color="#0f172a", fontsize=9, pad=8)

        self.figure.tight_layout()

    def _on_canvas_mouse_move(self, event):
        if event.inaxes and event.xdata is not None and event.ydata is not None:
            self.status_bar.setText(f"Coordinates: X = {event.xdata:+.3f}, Y = {event.ydata:+.3f}")

    def _export_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Graph as PNG", "kestrel_graph.png", "PNG Images (*.png)")
        if path:
            try:
                self.figure.savefig(path, dpi=200, facecolor=self.figure.get_facecolor(), edgecolor="none")
                QMessageBox.information(self, "Saved", f"Graph exported successfully to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save graph: {e}")

    def _insert_to_canvas(self):
        payload = {
            "type": "graph",
            "mode": self.current_mode,
            "equations_2d": self.equations_2d,
            "expr_3d": self.expr_3d,
            "expr_complex": self.expr_complex,
            "param_a": self.slider_a_val
        }
        self.insert_to_canvas_requested.emit(payload)
