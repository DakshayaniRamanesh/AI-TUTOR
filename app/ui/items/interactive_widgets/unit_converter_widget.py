"""
Interactive Unit Converter Canvas Widget
Live bidirectional converter for Length, Temperature, and Mass.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QLabel
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from ...theme_manager import ThemeManager
from ...kestrel_theme import MONO_FONT


class UnitConverterWidget(QWidget):
    """
    In-canvas interactive unit converter.
    """

    CATEGORIES = {
        "Length": {
            "Meters (m)": 1.0,
            "Kilometers (km)": 1000.0,
            "Centimeters (cm)": 0.01,
            "Feet (ft)": 0.3048,
            "Inches (in)": 0.0254,
            "Miles (mi)": 1609.34,
        },
        "Mass": {
            "Kilograms (kg)": 1.0,
            "Grams (g)": 0.001,
            "Pounds (lb)": 0.453592,
            "Ounces (oz)": 0.0283495,
        },
        "Temperature": ["Celsius (°C)", "Fahrenheit (°F)", "Kelvin (K)"]
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(260)
        self._init_ui()

    def _init_ui(self):
        c = ThemeManager.instance().get_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(8)

        # Category Selector
        self.combo_cat = QComboBox(self)
        self.combo_cat.addItems(list(self.CATEGORIES.keys()))
        self.combo_cat.currentTextChanged.connect(self._on_cat_changed)
        layout.addWidget(self.combo_cat)

        # Value input
        layout.addWidget(QLabel("From:", self))
        row1 = QHBoxLayout()
        self.txt_val = QLineEdit("1", self)
        self.txt_val.textChanged.connect(self._convert)
        self.combo_from = QComboBox(self)
        self.combo_from.currentTextChanged.connect(self._convert)
        row1.addWidget(self.txt_val, stretch=1)
        row1.addWidget(self.combo_from, stretch=1)
        layout.addLayout(row1)

        # Result display
        layout.addWidget(QLabel("To:", self))
        row2 = QHBoxLayout()
        self.lbl_res = QLabel("1", self)
        self.lbl_res.setStyleSheet(f"font-size: 16px; font-weight: 700; color: #8b5cf6; font-family: {MONO_FONT};")
        self.combo_to = QComboBox(self)
        self.combo_to.currentTextChanged.connect(self._convert)
        row2.addWidget(self.lbl_res, stretch=1)
        row2.addWidget(self.combo_to, stretch=1)
        layout.addLayout(row2)

        self._on_cat_changed(self.combo_cat.currentText())

    def _on_cat_changed(self, cat: str):
        self.combo_from.clear()
        self.combo_to.clear()
        items = self.CATEGORIES[cat]
        unit_names = list(items.keys()) if isinstance(items, dict) else items
        self.combo_from.addItems(unit_names)
        self.combo_to.addItems(unit_names)
        if len(unit_names) > 1:
            self.combo_to.setCurrentIndex(1)
        self._convert()

    def _convert(self):
        cat = self.combo_cat.currentText()
        u_from = self.combo_from.currentText()
        u_to = self.combo_to.currentText()
        try:
            val = float(self.txt_val.text().strip())
        except ValueError:
            self.lbl_res.setText("—")
            return

        if cat == "Temperature":
            res = self._convert_temp(val, u_from, u_to)
        else:
            factors = self.CATEGORIES[cat]
            base = val * factors.get(u_from, 1.0)
            res = base / factors.get(u_to, 1.0)

        self.lbl_res.setText(f"{res:.4g}")

    def _convert_temp(self, val: float, f: str, t: str) -> float:
        # Normalize to Celsius
        if "Fahrenheit" in f:
            c = (val - 32) * 5 / 9
        elif "Kelvin" in f:
            c = val - 273.15
        else:
            c = val

        # From Celsius to target
        if "Fahrenheit" in t:
            return (c * 9 / 5) + 32
        elif "Kelvin" in t:
            return c + 273.15
        return c
