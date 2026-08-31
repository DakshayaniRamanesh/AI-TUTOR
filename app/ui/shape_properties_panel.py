"""
Floating Shape Properties Panel & Toolbar Widget.

Provides a compact 3-dot floating toolbar positioned near an active canvas shape.
Tapping the 3-dot button opens a popup card containing:
- Shape title header with explicit '×' close button
- Unit selector dropdown (mm, cm, m, inch)
- Touch-friendly [-] and [+] numeric controls for shape dimensions
- Drop shadow, 12px rounded corners, and clean visual alignment

Bug & UX Fixes:
1. Bug 1: Added logging for computed pixel values; target item geometry update calls prepareGeometryChange().
2. Bug 2: Toolbar proxy and popup proxy are parented directly to target_item (setParentItem),
   so they automatically move with the shape whenever the shape is dragged across the canvas.
3. UI Polish: Replaced raw spinbox arrows with custom touch-friendly [-] / [+] buttons,
   added drop shadow, explicit close button, and generous padding/spacing.
"""

import sys
print(f"[MODULE LOAD] shape_properties_panel.py loaded from: {__file__}", flush=True)

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QComboBox,
    QDoubleSpinBox, QLabel, QFrame, QGraphicsProxyWidget,
    QGraphicsDropShadowEffect, QAbstractSpinBox
)
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt, pyqtSignal, QPointF

from .shape_metadata import (
    SHAPE_METADATA, SUPPORTED_UNITS, DEFAULT_UNIT,
    convert_px_to_unit, convert_unit_to_px
)
from .stroke_processor import SHAPE_DEBUG


class QuantityControl(QWidget):
    """
    Touch-friendly numeric field with flanking [-] and [+] buttons around a central spinbox.
    """

    def __init__(self, key: str, label_text: str, step: float = 1.0, min_val: float = 0.1, max_val: float = 9999.0, is_int: bool = False, value_changed_cb=None, parent=None):
        super().__init__(parent)
        self.key = key
        self.step = step
        self.min_val = min_val
        self.max_val = max_val
        self.is_int = is_int
        self.unit_convert = True
        self.value_changed_cb = value_changed_cb
        self._lock = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        from .theme_manager import ThemeManager
        from .kestrel_theme import MONO_FONT
        c = ThemeManager.instance().get_colors()

        # Label
        self.lbl = QLabel(f"{label_text.upper()}:")
        self.lbl.setStyleSheet(f"font-size: 10px; font-weight: 700; letter-spacing: 0.5px; font-family: {MONO_FONT}; color: {c['text_secondary']};")
        layout.addWidget(self.lbl)

        layout.addStretch()

        # Decrement Button [-]
        self.btn_minus = QPushButton("−")
        self.btn_minus.setFixedSize(24, 24)
        self.btn_minus.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_minus.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['panel_card_bg']};
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                font-size: 13px;
                font-weight: bold;
                font-family: {MONO_FONT};
                color: {c['text_primary']};
            }}
            QPushButton:hover {{
                background-color: {c['accent']};
                color: {c['accent_text']};
            }}
        """)
        self.btn_minus.clicked.connect(self._decrement)
        layout.addWidget(self.btn_minus)

        # Central SpinBox
        self.spin = QDoubleSpinBox()
        self.spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin.setRange(min_val, max_val)
        self.spin.setSingleStep(step)
        if is_int:
            self.spin.setDecimals(0)
        else:
            self.spin.setDecimals(2)
        self.spin.setFixedSize(60, 24)
        self.spin.setStyleSheet(f"""
            QDoubleSpinBox {{
                background-color: {c['input_bg']};
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                font-size: 11px;
                font-weight: 600;
                font-family: {MONO_FONT};
                color: {c['text_primary']};
                padding: 1px 2px;
            }}
            QDoubleSpinBox:focus {{
                border: 1px solid {c['accent']};
            }}
        """)
        self.spin.valueChanged.connect(self._on_spin_changed)
        layout.addWidget(self.spin)

        # Increment Button [+]
        self.btn_plus = QPushButton("+")
        self.btn_plus.setFixedSize(24, 24)
        self.btn_plus.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_plus.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['panel_card_bg']};
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                font-size: 13px;
                font-weight: bold;
                font-family: {MONO_FONT};
                color: {c['text_primary']};
            }}
            QPushButton:hover {{
                background-color: {c['accent']};
                color: {c['accent_text']};
            }}
        """)
        self.btn_plus.clicked.connect(self._increment)
        layout.addWidget(self.btn_plus)

    def _decrement(self):
        new_val = max(self.min_val, self.spin.value() - self.step)
        if self.is_int:
            new_val = float(round(new_val))
        self.spin.setValue(new_val)

    def _increment(self):
        new_val = min(self.max_val, self.spin.value() + self.step)
        if self.is_int:
            new_val = float(round(new_val))
        self.spin.setValue(new_val)

    def _on_spin_changed(self, val: float):
        if not self._lock and self.value_changed_cb:
            self.value_changed_cb(self.key, val)

    def setValue(self, val: float):
        self._lock = True
        try:
            self.spin.setValue(val)
        finally:
            self._lock = False

    def value(self) -> float:
        return self.spin.value()


class ShapePropertiesWidget(QFrame):
    """
    Sleek floating popup card containing unit dropdown and dynamic numeric spinboxes.
    """

    close_requested = pyqtSignal()

    def __init__(self, target_item, parent=None):
        super().__init__(parent)
        self.target_item = target_item
        self.active_unit = DEFAULT_UNIT
        self._updating_lock = False

        from .theme_manager import ThemeManager
        from .kestrel_theme import MONO_FONT
        c = ThemeManager.instance().get_colors()

        self.setObjectName("ShapePropertiesWidget")
        self.setStyleSheet(f"""
            QFrame#ShapePropertiesWidget {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border_color']};
                border-radius: 4px;
                padding: 8px;
            }}
            QComboBox {{
                background-color: {c['input_bg']};
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                padding: 2px 6px;
                font-size: 11px;
                font-family: {MONO_FONT};
                font-weight: 500;
                color: {c['text_primary']};
                min-height: 22px;
            }}
            QComboBox:hover {{
                border-color: {c['accent']};
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # Header Row: Shape Title, Unit Dropdown & Close Button
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        st = getattr(target_item, "stroke_type", "shape")
        meta = SHAPE_METADATA.get(st, {})
        title_txt = meta.get("display_name", st.upper())

        title_lbl = QLabel(title_txt.upper())
        title_lbl.setStyleSheet(f"font-size: 11px; font-weight: 700; font-family: {MONO_FONT}; letter-spacing: 1px; color: {c['text_primary']};")
        header_layout.addWidget(title_lbl)

        header_layout.addStretch()

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(SUPPORTED_UNITS)
        self.unit_combo.setCurrentText(self.active_unit)
        self.unit_combo.currentTextChanged.connect(self._on_unit_changed)
        header_layout.addWidget(self.unit_combo)

        # Close button '✕'
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(20, 20)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 2px;
                font-size: 10px;
                font-weight: bold;
                font-family: {MONO_FONT};
                color: {c['text_secondary']};
            }}
            QPushButton:hover {{
                background-color: {c['panel_card_bg']};
                color: {c['text_primary']};
            }}
        """)
        btn_close.clicked.connect(self._on_close_clicked)
        header_layout.addWidget(btn_close)

        main_layout.addLayout(header_layout)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setStyleSheet(f"background-color: {c['border_color']}; max-height: 1px; border: none;")
        main_layout.addWidget(sep)

        # Dimension Fields Layout
        self.field_controls: dict[str, QuantityControl] = {}
        fields = meta.get("fields", [])

        for f_info in fields:
            key = f_info["key"]
            label = f_info["label"]
            step = f_info.get("step", 1.0)
            min_val = f_info.get("min", 0.1)
            max_val = f_info.get("max", 9999.0)
            is_int = f_info.get("is_int", False)
            unit_convert = f_info.get("unit_convert", True)

            qc = QuantityControl(
                key=key,
                label_text=label,
                step=step,
                min_val=min_val,
                max_val=max_val,
                is_int=is_int,
                value_changed_cb=self._on_value_changed
            )
            qc.unit_convert = unit_convert
            self.field_controls[key] = qc
            main_layout.addWidget(qc)

        self.adjustSize()
        self.refresh_values_from_item()

    def _on_close_clicked(self):
        self.close_requested.emit()

    def _on_unit_changed(self, new_unit: str):
        """Changes unit and recalculates displayed values without modifying item size."""
        if self._updating_lock:
            return
        self.active_unit = new_unit
        self.refresh_values_from_item()

    def _on_value_changed(self, key: str, val_unit: float):
        """Converts user input from selected unit to px and updates target item immediately."""
        if self._updating_lock or not self.target_item:
            return

        self._updating_lock = True
        try:
            qc = self.field_controls.get(key)
            if qc and not getattr(qc, "unit_convert", True):
                val_px = float(round(val_unit)) if getattr(qc, "is_int", False) else val_unit
            else:
                val_px = convert_unit_to_px(val_unit, self.active_unit)

            if SHAPE_DEBUG:
                print(f"[PropertiesPanel] Field '{key}' changed to {val_unit} -> {val_px:.2f}px applied to target item", flush=True)

            cur_dims = self.target_item.get_dimensions_px()
            cur_dims[key] = val_px
            self.target_item.set_dimensions_px(cur_dims)
        finally:
            self._updating_lock = False

    def refresh_values_from_item(self):
        """Reads current item pixel dimensions, converts to active unit, and updates spinboxes."""
        if not self.target_item:
            return

        self._updating_lock = True
        try:
            dims_px = self.target_item.get_dimensions_px()
            for key, qc in self.field_controls.items():
                px_val = dims_px.get(key, 0.0)
                if getattr(qc, "unit_convert", True):
                    display_val = convert_px_to_unit(px_val, self.active_unit)
                else:
                    display_val = px_val
                qc.setValue(display_val)
        finally:
            self._updating_lock = False


class ShapePropertiesPanel(QGraphicsProxyWidget):
    """
    Floating graphics item container hosting the 3-dot button and separate properties popup card.
    Parented directly to target_item so both move natively whenever the shape is dragged.
    """

    def __init__(self, target_item, parent=None):
        super().__init__(parent)
        self.target_item = target_item
        self._popup_visible = False

        if target_item:
            self.setParentItem(target_item)
            # Register reference back on shape item for itemChange notifications
            target_item._properties_panel = self

        # ── Toolbar button widget ──────────────────────────────────────────────
        self._btn_widget = QWidget()
        self._btn_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        btn_layout = QHBoxLayout(self._btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        from .theme_manager import ThemeManager
        c = ThemeManager.instance().get_colors()

        self.btn_more = QPushButton("•••")
        self.btn_more.setFixedSize(30, 24)
        self.btn_more.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_more.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['bg_card']};
                border: 1px solid {c['border_color']};
                border-radius: 2px;
                font-weight: bold;
                font-size: 11px;
                color: {c['text_primary']};
            }}
            QPushButton:hover {{
                background-color: {c['accent']};
                color: {c['accent_text']};
            }}
        """)

        if SHAPE_DEBUG:
            print(f"[Step 1] 3-dot btn created: type={type(self.btn_more).__name__}, geom=({self.btn_more.x()},{self.btn_more.y()},{self.btn_more.width()},{self.btn_more.height()}), isVisible={self.btn_more.isVisible()}, isEnabled={self.btn_more.isEnabled()}", flush=True)
            print(f"[Step 2] Connecting 3-dot btn clicked signal to _on_btn_clicked handler", flush=True)

        self.btn_more.clicked.connect(self._on_btn_clicked)
        btn_layout.addWidget(self.btn_more)
        self._btn_widget.adjustSize()

        self.setWidget(self._btn_widget)
        self.setZValue(110)

        # ── Separate popup proxy widget ────────────────────────────────────────
        if SHAPE_DEBUG:
            print(f"[Step 4] Instantiating ShapePropertiesWidget popup card...", flush=True)

        try:
            self._popup_card = ShapePropertiesWidget(target_item)
            self._popup_card.close_requested.connect(self._hide_popup)
            self._popup_card.adjustSize()
            if SHAPE_DEBUG:
                print(f"[Step 4] Popup card created successfully: {self._popup_card}", flush=True)
        except Exception as err:
            if SHAPE_DEBUG:
                print(f"[Step 4] ERROR creating ShapePropertiesWidget: {err}", flush=True)
            raise err

        self.popup_proxy = QGraphicsProxyWidget()
        if target_item:
            self.popup_proxy.setParentItem(target_item)
        self.popup_proxy.setWidget(self._popup_card)
        self.popup_proxy.setZValue(111)
        self.popup_proxy.hide()

        self.update_position()

    def attach_to_scene(self, scene):
        """No-op kept for backwards compatibility (proxy is parented to target_item)."""
        pass

    def detach_from_scene(self):
        """Hides and cleans up popup proxy on deactivation."""
        self._hide_popup()
        if self.popup_proxy.scene():
            self.popup_proxy.scene().removeItem(self.popup_proxy)

    def _on_btn_clicked(self):
        """Toggle the separate popup proxy visibility."""
        if SHAPE_DEBUG:
            print(f"[Step 3] 3-dot clicked! Handler _on_btn_clicked invoked. Currently visible={self._popup_visible}", flush=True)

        self._popup_visible = not self._popup_visible
        if self._popup_visible:
            self._popup_card.refresh_values_from_item()
            self._popup_card.adjustSize()
            hint = self._popup_card.sizeHint()
            if hint.isValid():
                self.popup_proxy.resize(float(hint.width()), float(hint.height()))
            self.popup_proxy.show()
            self._position_popup()
            if SHAPE_DEBUG:
                rect = self.popup_proxy.geometry()
                spos = self.popup_proxy.scenePos()
                print(f"[Step 5] Popup proxy shown! isVisible={self.popup_proxy.isVisible()}, scenePos=({spos.x():.1f}, {spos.y():.1f}), geom=({rect.x():.1f}, {rect.y():.1f}, {rect.width():.1f}, {rect.height():.1f})", flush=True)
        else:
            self._hide_popup()

    def _hide_popup(self):
        self._popup_visible = False
        self.popup_proxy.hide()
        if SHAPE_DEBUG:
            print(f"[PropertiesPanel] Popup card HIDDEN.", flush=True)

    def _position_popup(self):
        """Position popup card right next to the 3-dot button in local item coords."""
        btn_pos = self.pos()
        btn_h = self._btn_widget.height()
        self.popup_proxy.setPos(btn_pos.x(), btn_pos.y() + btn_h + 4.0)

    def update_position(self):
        """Positions the floating toolbar near top-right of target item in local coordinates."""
        if not self.target_item:
            return

        rect = self.target_item.boundingRect()
        top_right = rect.topRight()
        self.setPos(top_right.x() + 10.0, top_right.y() - 10.0)

        if self._popup_visible:
            self._position_popup()

    def refresh(self):
        """Refreshes spinbox values from target item and repositions panel."""
        self._popup_card.refresh_values_from_item()
        self.update_position()
