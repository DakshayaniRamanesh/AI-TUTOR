"""
Constants Library Full-Page View for Kestrel AI Notebook
Matches Reference Screenshot 5:
- Breadcrumb navigation: Reference › Constants Library
- Search input with live multi-field filtering & A-Z sorting
- Category sidebar (Mathematics 12, Physics Mechanics 9, Electromagnetism 7, Thermodynamics 5, Quantum 6, Chemistry Physical 8, Atomic 6)
- 5-Column responsive card grid
- JetBrains Mono / monospace font for symbols, values, and headings
- One-click copy with clipboard integration and visual feedback ('COPIED! ✓')
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QScrollArea, QGridLayout, QFrame, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFont
import qtawesome as qta

from ..theme_manager import ThemeManager

MONO_JETBRAINS = '"JetBrains Mono", "Space Mono", ui-monospace, "Consolas", monospace'


# ── Comprehensive Constants Catalog Matching Reference Screenshot 5 ───────────
CONSTANTS_CATALOG = [
    # ── Mathematics ────────────────────────────────────────────────────────────
    {
        "category": "Mathematics",
        "symbol": "π",
        "name": "Pi",
        "value": "3.14159 26535 89793",
        "unit": ""
    },
    {
        "category": "Mathematics",
        "symbol": "e",
        "name": "Euler's number",
        "value": "2.71828 18284 59045",
        "unit": ""
    },
    {
        "category": "Mathematics",
        "symbol": "φ",
        "name": "Golden ratio",
        "value": "1.61803 39887 49894",
        "unit": ""
    },
    {
        "category": "Mathematics",
        "symbol": "√2",
        "name": "Square root of 2",
        "value": "1.41421 35623 73095",
        "unit": ""
    },
    {
        "category": "Mathematics",
        "symbol": "√3",
        "name": "Square root of 3",
        "value": "1.73205 08075 68877",
        "unit": ""
    },
    {
        "category": "Mathematics",
        "symbol": "ln 2",
        "name": "Natural log of 2",
        "value": "0.69314 71805 59945",
        "unit": ""
    },
    {
        "category": "Mathematics",
        "symbol": "γ",
        "name": "Euler-Mascheroni const.",
        "value": "0.57721 56649 01532",
        "unit": ""
    },
    {
        "category": "Mathematics",
        "symbol": "∞",
        "name": "Infinity (∞ / concept)",
        "value": "unbounded",
        "unit": ""
    },
    {
        "category": "Mathematics",
        "symbol": "i",
        "name": "Imaginary unit",
        "value": "i² = -1",
        "unit": ""
    },
    {
        "category": "Mathematics",
        "symbol": "δ",
        "name": "Kronecker delta (δᵢⱼ)",
        "value": "1 if i = j, else 0",
        "unit": ""
    },
    {
        "category": "Mathematics",
        "symbol": "Γ(½)",
        "name": "Gamma of ½",
        "value": "√π ≈ 1.77245",
        "unit": ""
    },
    {
        "category": "Mathematics",
        "symbol": "ζ(2)",
        "name": "Basel problem (ζ(2))",
        "value": "π²/6 ≈ 1.64493",
        "unit": ""
    },

    # ── Physics - Mechanics ────────────────────────────────────────────────────
    {
        "category": "Physics - Mechanics",
        "symbol": "c",
        "name": "Speed of light in vacuum",
        "value": "299,792,458",
        "unit": "m·s⁻¹"
    },
    {
        "category": "Physics - Mechanics",
        "symbol": "G",
        "name": "Newtonian gravitational const.",
        "value": "6.67430 × 10⁻¹¹",
        "unit": "m³·kg⁻¹·s⁻²"
    },
    {
        "category": "Physics - Mechanics",
        "symbol": "g",
        "name": "Standard gravity acceleration",
        "value": "9.80665",
        "unit": "m·s⁻²"
    },
    {
        "category": "Physics - Mechanics",
        "symbol": "mₑ",
        "name": "Electron rest mass",
        "value": "9.10938 × 10⁻³¹",
        "unit": "kg"
    },
    {
        "category": "Physics - Mechanics",
        "symbol": "m_p",
        "name": "Proton rest mass",
        "value": "1.67262 × 10⁻²⁷",
        "unit": "kg"
    },
    {
        "category": "Physics - Mechanics",
        "symbol": "m_n",
        "name": "Neutron rest mass",
        "value": "1.67493 × 10⁻²⁷",
        "unit": "kg"
    },
    {
        "category": "Physics - Mechanics",
        "symbol": "u",
        "name": "Atomic mass unit (Dalton)",
        "value": "1.66054 × 10⁻²⁷",
        "unit": "kg"
    },
    {
        "category": "Physics - Mechanics",
        "symbol": "P_0",
        "name": "Standard atmospheric pressure",
        "value": "101,325",
        "unit": "Pa"
    },
    {
        "category": "Physics - Mechanics",
        "symbol": "ρ_w",
        "name": "Density of pure water (4°C)",
        "value": "1,000",
        "unit": "kg·m⁻³"
    },

    # ── Physics - Electromagnetism ─────────────────────────────────────────────
    {
        "category": "Physics - Electromagnetism",
        "symbol": "e",
        "name": "Elementary charge",
        "value": "1.60218 × 10⁻¹⁹",
        "unit": "C"
    },
    {
        "category": "Physics - Electromagnetism",
        "symbol": "ε₀",
        "name": "Permittivity of vacuum",
        "value": "8.85419 × 10⁻¹²",
        "unit": "F·m⁻¹"
    },
    {
        "category": "Physics - Electromagnetism",
        "symbol": "μ₀",
        "name": "Permeability of vacuum",
        "value": "1.25664 × 10⁻⁶",
        "unit": "N·A⁻²"
    },
    {
        "category": "Physics - Electromagnetism",
        "symbol": "k_e",
        "name": "Coulomb's constant",
        "value": "8.98755 × 10⁹",
        "unit": "N·m²·C⁻²"
    },
    {
        "category": "Physics - Electromagnetism",
        "symbol": "Z₀",
        "name": "Characteristic vacuum impedance",
        "value": "376.73031",
        "unit": "Ω"
    },
    {
        "category": "Physics - Electromagnetism",
        "symbol": "Φ₀",
        "name": "Magnetic flux quantum",
        "value": "2.06783 × 10⁻¹⁵",
        "unit": "Wb"
    },
    {
        "category": "Physics - Electromagnetism",
        "symbol": "G₀",
        "name": "Conductance quantum",
        "value": "7.74809 × 10⁻⁵",
        "unit": "S"
    },

    # ── Physics - Thermodynamics ──────────────────────────────────────────────
    {
        "category": "Physics - Thermodynamics",
        "symbol": "k_B",
        "name": "Boltzmann constant",
        "value": "1.38065 × 10⁻²³",
        "unit": "J·K⁻¹"
    },
    {
        "category": "Physics - Thermodynamics",
        "symbol": "R",
        "name": "Molar gas constant",
        "value": "8.31446",
        "unit": "J·mol⁻¹·K⁻¹"
    },
    {
        "category": "Physics - Thermodynamics",
        "symbol": "N_A",
        "name": "Avogadro constant",
        "value": "6.02214 × 10²³",
        "unit": "mol⁻¹"
    },
    {
        "category": "Physics - Thermodynamics",
        "symbol": "σ",
        "name": "Stefan-Boltzmann constant",
        "value": "5.67037 × 10⁻⁸",
        "unit": "W·m⁻²·K⁻⁴"
    },
    {
        "category": "Physics - Thermodynamics",
        "symbol": "b",
        "name": "Wien displacement constant",
        "value": "2.89777 × 10⁻³",
        "unit": "m·K"
    },

    # ── Physics - Modern / Quantum ─────────────────────────────────────────────
    {
        "category": "Physics - Modern / Quantum",
        "symbol": "h",
        "name": "Planck constant",
        "value": "6.62607 × 10⁻³⁴",
        "unit": "J·s"
    },
    {
        "category": "Physics - Modern / Quantum",
        "symbol": "ħ",
        "name": "Reduced Planck constant (h/2π)",
        "value": "1.05457 × 10⁻³⁴",
        "unit": "J·s"
    },
    {
        "category": "Physics - Modern / Quantum",
        "symbol": "R_∞",
        "name": "Rydberg constant",
        "value": "1.09737 × 10⁷",
        "unit": "m⁻¹"
    },
    {
        "category": "Physics - Modern / Quantum",
        "symbol": "a₀",
        "name": "Bohr radius",
        "value": "5.29177 × 10⁻¹¹",
        "unit": "m"
    },
    {
        "category": "Physics - Modern / Quantum",
        "symbol": "μ_B",
        "name": "Bohr magneton",
        "value": "9.27401 × 10⁻²⁴",
        "unit": "J·T⁻¹"
    },
    {
        "category": "Physics - Modern / Quantum",
        "symbol": "α",
        "name": "Fine-structure constant",
        "value": "7.29735 × 10⁻³",
        "unit": "dimensionless"
    },

    # ── Chemistry - Physical ───────────────────────────────────────────────────
    {
        "category": "Chemistry - Physical",
        "symbol": "F",
        "name": "Faraday constant",
        "value": "96,485.33",
        "unit": "C·mol⁻¹"
    },
    {
        "category": "Chemistry - Physical",
        "symbol": "V_m",
        "name": "Molar gas volume (STP 0°C)",
        "value": "22.414",
        "unit": "L·mol⁻¹"
    },
    {
        "category": "Chemistry - Physical",
        "symbol": "V_m,SATP",
        "name": "Molar volume (SATP 25°C)",
        "value": "24.789",
        "unit": "L·mol⁻¹"
    },
    {
        "category": "Chemistry - Physical",
        "symbol": "K_w",
        "name": "Water auto-ionization (25°C)",
        "value": "1.0 × 10⁻¹⁴",
        "unit": "mol²·L⁻²"
    },
    {
        "category": "Chemistry - Physical",
        "symbol": "K_b",
        "name": "Ebullioscopic const. water",
        "value": "0.512",
        "unit": "K·kg·mol⁻¹"
    },
    {
        "category": "Chemistry - Physical",
        "symbol": "K_f",
        "name": "Cryoscopic const. water",
        "value": "1.86",
        "unit": "K·kg·mol⁻¹"
    },
    {
        "category": "Chemistry - Physical",
        "symbol": "pH",
        "name": "Neutral water pH (25°C)",
        "value": "7.00",
        "unit": ""
    },
    {
        "category": "Chemistry - Physical",
        "symbol": "ΔH_vap",
        "name": "Enthalpy of vaporization H2O",
        "value": "40.66",
        "unit": "kJ·mol⁻¹"
    },

    # ── Chemistry - Atomic & Bonding ───────────────────────────────────────────
    {
        "category": "Chemistry - Atomic & Bonding",
        "symbol": "r_cov(C)",
        "name": "Carbon covalent radius (sp³)",
        "value": "77",
        "unit": "pm"
    },
    {
        "category": "Chemistry - Atomic & Bonding",
        "symbol": "r_cov(H)",
        "name": "Hydrogen covalent radius",
        "value": "31",
        "unit": "pm"
    },
    {
        "category": "Chemistry - Atomic & Bonding",
        "symbol": "χ(F)",
        "name": "Fluorine electronegativity",
        "value": "3.98",
        "unit": "Pauling"
    },
    {
        "category": "Chemistry - Atomic & Bonding",
        "symbol": "χ(O)",
        "name": "Oxygen electronegativity",
        "value": "3.44",
        "unit": "Pauling"
    },
    {
        "category": "Chemistry - Atomic & Bonding",
        "symbol": "E_diss(H-H)",
        "name": "H-H Bond dissociation energy",
        "value": "436",
        "unit": "kJ·mol⁻¹"
    },
    {
        "category": "Chemistry - Atomic & Bonding",
        "symbol": "E_diss(C-C)",
        "name": "C-C Single bond dissociation",
        "value": "348",
        "unit": "kJ·mol⁻¹"
    }
]


class ConstantCard(QFrame):
    """
    Individual card rendering math symbol, name, and exact numerical value
    with hover copy affordance in fixed-width JetBrains Mono font.
    """
    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.data = data
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(135)
        self.setObjectName("ConstantCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        # Top row: Large Symbol + Copy Button
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        self.lbl_symbol = QLabel(data["symbol"], self)
        top_row.addWidget(self.lbl_symbol)
        top_row.addStretch()

        self.btn_copy = QPushButton(self)
        self.btn_copy.setIcon(qta.icon("ri.file-copy-line", color="#888888"))
        self.btn_copy.setIconSize(QSize(13, 13))
        self.btn_copy.setFixedSize(24, 24)
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.setToolTip("Click to copy value")
        self.btn_copy.clicked.connect(self._copy_value)
        top_row.addWidget(self.btn_copy)

        layout.addLayout(top_row)

        # Descriptive Name
        self.lbl_name = QLabel(data["name"], self)
        self.lbl_name.setWordWrap(True)
        layout.addWidget(self.lbl_name)

        # Hairline Divider
        self.divider = QFrame(self)
        self.divider.setFrameShape(QFrame.Shape.HLine)
        self.divider.setFixedHeight(1)
        layout.addWidget(self.divider)

        # Exact Numerical Value (+ optional unit)
        val_str = data["value"]
        if data.get("unit"):
            val_str += f" {data['unit']}"
        self.lbl_value = QLabel(val_str, self)
        self.lbl_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.lbl_value)

        self._apply_theme()

    def _apply_theme(self):
        c = ThemeManager.instance().get_colors()
        self.setStyleSheet(f"""
            QFrame#ConstantCard {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border_color']};
                border-radius: 8px;
            }}
            QFrame#ConstantCard:hover {{
                border-color: {c['accent']};
                background-color: {c['panel_card_bg']};
            }}
        """)

        self.lbl_symbol.setStyleSheet(f"""
            font-size: 24px;
            font-weight: 700;
            color: {c['text_primary']};
            background: transparent;
            font-family: {MONO_JETBRAINS};
        """)

        self.lbl_name.setStyleSheet(f"""
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            font-size: 11px;
            color: {c['text_secondary']};
            background: transparent;
        """)

        self.divider.setStyleSheet(f"background-color: {c['border_color']}; border: none;")

        self.lbl_value.setStyleSheet(f"""
            font-family: {MONO_JETBRAINS};
            font-size: 11px;
            font-weight: 700;
            color: {c['text_primary']};
            background: transparent;
            margin-top: 2px;
        """)

        self.btn_copy.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 3px;
                color: {c['text_secondary']};
            }}
            QPushButton:hover {{
                background-color: {c['panel_card_bg']};
                color: {c['text_primary']};
            }}
        """)

    def _copy_value(self):
        clipboard = QApplication.clipboard()
        copy_text = self.data["value"]
        if self.data.get("unit"):
            copy_text += f" {self.data['unit']}"
        clipboard.setText(copy_text)

        self.btn_copy.setIcon(qta.icon("ri.check-line", color="#28a745"))
        self.btn_copy.setToolTip("Copied!")
        QTimer.singleShot(1600, self._restore_copy_btn)

    def _restore_copy_btn(self):
        self.btn_copy.setIcon(qta.icon("ri.file-copy-line", color="#888888"))
        self.btn_copy.setToolTip("Click to copy value")


class ConstantsLibraryView(QWidget):
    """
    Full-page Constants Library matching Reference Screenshot 5.
    """
    go_back = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_category = "Mathematics"
        self._sort_ascending = True
        self._search_query = ""

        self._setup_ui()
        ThemeManager.instance().theme_changed.connect(self._apply_theme)
        self._apply_theme(ThemeManager.instance().current_theme)
        self._refresh_cards()

    def _setup_ui(self):
        layout_outer = QVBoxLayout(self)
        layout_outer.setContentsMargins(32, 20, 32, 20)
        layout_outer.setSpacing(14)

        # ── 1. Top Navigation & Breadcrumbs ──
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        self.lbl_breadcrumb = QLabel("Reference  ›  <b>Constants Library</b>", self)
        top_bar.addWidget(self.lbl_breadcrumb)
        top_bar.addStretch()

        # Search Bar
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search constants...")
        self.search_input.setFixedWidth(220)
        self.search_input.textChanged.connect(self._on_search_changed)
        top_bar.addWidget(self.search_input)

        # Sort Button
        self.btn_sort = QPushButton("Sort: A-Z", self)
        self.btn_sort.setIcon(qta.icon("ri.sort-asc", color="#888888"))
        self.btn_sort.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sort.clicked.connect(self._toggle_sort)
        top_bar.addWidget(self.btn_sort)

        layout_outer.addLayout(top_bar)

        # ── 2. Hero Title Section ──
        hero_box = QVBoxLayout()
        hero_box.setSpacing(2)

        self.lbl_hero_title = QLabel("Constants Library", self)
        hero_box.addWidget(self.lbl_hero_title)

        self.lbl_hero_sub = QLabel("Quick-reference values across Mathematics, Physics, and Chemistry — tap to copy.", self)
        hero_box.addWidget(self.lbl_hero_sub)

        layout_outer.addLayout(hero_box)

        # ── 3. Content Split: Sidebar (Sections) + Main Card Grid ──
        content_row = QHBoxLayout()
        content_row.setSpacing(20)

        # Sidebar Panel (~230px)
        self.sidebar_widget = QWidget(self)
        self.sidebar_widget.setFixedWidth(230)
        self.sidebar_layout = QVBoxLayout(self.sidebar_widget)
        self.sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_layout.setSpacing(3)

        self.lbl_sections_hdr = QLabel("SECTIONS", self.sidebar_widget)
        self.sidebar_layout.addWidget(self.lbl_sections_hdr)
        self.sidebar_layout.addSpacing(4)

        self._category_buttons = {}
        categories = [
            "Mathematics",
            "Physics - Mechanics",
            "Physics - Electromagnetism",
            "Physics - Thermodynamics",
            "Physics - Modern / Quantum",
            "Chemistry - Physical",
            "Chemistry - Atomic & Bonding"
        ]

        for cat in categories:
            count = sum(1 for c in CONSTANTS_CATALOG if c["category"] == cat)
            btn = QPushButton(self.sidebar_widget)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(32)
            btn.clicked.connect(lambda _, c=cat: self._select_category(c))

            b_layout = QHBoxLayout(btn)
            b_layout.setContentsMargins(8, 2, 8, 2)

            lbl_cat = QLabel(cat, btn)
            lbl_cat.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            b_layout.addWidget(lbl_cat)
            b_layout.addStretch()

            lbl_count = QLabel(str(count), btn)
            lbl_count.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            b_layout.addWidget(lbl_count)

            self._category_buttons[cat] = (btn, lbl_cat, lbl_count)
            self.sidebar_layout.addWidget(btn)

        self.sidebar_layout.addStretch()
        content_row.addWidget(self.sidebar_widget)

        # Scrollable Card Grid Area (5 Columns)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(12)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        for col_i in range(5):
            self.grid_layout.setColumnStretch(col_i, 1)

        self.scroll_area.setWidget(self.grid_container)
        content_row.addWidget(self.scroll_area, stretch=1)

        layout_outer.addLayout(content_row)

    def _apply_theme(self, theme_name: str = "light"):
        c = ThemeManager.instance().get_colors()
        self.setStyleSheet(f"background-color: {c['bg_app']};")

        self.lbl_breadcrumb.setStyleSheet(f"""
            font-family: {MONO_JETBRAINS};
            font-size: 11px;
            color: {c['text_secondary']};
            background: transparent;
        """)

        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border_color']};
                border-radius: 4px;
                padding: 5px 8px;
                font-family: {MONO_JETBRAINS};
                font-size: 11px;
                color: {c['text_primary']};
            }}
            QLineEdit:focus {{
                border-color: {c['accent']};
            }}
        """)

        self.btn_sort.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border_color']};
                border-radius: 4px;
                padding: 5px 10px;
                font-family: {MONO_JETBRAINS};
                font-size: 11px;
                font-weight: 600;
                color: {c['text_primary']};
            }}
            QPushButton:hover {{
                border-color: {c['accent']};
            }}
        """)

        self.lbl_hero_title.setStyleSheet(f"""
            font-size: 24px;
            font-weight: 800;
            color: {c['text_primary']};
            background: transparent;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        """)

        self.lbl_hero_sub.setStyleSheet(f"""
            font-size: 12px;
            color: {c['text_secondary']};
            background: transparent;
            font-family: {MONO_JETBRAINS};
        """)

        self.lbl_sections_hdr.setStyleSheet(f"""
            font-family: {MONO_JETBRAINS};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1.5px;
            color: {c['text_secondary']};
            background: transparent;
        """)

        self._update_sidebar_styles()

    def _update_sidebar_styles(self):
        c = ThemeManager.instance().get_colors()
        for cat, (btn, lbl_cat, lbl_count) in self._category_buttons.items():
            is_active = (cat == self._selected_category) and not self._search_query
            if is_active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {c['panel_card_bg']};
                        border: 1px solid {c['border_color']};
                        border-radius: 4px;
                    }}
                """)
                lbl_cat.setStyleSheet(f"font-weight: 700; font-size: 11px; color: {c['text_primary']}; font-family: {MONO_JETBRAINS};")
                lbl_count.setStyleSheet(f"font-weight: 700; font-size: 11px; color: {c['text_primary']}; font-family: {MONO_JETBRAINS};")
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        border: none;
                        border-radius: 4px;
                    }}
                    QPushButton:hover {{
                        background-color: {c['panel_card_bg']};
                    }}
                """)
                lbl_cat.setStyleSheet(f"font-size: 11px; color: {c['text_secondary']}; font-family: {MONO_JETBRAINS};")
                lbl_count.setStyleSheet(f"font-size: 11px; color: {c['text_secondary']}; font-family: {MONO_JETBRAINS};")

    def _select_category(self, cat: str):
        self._selected_category = cat
        self._search_query = ""
        self.search_input.clear()
        self._update_sidebar_styles()
        self._refresh_cards()

    def _on_search_changed(self, text: str):
        self._search_query = text.strip().lower()
        self._update_sidebar_styles()
        self._refresh_cards()

    def _toggle_sort(self):
        self._sort_ascending = not self._sort_ascending
        self.btn_sort.setText("Sort: A-Z" if self._sort_ascending else "Sort: Z-A")
        self._refresh_cards()

    def _refresh_cards(self):
        for i in reversed(range(self.grid_layout.count())):
            w = self.grid_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        items = []
        if self._search_query:
            for item in CONSTANTS_CATALOG:
                target = f"{item['symbol']} {item['name']} {item['value']} {item['category']}".lower()
                if self._search_query in target:
                    items.append(item)
        else:
            items = [c for c in CONSTANTS_CATALOG if c["category"] == self._selected_category]

        items.sort(key=lambda x: x["name"].lower(), reverse=not self._sort_ascending)

        if not items:
            c = ThemeManager.instance().get_colors()
            empty_lbl = QLabel("No constants found matching search criteria.")
            empty_lbl.setStyleSheet(f"font-family: {MONO_JETBRAINS}; color: {c['text_secondary']}; font-size: 12px; margin: 30px;")
            self.grid_layout.addWidget(empty_lbl, 0, 0)
            return

        row, col = 0, 0
        max_cols = 5

        for item in items:
            card = ConstantCard(item)
            self.grid_layout.addWidget(card, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
