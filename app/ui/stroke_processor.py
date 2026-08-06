"""
Smart Stroke Processor for Handwriting De-jittering & Real-time Shape Snapping.

Features:
1. Vector stroke capture with pressure & timestamp support (mouse & tablet).
2. Pure geometric classification (Handwriting vs. Shape: Line, Circle, Rectangle, Polygon).
3. Handwriting de-jittering via SciPy B-spline interpolation.
4. Least-squares & algebraic shape fitting (Line PCA, Kasa Circle, Angle-change Corner Detection).
5. Self-contained PyQt6 integration preserving raw vector data for future revert capabilities.
"""

import time
import math
import numpy as np
from scipy.interpolate import splprep, splev

from PyQt6.QtWidgets import (
    QGraphicsScene, QGraphicsPathItem, QGraphicsLineItem, 
    QGraphicsEllipseItem, QGraphicsRectItem, QGraphicsPolygonItem
)
from PyQt6.QtGui import QPen, QColor, QPainterPath, QPolygonF
from PyQt6.QtCore import Qt, QPointF, QRectF, QLineF


# ==============================================================================
# TUNABLE THRESHOLD CONSTANTS & CONFIGURATION
# ==============================================================================

# Performance downsampling threshold (strokes with > max_points are downsampled before fitting)
DOWNSAMPLE_MAX_POINTS: int = 200

# SciPy B-Spline handwriting smoothing factor 's' multiplier
# Higher values = smoother/rounder handwriting; Lower values = closer to raw input
SPLINE_SMOOTH_FACTOR: float = 1.5

# Straight Line Fitting Thresholds (PCA / Total Least Squares)
# Maximum Root Mean Square Error (in pixels) perpendicular to line fit
LINE_MAX_RMSE_PX: float = 5.0
# Maximum peak perpendicular distance error (in pixels) along line
LINE_MAX_ERROR_PX: float = 12.0
# Minimum directness ratio (end-to-end distance / total stroke length)
LINE_MIN_DIRECTNESS: float = 0.88

# Circle / Ellipse Fitting Thresholds (Kasa Algebraic Least-Squares)
# Maximum relative radial error (radial RMSE / fitted radius)
CIRCLE_MAX_RELATIVE_ERROR: float = 0.16
# Maximum absolute radial RMSE (in pixels)
CIRCLE_MAX_RMSE_PX: float = 9.0

# Closed Loop Thresholds (for circles, rectangles, and polygons)
# Maximum absolute distance (px) between start and end of stroke to consider it closed
CLOSED_LOOP_MAX_DIST_PX: float = 40.0
# Maximum relative start-to-end distance relative to stroke bounding box diagonal
CLOSED_LOOP_RELATIVE_THRES: float = 0.28

# Corner Detection Thresholds (Polygon & Rectangle fitting)
# Minimum direction change angle (in degrees) to register a corner peak
CORNER_ANGLE_THRESHOLD_DEG: float = 35.0
# Minimum arc distance (in pixels) between consecutive detected corners
MIN_CORNER_DISTANCE_PX: float = 15.0
# Angle tolerance (in degrees) around 90° for rectangle/quadrilateral detection
RECTANGLE_ANGLE_TOLERANCE_DEG: float = 22.0


# ==============================================================================
# PURE GEOMETRIC FITTING & CLASSIFICATION FUNCTIONS (NO QT DEPENDENCIES)
# ==============================================================================

def downsample_stroke(points: np.ndarray, max_points: int = DOWNSAMPLE_MAX_POINTS) -> np.ndarray:
    """
    Downsamples high-point-count strokes using uniform arc-length resampling.
    Improves real-time geometric fitting performance for long strokes.
    
    Parameters:
        points: (N, 2) array of (x, y) coordinates.
        max_points: Maximum number of points to retain.
        
    Returns:
        (M, 2) array of downsampled points where M <= max_points.
    """
    if len(points) <= max_points:
        return points

    diffs = np.diff(points, axis=0)
    dists = np.hypot(diffs[:, 0], diffs[:, 1])
    cum_dists = np.insert(np.cumsum(dists), 0, 0.0)
    total_length = cum_dists[-1]

    if total_length < 1e-6:
        return points[:max_points]

    target_dists = np.linspace(0.0, total_length, max_points)
    new_x = np.interp(target_dists, cum_dists, points[:, 0])
    new_y = np.interp(target_dists, cum_dists, points[:, 1])
    return np.column_stack((new_x, new_y))


def fit_line(points: np.ndarray) -> dict:
    """
    Fits a straight 2D line segment using Total Least Squares (Principal Component Analysis).
    Handles vertical, horizontal, and arbitrary sloped lines robustly.
    
    Returns:
        dict with fit validity, endpoints p1=(x1,y1), p2=(x2,y2), rmse, and max_error.
    """
    if len(points) < 2:
        return {'is_valid': False, 'rmse': float('inf'), 'max_error': float('inf')}

    mean = np.mean(points, axis=0)
    centered = points - mean

    try:
        _, _, vh = np.linalg.svd(centered)
        dir_vec = vh[0]  # Principal direction vector
        normal_vec = np.array([-dir_vec[1], dir_vec[0]])

        perp_dists = np.abs(np.dot(centered, normal_vec))
        rmse = float(np.sqrt(np.mean(perp_dists**2)))
        max_error = float(np.max(perp_dists))

        projections = np.dot(centered, dir_vec)
        min_proj, max_proj = np.min(projections), np.max(projections)

        p1 = mean + min_proj * dir_vec
        p2 = mean + max_proj * dir_vec

        return {
            'is_valid': True,
            'p1': (float(p1[0]), float(p1[1])),
            'p2': (float(p2[0]), float(p2[1])),
            'rmse': rmse,
            'max_error': max_error,
            'dir_vec': (float(dir_vec[0]), float(dir_vec[1]))
        }
    except Exception:
        return {'is_valid': False, 'rmse': float('inf'), 'max_error': float('inf')}


def fit_circle_kasa(points: np.ndarray) -> dict:
    """
    Fits a circle to 2D points using Kasa's algebraic least-squares method.
    Algebraic equation: x^2 + y^2 + D*x + E*y + F = 0
    
    Returns:
        dict with center=(cx, cy), radius, rmse, and relative_error (rmse / radius).
    """
    if len(points) < 4:
        return {'is_valid': False, 'rmse': float('inf'), 'relative_error': float('inf')}

    x = points[:, 0]
    y = points[:, 1]

    A = np.column_stack((x, y, np.ones_like(x)))
    B = -(x**2 + y**2)

    try:
        sol, _, _, _ = np.linalg.lstsq(A, B, rcond=None)
        D, E, F = sol
        cx = -D / 2.0
        cy = -E / 2.0
        val = (D**2 + E**2) / 4.0 - F

        if val <= 0:
            return {'is_valid': False, 'rmse': float('inf'), 'relative_error': float('inf')}

        radius = float(np.sqrt(val))
        radial_dists = np.hypot(x - cx, y - cy)
        errors = np.abs(radial_dists - radius)
        rmse = float(np.sqrt(np.mean(errors**2)))
        relative_error = rmse / radius if radius > 0 else float('inf')

        return {
            'is_valid': True,
            'center': (float(cx), float(cy)),
            'radius': radius,
            'rmse': rmse,
            'relative_error': relative_error
        }
    except Exception:
        return {'is_valid': False, 'rmse': float('inf'), 'relative_error': float('inf')}


def detect_corners(points: np.ndarray,
                   min_angle_deg: float = CORNER_ANGLE_THRESHOLD_DEG,
                   min_dist_px: float = MIN_CORNER_DISTANCE_PX) -> list[int]:
    """
    Detects corner indices along a stroke by analyzing local tangent angular changes.
    """
    N = len(points)
    if N < 8:
        return []

    # Adaptive window size based on point count
    window = max(2, min(8, N // 15))
    
    angles = np.zeros(N)
    min_angle_rad = np.radians(min_angle_deg)
    
    for i in range(window, N - window):
        v_in = points[i] - points[i - window]
        v_out = points[i + window] - points[i]
        
        norm_in = np.hypot(v_in[0], v_in[1])
        norm_out = np.hypot(v_out[0], v_out[1])
        
        if norm_in > 1e-4 and norm_out > 1e-4:
            unit_in = v_in / norm_in
            unit_out = v_out / norm_out
            dot = np.clip(np.dot(unit_in, unit_out), -1.0, 1.0)
            angles[i] = np.arccos(dot)

    candidate_peaks = []
    for i in range(window + 1, N - window - 1):
        if angles[i] >= min_angle_rad and angles[i] >= angles[i - 1] and angles[i] >= angles[i + 1]:
            candidate_peaks.append((i, angles[i]))

    filtered_indices = []
    for idx, _ in candidate_peaks:
        if not filtered_indices:
            filtered_indices.append(idx)
        else:
            prev_idx = filtered_indices[-1]
            dist = np.hypot(*(points[idx] - points[prev_idx]))
            if dist >= min_dist_px:
                filtered_indices.append(idx)

    return filtered_indices


def smooth_handwriting(points: np.ndarray,
                       smooth_factor: float = SPLINE_SMOOTH_FACTOR,
                       num_samples: int = 0) -> np.ndarray:
    """
    De-jitters handwriting using SciPy B-spline interpolation (splprep/splev).
    Preserves original stroke characteristics while smoothing tremulous jitter.
    
    Parameters:
        points: (N, 2) array of raw stroke (x, y) coordinates.
        smooth_factor: B-spline smoothing multiplier.
        num_samples: Target output point count (0 = auto based on length).
        
    Returns:
        (M, 2) array of de-jittered (x, y) coordinates.
    """
    N = len(points)
    if N < 4:
        return points

    # Remove consecutive duplicate/micro-step points
    diffs = np.diff(points, axis=0)
    dists = np.hypot(diffs[:, 0], diffs[:, 1])
    keep = np.insert(dists > 1e-4, 0, True)
    pts = points[keep]

    M = len(pts)
    if M < 4:
        return points

    x = pts[:, 0]
    y = pts[:, 1]

    try:
        k_degree = min(3, M - 1)
        # B-spline fitting
        tck, u = splprep([x, y], s=smooth_factor * M, k=k_degree)

        if num_samples <= 0:
            total_dist = np.sum(dists)
            num_samples = int(max(M, min(300, total_dist / 2.0)))

        u_new = np.linspace(0, 1, num_samples)
        x_smooth, y_smooth = splev(u_new, tck)
        return np.column_stack((x_smooth, y_smooth))
    except Exception:
        # Graceful fallback if spline fails
        return points


def classify_stroke(points: np.ndarray) -> tuple[str, float, dict]:
    """
    Classifies an input stroke as either 'handwriting' or 'shape' using geometric heuristics.
    Pure function — zero Qt dependencies.
    
    Parameters:
        points: (N, 2) array of stroke (x, y) coordinates.
        
    Returns:
        tuple: (classification, confidence, shape_details)
            - classification: 'handwriting' or 'shape'
            - confidence: float between 0.0 and 1.0
            - shape_details: dict specifying shape parameters if classified as 'shape'
    """
    N = len(points)
    if N < 3:
        return ('handwriting', 1.0, {})

    # Performance downsampling for evaluation
    pts_eval = downsample_stroke(points, max_points=DOWNSAMPLE_MAX_POINTS)

    # Calculate stroke metrics
    diffs = np.diff(pts_eval, axis=0)
    segment_lengths = np.hypot(diffs[:, 0], diffs[:, 1])
    total_length = float(np.sum(segment_lengths))
    if total_length < 5.0:  # Micro tap/dot
        return ('handwriting', 1.0, {})

    start_end_dist = float(np.hypot(*(pts_eval[-1] - pts_eval[0])))
    directness_ratio = start_end_dist / total_length

    # Bounding Box metrics
    min_xy = np.min(pts_eval, axis=0)
    max_xy = np.max(pts_eval, axis=0)
    bbox_w = float(max_xy[0] - min_xy[0])
    bbox_h = float(max_xy[1] - min_xy[1])
    bbox_diag = float(np.hypot(bbox_w, bbox_h))

    # Evaluate Shape Candidates
    line_fit = fit_line(pts_eval)
    circle_fit = fit_circle_kasa(pts_eval)
    corners = detect_corners(pts_eval)

    # 1. Straight Line Check
    if (line_fit['is_valid'] and 
        line_fit['rmse'] < LINE_MAX_RMSE_PX and 
        line_fit['max_error'] < LINE_MAX_ERROR_PX and 
        directness_ratio > LINE_MIN_DIRECTNESS):
        return ('shape', 0.95, {'shape_type': 'line', 'fit': line_fit})

    # 2. Circle / Ellipse Check
    is_closed = start_end_dist < max(CLOSED_LOOP_MAX_DIST_PX, bbox_diag * CLOSED_LOOP_RELATIVE_THRES)
    if (circle_fit['is_valid'] and 
        circle_fit['relative_error'] < CIRCLE_MAX_RELATIVE_ERROR and 
        circle_fit['rmse'] < CIRCLE_MAX_RMSE_PX and 
        is_closed):
        return ('shape', 0.92, {'shape_type': 'circle', 'fit': circle_fit})

    # 3. Polygon / Rectangle Check
    num_corners = len(corners)
    if is_closed and num_corners in [3, 4, 5, 6]:
        corner_pts = pts_eval[corners]

        if num_corners == 4:
            # Check for rectangle near 90-degree corners
            v = np.vstack([corner_pts, corner_pts[0]])
            side_vecs = np.diff(v, axis=0)
            side_norms = np.hypot(side_vecs[:, 0], side_vecs[:, 1])
            valid_sides = side_norms > 1e-4

            if np.all(valid_sides):
                unit_sides = side_vecs / side_norms[:, None]
                angles_deg = []
                for i in range(4):
                    dot = np.clip(np.dot(-unit_sides[i-1], unit_sides[i]), -1.0, 1.0)
                    angles_deg.append(np.degrees(np.arccos(dot)))

                if all(abs(ang - 90.0) < RECTANGLE_ANGLE_TOLERANCE_DEG for ang in angles_deg):
                    return ('shape', 0.90, {
                        'shape_type': 'rectangle',
                        'bbox': (float(min_xy[0]), float(min_xy[1]), bbox_w, bbox_h),
                        'corners': corner_pts
                    })

        return ('shape', 0.85, {
            'shape_type': 'polygon',
            'corners': corner_pts
        })

    # Default fallback: Classified as natural handwriting
    return ('handwriting', 0.90, {})


# ==============================================================================
# STROKE PROCESSOR CLASS (PYQT6 INTEGRATION LAYER)
# ==============================================================================

class StrokeProcessor:
    """
    Self-contained manager that receives raw input points (mouse & QTabletEvent),
    stores vector history (raw & processed), classifies strokes, and produces
    snapped shape items or smoothed handwriting items for QGraphicsScene.
    """

    def __init__(self, enable_smart_shapes: bool = True, enable_smoothing: bool = True):
        self.enable_smart_shapes = enable_smart_shapes
        self.enable_smoothing = enable_smoothing
        self.raw_points: list[tuple[float, float, float, float]] = []  # (x, y, pressure, timestamp)

    def start_stroke(self, pos: QPointF, pressure: float = 1.0, timestamp: float = None):
        """Starts capturing a new stroke."""
        if timestamp is None:
            timestamp = time.time()
        self.raw_points = [(float(pos.x()), float(pos.y()), float(pressure), float(timestamp))]

    def add_point(self, pos: QPointF, pressure: float = 1.0, timestamp: float = None):
        """Appends a new point to the active stroke."""
        if timestamp is None:
            timestamp = time.time()
        self.raw_points.append((float(pos.x()), float(pos.y()), float(pressure), float(timestamp)))

    def process_stroke(self, 
                       color: QColor = QColor("#1c1c1e"), 
                       width: float = 3.0, 
                       tool_mode: str = "pen") -> QGraphicsPathItem | QGraphicsLineItem | QGraphicsEllipseItem | QGraphicsRectItem | QGraphicsPolygonItem:
        """
        Processes captured stroke points upon pen release.
        Classifies stroke, applies shape snapping or de-jittering, attach vector metadata,
        and returns the finalized QGraphicsItem.
        """
        if not self.raw_points:
            return None

        points_np = np.array([(p[0], p[1]) for p in self.raw_points], dtype=np.float64)
        pressures = [p[2] for p in self.raw_points]
        avg_pressure = float(np.mean(pressures)) if pressures else 1.0

        # Setup standard pen styling
        pen = QPen(QColor(color), width * max(0.4, avg_pressure))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        if tool_mode == "highlighter":
            highlight_color = QColor(color)
            highlight_color.setAlpha(100)
            pen.setColor(highlight_color)
            pen.setWidthF(18.0)

        # Classify stroke
        classification, confidence, details = classify_stroke(points_np)

        # ----------------------------------------------------------------------
        # 1. SHAPE SNAPPING (If classified as Shape)
        # ----------------------------------------------------------------------
        if self.enable_smart_shapes and classification == 'shape':
            shape_type = details.get('shape_type')

            if shape_type == 'line':
                fit = details['fit']
                p1 = QPointF(*fit['p1'])
                p2 = QPointF(*fit['p2'])
                item = QGraphicsLineItem(QLineF(p1, p2))
                item.setPen(pen)
                
                # Metadata
                item.raw_stroke = self.raw_points
                item.processed_stroke = [fit['p1'], fit['p2']]
                item.stroke_type = "line"
                item.classification_confidence = confidence
                return item

            elif shape_type == 'circle':
                fit = details['fit']
                cx, cy = fit['center']
                r = fit['radius']
                rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
                item = QGraphicsEllipseItem(rect)
                item.setPen(pen)

                # Metadata
                item.raw_stroke = self.raw_points
                item.processed_stroke = [(cx, cy, r)]
                item.stroke_type = "circle"
                item.classification_confidence = confidence
                return item

            elif shape_type == 'rectangle':
                x, y, w, h = details['bbox']
                item = QGraphicsRectItem(QRectF(x, y, w, h))
                item.setPen(pen)

                # Metadata
                item.raw_stroke = self.raw_points
                item.processed_stroke = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
                item.stroke_type = "rectangle"
                item.classification_confidence = confidence
                return item

            elif shape_type == 'polygon':
                corners = details['corners']
                polygon = QPolygonF([QPointF(pt[0], pt[1]) for pt in corners])
                item = QGraphicsPolygonItem(polygon)
                item.setPen(pen)

                # Metadata
                item.raw_stroke = self.raw_points
                item.processed_stroke = [tuple(pt) for pt in corners]
                item.stroke_type = "polygon"
                item.classification_confidence = confidence
                return item

        # ----------------------------------------------------------------------
        # 2. HANDWRITING SMOOTHING (De-jitter via SciPy B-Splines)
        # ----------------------------------------------------------------------
        if self.enable_smoothing and len(points_np) >= 4:
            smoothed_pts = smooth_handwriting(points_np, smooth_factor=SPLINE_SMOOTH_FACTOR)
        else:
            smoothed_pts = points_np

        # Build QPainterPath for de-jittered handwriting
        path = QPainterPath()
        if len(smoothed_pts) > 0:
            path.moveTo(QPointF(float(smoothed_pts[0][0]), float(smoothed_pts[0][1])))
            for pt in smoothed_pts[1:]:
                path.lineTo(QPointF(float(pt[0]), float(pt[1])))

        item = QGraphicsPathItem(path)
        item.setPen(pen)

        # Store vector metadata for future revert / edit capabilities
        item.raw_stroke = self.raw_points
        item.processed_stroke = [tuple(pt) for pt in smoothed_pts]
        item.stroke_type = "handwriting"
        item.classification_confidence = confidence

        return item
