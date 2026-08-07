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
