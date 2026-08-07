"""
Unit Tests for Real-Time Shape Fitting, Unit Conversion, Pure Path Generators, and Metadata Registry.
"""

import math
import numpy as np
import pytest

from app.ui.shape_metadata import (
    SHAPE_METADATA, convert_px_to_unit, convert_unit_to_px, SUPPORTED_UNITS
)
from app.ui.stroke_processor import (
    classify_stroke, classify_stroke_precheck, 
    fit_line, fit_arrow, fit_circle_kasa, fit_ellipse, 
    fit_rectangle_and_square, fit_cloud,
    generate_arrowhead_polygon, generate_cloud_path_points
)


def test_unit_conversions():
    """Verifies bidirectional unit conversion accuracy between canvas pixels and physical units."""
    dpi = 96.0
    val_px = 96.0

    # 96 px at 96 DPI == 1.0 inch
    inch_val = convert_px_to_unit(val_px, "inch", dpi=dpi)
    assert pytest.approx(inch_val, 1e-4) == 1.0
    assert pytest.approx(convert_unit_to_px(inch_val, "inch", dpi=dpi), 1e-4) == val_px

    # 1 inch == 25.4 mm
    mm_val = convert_px_to_unit(val_px, "mm", dpi=dpi)
    assert pytest.approx(mm_val, 1e-4) == 25.4
    assert pytest.approx(convert_unit_to_px(mm_val, "mm", dpi=dpi), 1e-4) == val_px

    # 1 inch == 2.54 cm
    cm_val = convert_px_to_unit(val_px, "cm", dpi=dpi)
    assert pytest.approx(cm_val, 1e-4) == 2.54
    assert pytest.approx(convert_unit_to_px(cm_val, "cm", dpi=dpi), 1e-4) == val_px

    # 1 inch == 0.0254 m
    m_val = convert_px_to_unit(val_px, "m", dpi=dpi)
    assert pytest.approx(m_val, 1e-4) == 0.0254
    assert pytest.approx(convert_unit_to_px(m_val, "m", dpi=dpi), 1e-4) == val_px


def test_shape_metadata_registry():
    """Verifies that all 7 shape types are defined in SHAPE_METADATA with required schema."""
    expected_shapes = ["circle", "ellipse", "rectangle", "square", "line", "arrow", "cloud"]
    for shape in expected_shapes:
        assert shape in SHAPE_METADATA
        meta = SHAPE_METADATA[shape]
        assert "display_name" in meta
        assert "fields" in meta
        assert "handles" in meta
        assert len(meta["fields"]) >= 1


def test_fit_straight_line():
    """Verifies linear regression PCA fitting for straight lines."""
    t = np.linspace(0, 100, 50)
    # Perfectly horizontal line
    points = np.column_stack((t, np.zeros_like(t)))
    fit = fit_line(points)
    assert fit['is_valid']
    assert fit['rmse'] < 0.1
    assert pytest.approx(fit['p1'][0], 1e-2) == 0.0
    assert pytest.approx(fit['p2'][0], 1e-2) == 100.0


def test_fit_arrow():
    """Verifies arrow fitting with endpoint flare detection."""
    t = np.linspace(0, 100, 40)
    shaft = np.column_stack((t, np.zeros_like(t)))
    # Add arrowhead flare at endpoint (100, 0)
    flare = np.array([
        [90, 10],
        [100, 0],
        [90, -10]
    ])
    points = np.vstack([shaft, flare])
    fit = fit_arrow(points)
    assert fit['is_valid']
    assert fit['head_at'] == 'p2'


def test_fit_circle():
    """Verifies Kasa algebraic circle fitting."""
    theta = np.linspace(0, 2 * math.pi, 60)
    cx, cy, r = 50.0, 50.0, 30.0
    x = cx + r * np.cos(theta)
    y = cy + r * np.sin(theta)
    points = np.column_stack((x, y))

    fit = fit_circle_kasa(points)
    assert fit['is_valid']
    assert pytest.approx(fit['center'][0], 1e-2) == cx
    assert pytest.approx(fit['center'][1], 1e-2) == cy
    assert pytest.approx(fit['radius'], 1e-2) == r


def test_fit_rectangle_and_square():
    """Verifies corner detection and 1:1 aspect ratio square reclassification."""
    # Perfect square corners
    sq_points = np.array([
        [0, 0], [50, 0], [50, 50], [0, 50], [0, 0]
    ], dtype=np.float64)

    # Dense sampling along square perimeter
    dense_pts = []
    for i in range(len(sq_points) - 1):
        p1, p2 = sq_points[i], sq_points[i+1]
        for alpha in np.linspace(0, 1, 15):
            dense_pts.append((1 - alpha) * p1 + alpha * p2)
    dense_pts = np.array(dense_pts)

    fit = fit_rectangle_and_square(dense_pts)
    assert fit['is_valid']
    assert fit['shape_type'] == 'square'
    assert pytest.approx(fit['side'], 1.0) == 50.0

    # Unequal rectangle
    rect_points = np.array([
        [0, 0], [100, 0], [100, 40], [0, 40], [0, 0]
    ], dtype=np.float64)
    dense_rect = []
    for i in range(len(rect_points) - 1):
        p1, p2 = rect_points[i], rect_points[i+1]
        for alpha in np.linspace(0, 1, 15):
            dense_rect.append((1 - alpha) * p1 + alpha * p2)
    dense_rect = np.array(dense_rect)

    rect_fit = fit_rectangle_and_square(dense_rect)
    assert rect_fit['is_valid']
    assert rect_fit['shape_type'] == 'rectangle'
    assert pytest.approx(rect_fit['width'], 1.0) == 100.0
    assert pytest.approx(rect_fit['height'], 1.0) == 40.0


def test_fit_cloud():
    """Verifies cloud detection via curvature oscillation variance."""
    theta = np.linspace(0, 2 * math.pi, 80)
    # Base circle + high frequency sinusoidal curvature bumps
    rx, ry = 60.0, 40.0
    r_bump = 8.0 * np.sin(12 * theta)
    x = (rx + r_bump) * np.cos(theta)
    y = (ry + r_bump) * np.sin(theta)
    points = np.column_stack((x, y))

    fit = fit_cloud(points)
    assert fit['is_valid']
    assert fit['curvature_var'] > 0.01


def test_pure_arrowhead_generator():
    """Verifies arrow head polygon coordinate generation."""
    p1 = (0.0, 0.0)
    p2 = (100.0, 0.0)
    head_len = 20.0
    head_angle = 30.0

    poly = generate_arrowhead_polygon(p1, p2, head_length=head_len, head_angle_deg=head_angle)
    assert len(poly) == 3
    # Tip point
    assert poly[0] == p2
    # Left and right wings should extend backwards from p2
    assert poly[1][0] < 100.0
    assert poly[2][0] < 100.0


def test_pure_cloud_path_generator():
    """Verifies cloud bump path arc generator."""
    bbox = (0.0, 0.0, 100.0, 80.0)
    bumps = generate_cloud_path_points(bbox)
    assert len(bumps) >= 6
    for b in bumps:
        assert "start" in b
        assert "end" in b
        assert "control" in b
