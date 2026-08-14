"""
Comprehensive Unit Tests for Penecho Canvas Integration in AI-TUTOR.
Covers:
1. Unified Drawing Protocol (normalization, extrema solver, smoothing, arrowheads, QGraphicsItem).
2. Mixed Markdown & LaTeX Math Parser (bare & explicit TeX, markdown tokens, rich text rendering, QGraphicsItem).
3. Declarative 2D Animation Engine (object & motion normalizers, keyframe & orbit evaluators, 60fps item).
4. Freehand Lasso Selection System (ray-casting point-in-polygon, bounding box mapping, overlay).
5. Procedural Mathematical Curves (Lemniscate, Rose, Superellipse, Spiral, Deltoid).
6. Lossless Cropped Exporter.
7. CanvasScene round-trip persistence and deserialization.
"""

import math
import sys
import tempfile
import os
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor
from PyQt6.QtCore import QPointF, QRectF


@pytest.fixture(scope="session")
def qt_app():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture
def scene(qt_app):
    from app.ui.canvas_scene import CanvasScene
    s = CanvasScene()
    yield s
    try:
        s.clear()
    except Exception:
        pass


# ==============================================================================
# 1. Unified Drawing Protocol Tests
# ==============================================================================

def test_unified_drawing_normalization():
    from app.ui.penecho_integration.unified_draw import normalize_drawing_command

    valid_cmd = {
        "origin": [100, 200],
        "types": ["rect", "circle", "line", "smooth", "ellipse", "arc"],
        "items": [
            [0, 0, 50, 60],
            [10, 20, 15],
            [0, 0, 100, 100],
            [0, 0, 50, 50, 100, 0],
            [0, 0, 40, 20],
            [0, 0, 30, 30, 0, 180]
        ],
        "width": 4.0,
        "tension": 60.0,
        "color": "#2563eb",
        "closed": [0, 3],
        "fill": [0],
        "arrows": [2]
    }

    norm = normalize_drawing_command(valid_cmd)
    assert norm is not None
    assert norm["origin"] == [100, 200]
    assert len(norm["primitives"]) == 6
    assert norm["width"] == 4.0
    assert norm["color"] == "#2563eb"
    assert norm["primitives"][0]["type"] == "rect"
    assert norm["primitives"][0]["fill"] is True
    assert norm["primitives"][2]["arrow"] is True
    assert "bounds" in norm


def test_unified_drawing_bezier_extrema_and_arrows():
    from app.ui.penecho_integration.unified_draw import _cubic_extrema, _cubic_at, _arrow_geometry

    # Extrema roots of cubic bezier
    roots = _cubic_extrema(0, 100, 100, 0)
    assert len(roots) >= 1
    t = roots[0]
    assert 0 < t < 1
    val = _cubic_at(0, 100, 100, 0, t)
    assert val > 50

    # Arrow geometry
    arrow = _arrow_geometry((100, 100), (90, 100), width=4.0)
    assert len(arrow) == 3
    assert arrow[0] == (100, 100)


def test_penecho_draw_item_serialization(scene):
    from app.ui.penecho_integration.unified_draw import PenechoDrawItem

    cmd = {
        "origin": [50, 50],
        "types": ["rect", "circle"],
        "items": [[0, 0, 80, 40], [100, 50, 20]],
        "width": 3.0,
        "color": "#ef4444"
    }

    item = PenechoDrawItem(cmd)
    item.setPos(150, 250)
    scene.addItem(item)

    d = item.to_dict()
    assert d["type"] == "PenechoDrawItem"
    assert d["x"] == 150
    assert d["y"] == 250

    restored = scene.create_item_from_dict(d)
    assert restored is not None
    assert isinstance(restored, PenechoDrawItem)
    assert restored.boundingRect().width() > 0


# ==============================================================================
# 2. Mixed Text & LaTeX Parser Tests
# ==============================================================================

def test_mixed_text_parser():
    from app.ui.penecho_integration.mixed_text import parse_mixed_text, mixed_tokens_to_html

    text = "Hello **bold world** and `code inline` with math $x^2 + y^2 = r^2$ and bare \\alpha + \\beta."
    tokens = parse_mixed_text(text)

    token_types = [t["type"] for t in tokens]
    assert "styled" in token_types
    assert "code" in token_types
    assert "math" in token_types

    html = mixed_tokens_to_html(tokens)
    assert "bold world" in html
    assert "code inline" in html
    assert "x<sup>2</sup>" in html or "α" in html or "r<sup>2</sup>" in html


def test_penecho_mixed_text_item_serialization(scene):
    from app.ui.penecho_integration.mixed_text import PenechoMixedTextItem

    raw = "Euler identity: **$e^{i\\pi} + 1 = 0$**"
    item = PenechoMixedTextItem(raw_text=raw, font_size=16, width=350.0)
    item.setPos(100, 100)
    scene.addItem(item)

    d = item.to_dict()
    assert d["type"] == "PenechoMixedTextItem"
    assert d["raw_text"] == raw
    assert d["font_size"] == 16

    restored = scene.create_item_from_dict(d)
    assert restored is not None
    assert isinstance(restored, PenechoMixedTextItem)
    assert restored._raw_text == raw


# ==============================================================================
# 3. Declarative Animation Engine Tests
# ==============================================================================

def test_animation_normalization_and_evaluation():
    from app.ui.penecho_integration.animation_engine import (
        normalize_animation_scene, evaluate_scene_state
    )

    scene_data = {
        "title": "Spin & Orbit Test",
        "w": 400,
        "h": 300,
        "durationMs": 4000,
        "objects": [
            {"id": "sun", "type": "circle", "cx": 200, "cy": 150, "r": 30, "fill": "#f59e0b"},
            {"id": "planet", "type": "circle", "cx": 200, "cy": 150, "r": 12, "fill": "#3b82f6"}
        ],
        "motions": [
            {"type": "spin", "target": "sun", "periodMs": 4000, "clockwise": True},
            {"type": "orbit", "target": "planet", "center": [200, 150], "rx": 80, "ry": 40, "periodMs": 2000}
        ]
    }

    norm = normalize_animation_scene(scene_data)
    assert norm is not None
    assert len(norm["objects"]) == 2
    assert len(norm["motions"]) == 2

    # Evaluate at t = 0
    t0 = evaluate_scene_state(norm, 0.0)
    assert "sun" in t0 and "planet" in t0
    assert pytest.approx(t0["sun"]["rotation"], abs=1) == 0.0

    # Evaluate at t = 1000ms (1/4 cycle for sun = 90 deg, 1/2 cycle for planet orbit)
    t1 = evaluate_scene_state(norm, 1000.0)
    assert pytest.approx(t1["sun"]["rotation"], abs=1) == 90.0
    assert abs(t1["planet"]["dx"]) > 0 or abs(t1["planet"]["dy"]) > 0


def test_penecho_animation_item_serialization(scene):
    from app.ui.penecho_integration.animation_engine import PenechoAnimationItem

    scene_data = {
        "title": "Pulse Demo",
        "w": 300,
        "h": 200,
        "durationMs": 3000,
        "objects": [
            {"id": "core", "type": "circle", "cx": 150, "cy": 100, "r": 25, "fill": "#10b981"}
        ],
        "motions": [
            {"type": "pulse", "target": "core", "from": 0.8, "to": 1.2, "periodMs": 1500}
        ]
    }

    item = PenechoAnimationItem(scene_data)
    item.set_speed(1.5)
    item.setPos(50, 80)
    scene.addItem(item)

    d = item.to_dict()
    assert d["type"] == "PenechoAnimationItem"
    assert d["speed"] == 1.5

    restored = scene.create_item_from_dict(d)
    assert restored is not None
    assert isinstance(restored, PenechoAnimationItem)
    assert restored._speed_multiplier == 1.5


# ==============================================================================
# 4. Freehand Lasso Selection Tests
# ==============================================================================

def test_lasso_point_in_polygon_and_bounds():
    from app.ui.penecho_integration.lasso_selection import point_in_polygon, polygon_bounds

    poly = [(0, 0), (100, 0), (100, 100), (0, 100)]
    assert point_in_polygon(50, 50, poly) is True
    assert point_in_polygon(150, 50, poly) is False
    assert point_in_polygon(-10, 50, poly) is False

    bounds = polygon_bounds(poly)
    assert bounds == (0, 0, 100, 100)


def test_lasso_overlay_actions(scene):
    from app.ui.penecho_integration.lasso_selection import PenechoLassoOverlay
    from app.ui.items.sticky_note import StickyNote

    note = StickyNote(text="Selected note")
    note.setPos(50, 50)
    scene.addItem(note)

    poly = [(0, 0), (200, 0), (200, 200), (0, 200)]
    overlay = PenechoLassoOverlay(poly, [note])
    scene.addItem(overlay)

    # Verify overlay is present
    assert overlay in scene.items()

    # Cancel selection restores positions
    overlay.cancel_selection()
    assert overlay not in scene.items()


# ==============================================================================
# 5. Procedural Mathematical Summon Curves Tests
# ==============================================================================

def test_summon_curve_generators():
    from app.ui.penecho_integration.summon_widgets import generate_curve_points

    for ctype in ["lemniscate", "rose", "superellipse", "golden-spiral", "deltoid"]:
        pts = generate_curve_points(ctype, elapsed=1.0, samples=100)
        assert len(pts) > 50
        # All normalized in [-1.5, 1.5]
        for x, y in pts:
            assert -1.5 <= x <= 1.5
            assert -1.5 <= y <= 1.5


def test_penecho_summon_item_serialization(scene):
    from app.ui.penecho_integration.summon_widgets import PenechoSummonItem

    item = PenechoSummonItem(curve_type="rose", size=220.0)
    item.setPos(300, 150)
    scene.addItem(item)

    d = item.to_dict()
    assert d["type"] == "PenechoSummonItem"
    assert d["curve_type"] == "rose"
    assert d["size"] == 220.0

    restored = scene.create_item_from_dict(d)
    assert restored is not None
    assert isinstance(restored, PenechoSummonItem)
    assert restored._curve_type == "rose"


# ==============================================================================
# 6. Lossless Canvas Export Test
# ==============================================================================

def test_export_canvas_to_image(scene):
    from app.ui.penecho_integration.export_utils import export_canvas_to_image
    from app.ui.items.sticky_note import StickyNote

    note = StickyNote(text="Export Test")
    note.setPos(100, 100)
    scene.addItem(note)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        out_path = tf.name

    try:
        success = export_canvas_to_image(scene, out_path, margin_px=20.0, scale_factor=1.5)
        assert success is True
        assert os.path.exists(out_path)
        assert os.path.getsize(out_path) > 100
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)


# ==============================================================================
# 7. CanvasScene Full Round-Trip Persistence Test
# ==============================================================================

def test_canvas_scene_full_roundtrip_with_penecho_items(scene):
    from app.ui.penecho_integration import (
        PenechoDrawItem, PenechoAnimationItem, PenechoMixedTextItem, PenechoSummonItem
    )

    draw_item = PenechoDrawItem({"origin": [0, 0], "types": ["rect"], "items": [[0, 0, 60, 40]], "width": 2.0})
    draw_item.setPos(10, 10)
    scene.addItem(draw_item)

    anim_item = PenechoAnimationItem({"title": "A", "w": 200, "h": 150, "durationMs": 2000, "objects": [{"id": "o", "type": "circle", "cx": 50, "cy": 50, "r": 10}], "motions": []})
    anim_item.setPos(100, 100)
    scene.addItem(anim_item)

    text_item = PenechoMixedTextItem(raw_text="Test **formula** $x=1$", font_size=14)
    text_item.setPos(250, 250)
    scene.addItem(text_item)

    summon_item = PenechoSummonItem(curve_type="golden-spiral", size=200.0)
    summon_item.setPos(400, 400)
    scene.addItem(summon_item)

    dict_list = scene.to_dict_list()
    assert len(dict_list) >= 5 # 1 meta + 4 items

    # Load back into scene
    scene.load_from_dict_list(dict_list)

    types_in_scene = [item.__class__.__name__ for item in scene.items()]
    assert "PenechoDrawItem" in types_in_scene
    assert "PenechoAnimationItem" in types_in_scene
    assert "PenechoMixedTextItem" in types_in_scene
    assert "PenechoSummonItem" in types_in_scene


# ==============================================================================
# 8. PenEcho Unconfirmed Draft Layer & Magic Orb Tests
# ==============================================================================

def test_draft_layer_accept_and_discard(scene):
    from app.ui.penecho_integration.draft_layer import PenechoDraftLayerItem
    from app.ui.penecho_integration.mixed_text import PenechoMixedTextItem

    card = PenechoMixedTextItem(raw_text="Candidate **AI Draft** $E=mc^2$")
    draft = PenechoDraftLayerItem(card, title="Test Draft")
    draft.setPos(200, 300)
    scene.addItem(draft)

    assert draft in scene.items()
    assert card.parentItem() == draft

    # Test Accept
    draft.accept_draft()
    assert draft not in scene.items()
    assert card in scene.items()
    assert card.parentItem() is None
    assert card.scenePos().x() == 200
    assert card.scenePos().y() == 300

    # Test Discard on new draft
    card2 = PenechoMixedTextItem(raw_text="Discard me")
    draft2 = PenechoDraftLayerItem(card2, title="Discard Draft")
    scene.addItem(draft2)
    draft2.discard_draft()
    assert draft2 not in scene.items()
    assert card2 not in scene.items()


def test_magic_orb_widget(qt_app):
    from app.ui.widgets.magic_orb_widget import MagicOrbWidget

    orb = MagicOrbWidget()
    assert orb._state == "idle"
    assert orb._is_auto_ai is True

    orb.set_state("thinking", "Solving Problem...")
    assert orb._state == "thinking"
    assert "Solving" in orb.status_label.text()

    orb.set_state("draft", "Draft Ready")
    assert orb._state == "draft"

    orb.set_state("idle")
    assert orb._state == "idle"
