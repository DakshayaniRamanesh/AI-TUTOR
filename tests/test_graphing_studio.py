"""
Automated Tests for Desmos-Style Graph Studio & In-Canvas Interactive Graphing Widget
Covers:
1. 2D, 3D, and Complex mathematical evaluation
2. GraphStudioView mode switching and rendering
3. In-canvas InteractiveGraphingWidget parameter updates
4. CanvasScene serialization and collaborative round-trip sync
5. Natural language preset detection
"""

import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication

from app.ui.views.graph_studio_view import (
    GraphStudioView,
    eval_2d_function,
    eval_3d_surface,
    eval_complex_function,
    sanitize_math_expression
)
from app.ui.items.interactive_widgets.graph_widget import InteractiveGraphingWidget
from app.ui.items.interactive_widgets.dynamic_builder import (
    match_instant_interactive_preset,
    create_instant_widget_item,
    is_interactive_build_request
)
from app.ui.items.interactive_widgets.base_interactive_widget import InteractiveCanvasItem
from app.ui.canvas_scene import CanvasScene


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_math_expression_sanitization():
    assert sanitize_math_expression("x^2 + 2x + 1") == "x**2 + 2*x + 1"
    assert sanitize_math_expression("sin(2x)cos(3x)") == "sin(2*x)*cos(3*x)"
    assert sanitize_math_expression("3(x + 1)") == "3*(x + 1)"


def test_2d_function_evaluation():
    x = np.linspace(-5, 5, 50)
    y1 = eval_2d_function("sin(x)", x)
    assert len(y1) == 50
    assert np.allclose(y1, np.sin(x))

    y2 = eval_2d_function("a*x^2 + b", x, a=2.0, b=3.0)
    assert np.allclose(y2, 2.0 * x**2 + 3.0)


def test_3d_surface_evaluation():
    x = np.linspace(-2, 2, 20)
    y = np.linspace(-2, 2, 20)
    X, Y = np.meshgrid(x, y)
    Z = eval_3d_surface("x^2 + y^2", X, Y)
    assert Z.shape == (20, 20)
    assert np.allclose(Z, X**2 + Y**2)


def test_complex_function_evaluation():
    res = 15
    x = np.linspace(-2, 2, res)
    y = np.linspace(-2, 2, res)
    X, Y = np.meshgrid(x, y)
    Z = X + 1j * Y
    W = eval_complex_function("z^3 - 1", Z)
    assert W.shape == (res, res)
    assert np.allclose(W, Z**3 - 1)


def test_graph_studio_view_modes(qapp):
    studio = GraphStudioView()
    assert studio.current_mode == "2d"

    # Test 3D mode
    studio._set_mode("3d")
    assert studio.current_mode == "3d"
    assert studio.figure.axes is not None

    # Test Complex 2D (Domain Coloring)
    studio._set_mode("complex_2d")
    assert studio.current_mode == "complex_2d"

    # Test Complex 3D (Riemann surface)
    studio._set_mode("complex_3d")
    assert studio.current_mode == "complex_3d"

    # Test parameter slider update
    studio.slider_a.setValue(250)
    assert studio.slider_a_val == 2.50


def test_interactive_graphing_widget_canvas_card(qapp):
    w2d = InteractiveGraphingWidget(mode="2d")
    assert w2d.mode == "2d"
    assert w2d.figure.axes is not None

    w3d = InteractiveGraphingWidget(mode="3d")
    assert w3d.mode == "3d"

    w_comp = InteractiveGraphingWidget(mode="complex")
    assert w_comp.mode == "complex"

    # Test serialization
    data = w2d.to_dict()
    assert "mode" in data
    assert "expr_2d" in data
    assert "slider_a" in data

    w_restored = InteractiveGraphingWidget.from_dict(data)
    assert w_restored.mode == "2d"


def test_graph_preset_detection_and_canvas_roundtrip(qapp):
    queries = [
        "desmos",
        "open graphing calculator",
        "plot 3d surface",
        "complex graph",
        "2d graph",
    ]
    for q in queries:
        preset = match_instant_interactive_preset(q)
        assert preset is not None
        assert preset[0] == "graph_widget"
        assert is_interactive_build_request(q) is True

    # Test instantiation & scene restoration
    item = create_instant_widget_item("graph_widget", title="Graphing Studio", prompt="plot 3d surface")
    assert item is not None
    assert isinstance(item.content_widget, InteractiveGraphingWidget)
    assert item.content_widget.mode == "3d"

    scene = CanvasScene()
    scene.addItem(item)
    dict_data = item.to_dict()

    restored = scene.create_item_from_dict(dict_data)
    assert restored is not None
    assert isinstance(restored, InteractiveCanvasItem)
    assert isinstance(restored.content_widget, InteractiveGraphingWidget)
