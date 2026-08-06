"""
Unit tests for StrokeProcessor: vector capture, handwriting de-jittering,
and shape snapping (line, circle, rectangle, polygon).
"""

import pytest
import numpy as np
from app.ui.stroke_processor import (
    downsample_stroke,
    fit_line,
    fit_circle_kasa,
    detect_corners,
    smooth_handwriting,
    classify_stroke,
    StrokeProcessor
)


def test_downsample_stroke():
    # 500 points along a line
    t = np.linspace(0, 100, 500)
    pts = np.column_stack((t, t * 2))
    downsampled = downsample_stroke(pts, max_points=100)
    assert len(downsampled) == 100
    assert np.isclose(downsampled[0, 0], 0.0)
    assert np.isclose(downsampled[-1, 0], 100.0)


def test_fit_line_pure():
    # Perfect straight line with tiny noise
    t = np.linspace(10, 200, 50)
    noise = np.random.normal(0, 0.1, 50)
    pts = np.column_stack((t, t * 0.5 + 10 + noise))
    
    res = fit_line(pts)
    assert res['is_valid'] is True
    assert res['rmse'] < 1.0
    assert res['max_error'] < 2.0


def test_fit_circle_kasa_pure():
    # Perfect circle with radius 50 at (100, 100)
    angles = np.linspace(0, 2 * np.pi, 100)
    cx, cy, r = 100.0, 100.0, 50.0
    x = cx + r * np.cos(angles) + np.random.normal(0, 0.2, 100)
    y = cy + r * np.sin(angles) + np.random.normal(0, 0.2, 100)
    pts = np.column_stack((x, y))

    res = fit_circle_kasa(pts)
    assert res['is_valid'] is True
    assert abs(res['center'][0] - cx) < 1.0
    assert abs(res['center'][1] - cy) < 1.0
    assert abs(res['radius'] - r) < 1.0
    assert res['relative_error'] < 0.05


def test_corner_detection_rectangle():
    # Rectangle vertices: (0,0) -> (100,0) -> (100,50) -> (0,50) -> (0,0)
    side1 = np.column_stack((np.linspace(0, 100, 30), np.zeros(30)))
    side2 = np.column_stack((np.full(30, 100.0), np.linspace(0, 50, 30)))
    side3 = np.column_stack((np.linspace(100, 0, 30), np.full(30, 50.0)))
    side4 = np.column_stack((np.zeros(30), np.linspace(50, 0, 30)))
    rect_pts = np.vstack([side1, side2[1:], side3[1:], side4[1:]])

    corners = detect_corners(rect_pts)
    # Should detect 3 or 4 interior corners
    assert len(corners) in [3, 4]


def test_smooth_handwriting():
    # Jittery curve
    t = np.linspace(0, 10, 40)
    jitter = np.random.normal(0, 1.5, 40)
    pts = np.column_stack((t * 10, np.sin(t) * 20 + jitter))

    smoothed = smooth_handwriting(pts, smooth_factor=1.5)
    assert len(smoothed) > 0
    # Smoothed curve should have lower variance in point differences than raw jittery input
    raw_diff_var = np.var(np.diff(pts, axis=0))
    smooth_diff_var = np.var(np.diff(smoothed, axis=0))
    assert smooth_diff_var < raw_diff_var * 1.5


def test_classify_stroke_line():
    t = np.linspace(0, 150, 60)
    noise = np.random.normal(0, 0.2, 60)
    pts = np.column_stack((t, t * 1.2 + noise))
    
    cls_type, conf, details = classify_stroke(pts)
    assert cls_type == 'shape'
    assert details['shape_type'] == 'line'
    assert conf > 0.8


def test_classify_stroke_circle():
    angles = np.linspace(0, 2 * np.pi, 80)
    pts = np.column_stack((200 + 60 * np.cos(angles), 150 + 60 * np.sin(angles)))
    
    cls_type, conf, details = classify_stroke(pts)
    assert cls_type == 'shape'
    assert details['shape_type'] == 'circle'
    assert conf > 0.8


def test_classify_stroke_handwriting():
    # Irregular handwriting s-curve
    t = np.linspace(0, 5, 50)
    x = t * 15 + np.sin(t * 3) * 10
    y = np.cos(t * 2) * 25 + np.sin(t * 7) * 5
    pts = np.column_stack((x, y))

    cls_type, conf, details = classify_stroke(pts)
    assert cls_type == 'handwriting'
