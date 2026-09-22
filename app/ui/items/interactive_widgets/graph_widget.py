"""
In-Canvas Interactive Graphing Widget (2D Curves, 3D Surfaces, Complex Analysis)
Clean, professional light theme matching Kestrel design system and academic workstations.
No emojis or neon styling — uses crisp typography, Remix icons, and light high-contrast palette.
"""

import re
import numpy as np
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSlider, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
import qtawesome as qta

from ...kestrel_theme import MONO_FONT


def _sanitize_math(expr_str: str) -> str:
    s = expr_str.strip().replace("^", "**")
    s = re.sub(r"(\d)([a-zA-Z\(])", r"\1*\2", s)
    s = re.sub(r"\)([a-zA-Z0-9\(])", r")*\1", s)
    return s


class InteractiveGraphingWidget(QWidget):
    """
    Compact Desmos-style interactive widget designed to live as a draggable,
    minimizable card directly on the whiteboard canvas.
    Light theme, academic aesthetic, Remix icons.
    """

    def __init__(self, mode: str = "2d", initial_expr: str = "", parent=None):
        super().__init__(parent)
        self.setFixedSize(360, 390)
        self.setStyleSheet("background-color: #ffffff;")
        self.mode = mode if mode in ("2d", "3d", "complex") else "2d"
        self.expr_2d = initial_expr if (initial_expr and self.mode == "2d") else "sin(a*x) + 0.3*sin(3*x)"
        self.expr_3d = initial_expr if (initial_expr and self.mode == "3d") else "sin(sqrt(x^2 + y^2) * a) / (sqrt(x^2 + y^2) + 0.05)"
        self.expr_complex = initial_expr if (initial_expr and self.mode == "complex") else "z^3 - a"
        self.slider_a_val = 1.0

        self._init_ui()
        self.update_plot()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # 1. Mode Pill Row (No emojis, clean Remix icons)
        row_modes = QHBoxLayout()
        row_modes.setSpacing(4)
        self.btn_2d = QPushButton("2D Curve", self)
        self.btn_3d = QPushButton("3D Surface", self)
        self.btn_comp = QPushButton("Complex", self)

        for btn in (self.btn_2d, self.btn_3d, self.btn_comp):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(24)

        self.btn_2d.clicked.connect(lambda: self._switch_mode("2d"))
        self.btn_3d.clicked.connect(lambda: self._switch_mode("3d"))
        self.btn_comp.clicked.connect(lambda: self._switch_mode("complex"))

        row_modes.addWidget(self.btn_2d)
        row_modes.addWidget(self.btn_3d)
        row_modes.addWidget(self.btn_comp)
        layout.addLayout(row_modes)

        # 2. Formula Input + Presets (Light Theme)
        inp_row = QHBoxLayout()
        self.inp_formula = QLineEdit(self)
        self.inp_formula.setStyleSheet(f"""
            QLineEdit {{
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px 6px;
                font-family: {MONO_FONT};
                font-size: 11px;
                font-weight: 600;
            }}
            QLineEdit:focus {{
                border: 1px solid #2563eb;
            }}
        """)
        self.inp_formula.returnPressed.connect(self._on_formula_submitted)
        inp_row.addWidget(self.inp_formula, stretch=1)

        self.combo_presets = QComboBox(self)
        self.combo_presets.setFixedWidth(85)
        self.combo_presets.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                font-size: 10px;
                padding: 2px 6px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #0f172a;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }
        """)
        self.combo_presets.currentIndexChanged.connect(self._on_preset_picked)
        inp_row.addWidget(self.combo_presets)
        layout.addLayout(inp_row)

        # 3. Parameter Slider `a` (Light Theme)
        slider_row = QHBoxLayout()
        self.lbl_slider = QLabel("a = 1.00", self)
        self.lbl_slider.setStyleSheet(f"font-size: 10px; color: #0f172a; font-family: {MONO_FONT}; font-weight: 600;")
        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(-400, 400)
        self.slider.setValue(100)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #e2e8f0;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #2563eb;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 2px solid #2563eb;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
        """)
        self.slider.valueChanged.connect(self._on_slider_changed)
        slider_row.addWidget(self.lbl_slider)
        slider_row.addWidget(self.slider)
        layout.addLayout(slider_row)

        # 4. Embedded Matplotlib Figure Canvas (Pure White Academic Light)
        self.figure = Figure(figsize=(3.4, 2.7), dpi=90, facecolor="#ffffff")
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.canvas)

        self._refresh_presets()
        self._update_button_styles()

    def _switch_mode(self, mode: str):
        self.mode = mode
        self._update_button_styles()
        self._refresh_presets()
        self.update_plot()

    def _update_button_styles(self):
        active_style = """
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                font-size: 10px;
                font-weight: 600;
                border: 1px solid #2563eb;
                border-radius: 4px;
                padding: 2px 6px;
            }
        """
        idle_style = """
            QPushButton {
                background-color: #f8fafc;
                color: #475569;
                font-size: 10px;
                font-weight: 500;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 2px 6px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
                color: #0f172a;
            }
        """

        self.btn_2d.setStyleSheet(active_style if self.mode == "2d" else idle_style)
        self.btn_3d.setStyleSheet(active_style if self.mode == "3d" else idle_style)
        self.btn_comp.setStyleSheet(active_style if self.mode == "complex" else idle_style)

        # Remix icons instead of emojis
        col_2d = "#ffffff" if self.mode == "2d" else "#475569"
        col_3d = "#ffffff" if self.mode == "3d" else "#475569"
        col_comp = "#ffffff" if self.mode == "complex" else "#475569"

        self.btn_2d.setIcon(qta.icon("ri.line-chart-line", color=col_2d))
        self.btn_3d.setIcon(qta.icon("ri.shape-line", color=col_3d))
        self.btn_comp.setIcon(qta.icon("ri.contrast-drop-line", color=col_comp))

        if self.mode == "2d":
            self.inp_formula.setText(self.expr_2d)
        elif self.mode == "3d":
            self.inp_formula.setText(self.expr_3d)
        else:
            self.inp_formula.setText(self.expr_complex)

    def _refresh_presets(self):
        self.combo_presets.blockSignals(True)
        self.combo_presets.clear()
        self.combo_presets.addItem("Preset…", "")

        if self.mode == "2d":
            items = [
                ("Sine wave", "sin(a*x) + 0.3*sin(3*x)"),
                ("Damped", "exp(-0.2*x) * cos(a*x)"),
                ("Cubic", "x^3 - 3*x + a"),
                ("Bell", "exp(-x^2 / (2*a^2))"),
            ]
        elif self.mode == "3d":
            items = [
                ("Sombrero", "sin(sqrt(x^2 + y^2) * a) / (sqrt(x^2 + y^2) + 0.05)"),
                ("Saddle", "a * (x^2 - y^2)"),
                ("Paraboloid", "a * (x^2 + y^2) / 2"),
                ("Egg crate", "cos(a*x) * sin(a*y)"),
            ]
        else:
            items = [
                ("z^3 - 1", "z^3 - a"),
                ("exp(z)", "exp(a * z)"),
                ("1 / z", "1 / (z + 1e-9)"),
                ("sin(z)", "sin(a * z)"),
            ]

        for label, val in items:
            self.combo_presets.addItem(label, val)

        self.combo_presets.blockSignals(False)

    def _on_preset_picked(self, idx: int):
        val = self.combo_presets.currentData()
        if val:
            self.inp_formula.setText(val)
            self._on_formula_submitted()

    def _on_formula_submitted(self):
        txt = self.inp_formula.text().strip()
        if self.mode == "2d":
            self.expr_2d = txt
        elif self.mode == "3d":
            self.expr_3d = txt
        else:
            self.expr_complex = txt
        self.update_plot()

    def _on_slider_changed(self, val: int):
        self.slider_a_val = val / 100.0
        self.lbl_slider.setText(f"a = {self.slider_a_val:.2f}")
        self.update_plot()

    def update_plot(self):
        self.figure.clear()

        try:
            if self.mode == "2d":
                ax = self.figure.add_subplot(111)
                ax.set_facecolor("#ffffff")
                self.figure.patch.set_facecolor("#ffffff")

                x = np.linspace(-8, 8, 400)
                scope = {
                    "x": x, "a": self.slider_a_val,
                    "sin": np.sin, "cos": np.cos, "tan": np.tan,
                    "exp": np.exp, "log": np.log, "sqrt": np.sqrt,
                    "abs": np.abs, "pi": np.pi, "e": np.e
                }
                prep = _sanitize_math(self.expr_2d)
                y = eval(prep, {"__builtins__": {}}, scope)
                if isinstance(y, (int, float)):
                    y = np.full_like(x, float(y))

                y_clean = np.copy(y)
                y_clean[np.abs(y_clean) > 40] = np.nan

                ax.axhline(0, color="#94a3b8", linewidth=0.8)
                ax.axvline(0, color="#94a3b8", linewidth=0.8)
                ax.grid(True, color="#e2e8f0", linestyle="--", linewidth=0.6, alpha=0.8)
                ax.plot(x, y_clean, color="#2563eb", linewidth=2.0)
                ax.set_xlim(-8, 8)
                ax.set_ylim(-5, 5)
                ax.tick_params(colors="#64748b", labelsize=7)
                for spine in ax.spines.values():
                    spine.set_color("#cbd5e1")

            elif self.mode == "3d":
                ax = self.figure.add_subplot(111, projection="3d")
                ax.set_facecolor("#ffffff")
                self.figure.patch.set_facecolor("#ffffff")

                x = np.linspace(-3, 3, 40)
                y = np.linspace(-3, 3, 40)
                X, Y = np.meshgrid(x, y)
                scope = {
                    "x": X, "y": Y, "a": self.slider_a_val,
                    "sin": np.sin, "cos": np.cos, "tan": np.tan,
                    "exp": np.exp, "log": np.log, "sqrt": np.sqrt,
                    "abs": np.abs, "pi": np.pi, "e": np.e
                }
                prep = _sanitize_math(self.expr_3d)
                Z = eval(prep, {"__builtins__": {}}, scope)
                if isinstance(Z, (int, float)):
                    Z = np.full_like(X, float(Z))
                Z = np.clip(Z, -10, 10)

                ax.plot_surface(X, Y, Z, cmap="viridis", edgecolor="none", alpha=0.9)
                ax.xaxis.pane.fill = False
                ax.yaxis.pane.fill = False
                ax.zaxis.pane.fill = False
                ax.xaxis.pane.set_edgecolor("#e2e8f0")
                ax.yaxis.pane.set_edgecolor("#e2e8f0")
                ax.zaxis.pane.set_edgecolor("#e2e8f0")
                ax.tick_params(colors="#64748b", labelsize=6)
                ax.grid(color="#e2e8f0", linestyle=":")

            else: # complex
                ax = self.figure.add_subplot(111)
                ax.set_facecolor("#ffffff")
                self.figure.patch.set_facecolor("#ffffff")

                res = 120
                x = np.linspace(-2.5, 2.5, res)
                y = np.linspace(-2.5, 2.5, res)
                X, Y = np.meshgrid(x, y)
                Z = X + 1j * Y

                scope = {
                    "z": Z, "a": self.slider_a_val,
                    "sin": np.sin, "cos": np.cos, "tan": np.tan,
                    "exp": np.exp, "log": np.log, "sqrt": np.sqrt,
                    "abs": np.abs, "pi": np.pi, "e": np.e
                }
                prep = _sanitize_math(self.expr_complex)
                W = eval(prep, {"__builtins__": {}}, scope)

                H = (np.angle(W) + np.pi) / (2.0 * np.pi)
                S = np.ones_like(H) * 0.85
                mod = np.abs(W)
                V = 0.80 + 0.20 * np.sin(2.0 * np.pi * np.log(mod + 1e-9))
                V = np.clip(V, 0.0, 1.0)
                HSV = np.dstack((H, S, V))
                RGB = mcolors.hsv_to_rgb(HSV)

                ax.imshow(RGB, extent=[-2.5, 2.5, -2.5, 2.5], origin="lower")
                ax.axhline(0, color="#ffffff", linewidth=0.5, alpha=0.6)
                ax.axvline(0, color="#ffffff", linewidth=0.5, alpha=0.6)
                ax.tick_params(colors="#64748b", labelsize=6)
                for spine in ax.spines.values():
                    spine.set_color("#cbd5e1")

            self.figure.tight_layout(pad=1.0)

        except Exception as err:
            ax = self.figure.add_subplot(111)
            ax.set_facecolor("#ffffff")
            self.figure.patch.set_facecolor("#ffffff")
            ax.text(0.5, 0.5, f"Syntax Error:\n{err}", color="#dc2626", fontsize=8, ha="center", va="center")

        self.canvas.draw_idle()

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "expr_2d": self.expr_2d,
            "expr_3d": self.expr_3d,
            "expr_complex": self.expr_complex,
            "slider_a": self.slider_a_val
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InteractiveGraphingWidget":
        mode = data.get("mode", "2d")
        expr = data.get(f"expr_{mode}", "")
        w = cls(mode=mode, initial_expr=expr)
        w.slider_a_val = data.get("slider_a", 1.0)
        w.slider.setValue(int(w.slider_a_val * 100))
        return w
