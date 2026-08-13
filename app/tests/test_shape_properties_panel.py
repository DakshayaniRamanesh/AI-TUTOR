"""
Unit Tests for ShapePropertiesPanel UI Proxy, Parent Hierarchy, and Popup Toggling.
"""

import pytest
from PyQt6.QtWidgets import QApplication, QGraphicsScene, QGraphicsProxyWidget
from PyQt6.QtGui import QPen, QColor
from PyQt6.QtCore import Qt, QPointF

# Ensure single QApplication instance for Qt widget tests
app = QApplication.instance() or QApplication([])

from app.ui.items.smart_shape_item import SmartShapeItem
from app.ui.shape_properties_panel import ShapePropertiesPanel, ShapePropertiesWidget
from app.ui.canvas_scene import CanvasScene


def test_shape_properties_panel_parenting():
    """Verifies that ShapePropertiesPanel and its popup_proxy remain parented to SmartShapeItem."""
    scene = CanvasScene()
    shape = SmartShapeItem(
        shape_type="circle",
        fit_data={"radius": 40.0, "center": (0.0, 0.0)}
    )
    scene.addItem(shape)

    scene.activate_shape(shape)

    panel = scene._active_properties_panel
    assert panel is not None
    assert panel.parentItem() == shape, "ShapePropertiesPanel must remain parented to shape"
    assert panel.popup_proxy.parentItem() == shape, "popup_proxy must remain parented to shape"


def test_shape_properties_panel_toggle_popup():
    """Verifies that clicking the 3-dot button toggles popup_proxy visibility cleanly."""
    scene = CanvasScene()
    shape = SmartShapeItem(
        shape_type="rectangle",
        fit_data={"bbox": (0, 0, 100, 60)}
    )
    scene.addItem(shape)
    scene.activate_shape(shape)

    panel = scene._active_properties_panel
    assert not panel.popup_proxy.isVisible()

    # Simulate 3-dot button click
    panel.btn_more.click()
    assert panel.popup_proxy.isVisible(), "Popup proxy should be visible after 3-dot click"

    # Verify size is non-zero
    rect = panel.popup_proxy.geometry()
    assert rect.width() > 0 and rect.height() > 0, "Popup proxy size must be positive"

    # Simulate second click (close)
    panel.btn_more.click()
    assert not panel.popup_proxy.isVisible(), "Popup proxy should hide after second click"


def test_triangle_num_sides_integer_field_and_path_closure():
    """
    Verifies Bug 1 & Bug 2 fixes:
    1. Triangle path is properly closed (elementCount == 4 for 3 vertices + closeSubpath).
    2. 'num_sides' property widget uses 0 decimals, no unit conversion, displays 3, and updates polygon on increment.
    """
    scene = CanvasScene()
    shape = SmartShapeItem(
        shape_type="triangle",
        fit_data={"bbox": (0, 0, 100, 100)}
    )
    scene.addItem(shape)
    scene.activate_shape(shape)

    # 1. Verify path is closed
    path = shape.path()
    assert path.elementCount() == 4  # moveTo + 2 lineTo + closeSubpath/lineTo

    panel = scene._active_properties_panel
    popup_widget = panel._popup_card

    # 2. Verify num_sides field control
    assert "num_sides" in popup_widget.field_controls
    qc = popup_widget.field_controls["num_sides"]
    assert qc.spin.decimals() == 0, "num_sides field must use 0 decimals"
    assert qc.spin.value() == 3.0, "num_sides field must display 3 for triangle"
    assert not qc.unit_convert, "num_sides field must not apply spatial unit conversion"

    # 3. Increment sides to 5 (pentagon)
    qc._increment()
    assert shape.dimensions_px["num_sides"] == 4.0
    qc._increment()
    assert shape.dimensions_px["num_sides"] == 5.0
    assert shape.path().elementCount() == 6  # 5 sides closed polygon
