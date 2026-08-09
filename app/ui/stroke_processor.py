"""
Smart Stroke Processor for Handwriting De-jittering & Real-time Shape Snapping.

Features:
1. Vector stroke capture with pressure & timestamp support (mouse & tablet).
2. Pure geometric classification for 7 Shape Types:
   - Rectangle, Square, Circle, Ellipse, Straight Line, Arrow, Cloud.
3. Live Hold-to-Snap state machine (500ms hold, 3px movement threshold).
4. Handwriting de-jittering via SciPy B-spline interpolation.
5. Least-squares & algebraic shape fitting (Line PCA, Kasa Circle, Angle-change Corner Detection, Cloud Curvature Oscillation).
6. Self-contained PyQt6 integration preserving raw vector data for future revert capabilities.
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
# DEBUG FLAG — set to True to print classification decisions during development
# ==============================================================================
SHAPE_DEBUG: bool = False


def _dbg(msg: str) -> None:
    """No-op unless SHAPE_DEBUG is True. Centralises all debug output."""
_dbg(msg)


# ==============================================================================
# TUNABLE THRESHOLD CONSTANTS & CONFIGURATION
# ==============================================================================

# Live Hold-to-Snap Constants (250ms hold for responsive feel, 6px move threshold for jitter tolerance)
HOLD_DURATION_MS: int = 250
# Minimum pixel movement that resets the hold timer during a stroke
HOLD_MOVE_THRESHOLD_PX: float = 6.0

# Performance downsampling threshold
DOWNSAMPLE_MAX_POINTS: int = 200

# SciPy B-Spline handwriting smoothing factor 's' multiplier
SPLINE_SMOOTH_FACTOR: float = 1.5

# Straight Line Fitting Thresholds (PCA / Total Least Squares)
LINE_MAX_RMSE_PX: float = 6.0
LINE_MAX_ERROR_PX: float = 14.0
LINE_MIN_DIRECTNESS: float = 0.85

# Arrow Fitting Thresholds
# Fraction of total point count treated as the "head" region to inspect for flare
ARROW_TAIL_RATIO: float = 0.20
ARROW_HEAD_LENGTH_PX: float = 16.0
ARROW_HEAD_ANGLE_DEG: float = 30.0
# Minimum angle change (deg) at endpoint to qualify as an arrowhead flare
ARROW_FLARE_MIN_ANGLE_DEG: float = 20.0
# Maximum angle change (deg) — above this it looks like a corner, not a flare
ARROW_FLARE_MAX_ANGLE_DEG: float = 150.0
# Shaft RMSE must be below this to qualify as an arrow (tight line on shaft)
ARROW_SHAFT_MAX_RMSE_PX: float = 5.0
# Directness of whole stroke (arrow is NOT a closed loop)
ARROW_MIN_DIRECTNESS: float = 0.45

# Circle / Ellipse Fitting Thresholds (Kasa Algebraic Least-Squares)
CIRCLE_MAX_RELATIVE_ERROR: float = 0.18
CIRCLE_MAX_RMSE_PX: float = 10.0

# Square vs Rectangle Tolerance (10% ratio tolerance)
SQUARE_TOLERANCE_RATIO: float = 0.10

# Closed Loop Thresholds
CLOSED_LOOP_MAX_DIST_PX: float = 45.0
CLOSED_LOOP_RELATIVE_THRES: float = 0.30

# Corner Detection Thresholds
CORNER_ANGLE_THRESHOLD_DEG: float = 30.0
MIN_CORNER_DISTANCE_PX: float = 12.0
RECTANGLE_ANGLE_TOLERANCE_DEG: float = 25.0

# Cloud Detection & Generation Thresholds
CLOUD_MIN_BUMP_COUNT: int = 6
CLOUD_MAX_BUMP_COUNT: int = 24
CLOUD_BUMP_SPACING_PX: float = 24.0
CLOUD_BUMP_AMPLITUDE_PX: float = 8.0
# Minimum curvature variance to qualify as cloud (higher = needs more oscillation)
CLOUD_CURVATURE_VAR_THRESHOLD: float = 0.006
# Minimum bbox size (px) for cloud recognition — short strokes like letters are excluded
CLOUD_MIN_BBOX_PX: float = 45.0
# Minimum stroke arc-length for cloud recognition
CLOUD_MIN_ARC_LENGTH_PX: float = 80.0
# Minimum number of curvature sign changes (bumps) for cloud
CLOUD_MIN_SIGN_CHANGES: int = 7

# Pre-classifier minimum thresholds (strokes below these are always handwriting)
PRECHECK_MIN_ARC_LENGTH_PX: float = 20.0
PRECHECK_MIN_BBOX_DIAG_PX: float = 20.0


# ==============================================================================
# PURE GEOMETRIC FITTING & CLASSIFICATION FUNCTIONS (NO QT DEPENDENCIES)
# ==============================================================================

def downsample_stroke(points: np.ndarray, max_points: int = DOWNSAMPLE_MAX_POINTS) -> np.ndarray:
    """
    Downsamples high-point-count strokes using uniform arc-length resampling.
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


def generate_arrowhead_polygon(p1: tuple[float, float], 
                               p2: tuple[float, float], 
                               head_length: float = ARROW_HEAD_LENGTH_PX, 
                               head_angle_deg: float = ARROW_HEAD_ANGLE_DEG) -> list[tuple[float, float]]:
    """
    Pure geometric function generating triangular arrowhead coordinates at endpoint p2.
    """
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    angle = math.atan2(dy, dx)
    rad = math.radians(head_angle_deg)
    
    left_x = p2[0] - head_length * math.cos(angle - rad)
    left_y = p2[1] - head_length * math.sin(angle - rad)
    right_x = p2[0] - head_length * math.cos(angle + rad)
    right_y = p2[1] - head_length * math.sin(angle + rad)
    
    return [p2, (left_x, left_y), (right_x, right_y)]


def generate_cloud_path_points(bbox: tuple[float, float, float, float], 
                               bump_spacing: float = CLOUD_BUMP_SPACING_PX, 
                               bump_amplitude: float = CLOUD_BUMP_AMPLITUDE_PX) -> list[dict]:
    """
    Pure geometric function generating arc bump parameters around a bounding box.
    """
    x, y, w, h = bbox
    cx = x + w / 2.0
    cy = y + h / 2.0
    rx = max(5.0, w / 2.0)
    ry = max(5.0, h / 2.0)
    
    perimeter = math.pi * (3 * (rx + ry) - math.sqrt((3 * rx + ry) * (rx + 3 * ry)))
    num_bumps = max(CLOUD_MIN_BUMP_COUNT, min(CLOUD_MAX_BUMP_COUNT, int(round(perimeter / bump_spacing))))
    
    bumps = []
    for i in range(num_bumps):
        t1 = 2.0 * math.pi * i / num_bumps
        t2 = 2.0 * math.pi * (i + 1) / num_bumps
        t_mid = (t1 + t2) / 2.0
        pt1 = (cx + rx * math.cos(t1), cy + ry * math.sin(t1))
        pt2 = (cx + rx * math.cos(t2), cy + ry * math.sin(t2))
        ctrl = (cx + (rx + bump_amplitude) * math.cos(t_mid), cy + (ry + bump_amplitude) * math.sin(t_mid))
        bumps.append({"start": pt1, "end": pt2, "control": ctrl})
        
    return bumps


def fit_line(points: np.ndarray) -> dict:
    """
    Fits a straight 2D line segment using Total Least Squares (PCA).
    """
    if len(points) < 2:
        return {'is_valid': False, 'rmse': float('inf'), 'max_error': float('inf')}

    mean = np.mean(points, axis=0)
    centered = points - mean

    try:
        _, _, vh = np.linalg.svd(centered)
        dir_vec = vh[0]
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


def fit_arrow(points: np.ndarray) -> dict:
    """
    Fits an Arrow shape by detecting a straight shaft line plus a sharp directional
    flare ('V') near one endpoint.

    Strategy:
      1. The whole stroke must be sufficiently 'direct' (not a closed loop).
      2. Split off the last ARROW_TAIL_RATIO fraction as the candidate head region.
      3. Fit a line to the remaining shaft points; shaft RMSE must be tight.
      4. Compute the angle between each segment in the head region and the shaft
         direction. Any segment with angle in [ARROW_FLARE_MIN_ANGLE_DEG,
         ARROW_FLARE_MAX_ANGLE_DEG] is a flare candidate.
      5. Repeat in reverse to detect a flare at the start of the stroke.
    """
    N = len(points)
    if N < 10:
        return {'is_valid': False}

    # Reject closed loops (circles, rectangles, etc.)
    start_end_dist = float(np.hypot(*(points[-1] - points[0])))
    diffs = np.diff(points, axis=0)
    seg_lens = np.hypot(diffs[:, 0], diffs[:, 1])
    total_len = float(np.sum(seg_lens))
    if total_len == 0:
        return {'is_valid': False}

    directness = start_end_dist / total_len
    if directness < ARROW_MIN_DIRECTNESS:
_dbg(f"[Arrow] Rejected: directness={directness:.3f} < {ARROW_MIN_DIRECTNESS}")
        return {'is_valid': False}

    tail_count = max(4, int(N * ARROW_TAIL_RATIO))

    def _check_flare(shaft_pts: np.ndarray, head_pts: np.ndarray, shaft_end: str) -> dict:
        """Fit shaft line, then check head segments for angular flare."""
        lf = fit_line(shaft_pts)
        if not lf['is_valid'] or lf['rmse'] > ARROW_SHAFT_MAX_RMSE_PX:
            if SHAPE_DEBUG:
                rmse = lf.get('rmse', float('inf'))
                print(f"[Arrow] Shaft fit rejected: rmse={rmse:.2f} (max {ARROW_SHAFT_MAX_RMSE_PX})")
            return {'is_valid': False}

        shaft_vec = np.array([lf['p2'][0] - lf['p1'][0], lf['p2'][1] - lf['p1'][1]])
        shaft_len = float(np.hypot(shaft_vec[0], shaft_vec[1]))
        if shaft_len < 15.0:
            return {'is_valid': False}

        # Direction from shaft start toward shaft end
        unit_shaft = shaft_vec / shaft_len
        # For tail-end flare detection, the head segments should deviate from unit_shaft
        head_diffs = np.diff(head_pts, axis=0)
        max_flare_angle = 0.0
        has_flare = False
        for v in head_diffs:
            v_norm = float(np.hypot(v[0], v[1]))
            if v_norm < 1e-3:
                continue
            unit_v = v / v_norm
            # angle between head segment and the shaft forward direction
            dot = float(np.clip(np.dot(unit_shaft, unit_v), -1.0, 1.0))
            ang_deg = float(np.degrees(np.arccos(dot)))
            max_flare_angle = max(max_flare_angle, ang_deg)
            if ARROW_FLARE_MIN_ANGLE_DEG <= ang_deg <= ARROW_FLARE_MAX_ANGLE_DEG:
                has_flare = True

        if SHAPE_DEBUG:
            print(f"[Arrow] Shaft RMSE={lf['rmse']:.2f}, max_flare_angle={max_flare_angle:.1f}°, flare={has_flare}")

        if has_flare:
            return {
                'is_valid': True,
                'p1': lf['p1'],
                'p2': lf['p2'],
                'head_at': shaft_end,
                'shaft_length': float(shaft_len),
                'max_flare_angle': max_flare_angle
            }
        return {'is_valid': False}

    # Try: shaft = points[:-tail_count], head (flare) = points[-tail_count:]
    result = _check_flare(points[:-tail_count], points[-tail_count:], 'p2')
    if result['is_valid']:
        return result

    # Try: shaft = points[tail_count:], head (flare) = points[:tail_count]
    # Reverse shaft direction for comparison
    shaft_rev = points[tail_count:]
    lf_rev = fit_line(shaft_rev)
    if lf_rev['is_valid'] and lf_rev['rmse'] <= ARROW_SHAFT_MAX_RMSE_PX:
        shaft_vec = np.array([lf_rev['p2'][0] - lf_rev['p1'][0], lf_rev['p2'][1] - lf_rev['p1'][1]])
        shaft_len = float(np.hypot(shaft_vec[0], shaft_vec[1]))
        if shaft_len >= 15.0:
            # For start-end flare, head segments should deviate from the shaft's backward direction
            unit_shaft_rev = -shaft_vec / shaft_len
            head_pts = points[:tail_count]
            head_diffs = np.diff(head_pts, axis=0)
            max_flare_angle = 0.0
            has_flare = False
            for v in head_diffs:
                v_norm = float(np.hypot(v[0], v[1]))
                if v_norm < 1e-3:
                    continue
                unit_v = v / v_norm
                dot = float(np.clip(np.dot(unit_shaft_rev, unit_v), -1.0, 1.0))
                ang_deg = float(np.degrees(np.arccos(dot)))
                max_flare_angle = max(max_flare_angle, ang_deg)
                if ARROW_FLARE_MIN_ANGLE_DEG <= ang_deg <= ARROW_FLARE_MAX_ANGLE_DEG:
                    has_flare = True

            if SHAPE_DEBUG:
                print(f"[Arrow] Rev shaft RMSE={lf_rev['rmse']:.2f}, max_flare_angle={max_flare_angle:.1f}°, flare={has_flare}")

            if has_flare:
                return {
                    'is_valid': True,
                    'p1': lf_rev['p2'],
                    'p2': lf_rev['p1'],
                    'head_at': 'p1',
                    'shaft_length': float(shaft_len),
                    'max_flare_angle': max_flare_angle
                }

    return {'is_valid': False}


def fit_circle_kasa(points: np.ndarray) -> dict:
    """
    Fits a circle to 2D points using Kasa's algebraic least-squares method.
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


def fit_ellipse(points: np.ndarray) -> dict:
    """
    Fits a general axis-aligned Ellipse to closed stroke points.
    """
    if len(points) < 6:
        return {'is_valid': False}

    min_xy = np.min(points, axis=0)
    max_xy = np.max(points, axis=0)
    w = float(max_xy[0] - min_xy[0])
    h = float(max_xy[1] - min_xy[1])
    cx = float(min_xy[0] + w / 2.0)
    cy = float(min_xy[1] + h / 2.0)

    if w < 10.0 or h < 10.0:
        return {'is_valid': False}

    return {
        'is_valid': True,
        'center': (cx, cy),
        'width': w,
        'height': h,
        'bbox': (float(min_xy[0]), float(min_xy[1]), w, h)
    }


def detect_corners(points: np.ndarray,
                   min_angle_deg: float = CORNER_ANGLE_THRESHOLD_DEG,
                   min_dist_px: float = MIN_CORNER_DISTANCE_PX) -> list[int]:
    """
    Detects corner indices along a stroke by analyzing local tangent angular changes.
    """
    N = len(points)
    if N < 8:
        return []

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


def fit_rectangle_and_square(points: np.ndarray) -> dict:
    """
    Fits Rectangle or Square from detected corners near 90 degrees.
    """
    corners = detect_corners(points)

    start_end_dist = float(np.hypot(*(points[-1] - points[0])))
    min_xy = np.min(points, axis=0)
    max_xy = np.max(points, axis=0)
    w = float(max_xy[0] - min_xy[0])
    h = float(max_xy[1] - min_xy[1])
    bbox_diag = float(np.hypot(w, h))
    is_closed = start_end_dist < max(CLOSED_LOOP_MAX_DIST_PX, bbox_diag * CLOSED_LOOP_RELATIVE_THRES)

    if len(corners) == 3 and is_closed:
        corners = [0] + corners

    if len(corners) == 5 and is_closed:
        dist_closure = np.hypot(*(points[corners[0]] - points[corners[-1]]))
        if dist_closure < 25.0:
            corners = corners[:4]

    if len(corners) != 4:
        return {'is_valid': False}

    corner_pts = points[corners]

    if w < 5.0 or h < 5.0:
        return {'is_valid': False}

    v = np.vstack([corner_pts, corner_pts[0]])
    side_vecs = np.diff(v, axis=0)
    side_norms = np.hypot(side_vecs[:, 0], side_vecs[:, 1])

    if np.any(side_norms < 1e-4):
        return {'is_valid': False}

    unit_sides = side_vecs / side_norms[:, None]
    angles_deg = []
    for i in range(4):
        dot = np.clip(np.dot(-unit_sides[i-1], unit_sides[i]), -1.0, 1.0)
        angles_deg.append(np.degrees(np.arccos(dot)))

    if not all(abs(ang - 90.0) < RECTANGLE_ANGLE_TOLERANCE_DEG for ang in angles_deg):
        return {'is_valid': False}

    max_dim = max(w, h)
    diff_ratio = abs(w - h) / max_dim if max_dim > 0 else 0.0
    
    if diff_ratio <= SQUARE_TOLERANCE_RATIO:
        side_len = (w + h) / 2.0
        cx = min_xy[0] + w / 2.0
        cy = min_xy[1] + h / 2.0
        sq_x = cx - side_len / 2.0
        sq_y = cy - side_len / 2.0
        return {
            'is_valid': True,
            'shape_type': 'square',
            'side': side_len,
            'bbox': (sq_x, sq_y, side_len, side_len),
            'corners': corner_pts
        }

    return {
        'is_valid': True,
        'shape_type': 'rectangle',
        'width': w,
        'height': h,
        'bbox': (float(min_xy[0]), float(min_xy[1]), w, h),
        'corners': corner_pts
    }


def fit_cloud(points: np.ndarray) -> dict:
    """
    Detects Cloud shape: closed blobby stroke with high-frequency curvature oscillation.

    Strict multi-gate filter to prevent letterforms from being misclassified:
      1. Must be a closed stroke.
      2. Bounding box must be at least CLOUD_MIN_BBOX_PX px on each dimension.
      3. Arc length must be at least CLOUD_MIN_ARC_LENGTH_PX px.
      4. Curvature cross-product variance must exceed CLOUD_CURVATURE_VAR_THRESHOLD.
      5. Must have at least CLOUD_MIN_SIGN_CHANGES curvature sign changes (bumps).
    """
    N = len(points)
    if N < 16:
        return {'is_valid': False}

    start_end_dist = float(np.hypot(*(points[-1] - points[0])))
    min_xy = np.min(points, axis=0)
    max_xy = np.max(points, axis=0)
    w = float(max_xy[0] - min_xy[0])
    h = float(max_xy[1] - min_xy[1])
    bbox_diag = float(np.hypot(w, h))

    # Gate 1: Must be a closed loop
    is_closed = start_end_dist < max(CLOSED_LOOP_MAX_DIST_PX, bbox_diag * CLOSED_LOOP_RELATIVE_THRES)
    if not is_closed:
        if SHAPE_DEBUG:
            print(f"[Cloud] Rejected: not closed (start_end_dist={start_end_dist:.1f})")
        return {'is_valid': False}

    # Reject 4-corner polygonal boxes (rectangle/square candidate)
    corners = detect_corners(points)
    if len(corners) in [3, 4, 5] and is_closed:
_dbg(f"[Cloud] Rejected: {len(corners)} sharp corners detected (likely rectangle/square)")
        return {'is_valid': False}

    # Gate 2: Minimum bounding box size (filters single letters)
    if w < CLOUD_MIN_BBOX_PX or h < CLOUD_MIN_BBOX_PX:
_dbg(f"[Cloud] Rejected: bbox too small ({w:.0f}x{h:.0f} < {CLOUD_MIN_BBOX_PX})")
        return {'is_valid': False}

    # Gate 3: Minimum arc length
    diffs_all = np.diff(points, axis=0)
    arc_length = float(np.sum(np.hypot(diffs_all[:, 0], diffs_all[:, 1])))
    if arc_length < CLOUD_MIN_ARC_LENGTH_PX:
_dbg(f"[Cloud] Rejected: arc too short ({arc_length:.1f} < {CLOUD_MIN_ARC_LENGTH_PX})")
        return {'is_valid': False}

    # Gate 4 & 5: Curvature oscillation analysis
    pts = downsample_stroke(points, max_points=100)
    diffs = np.diff(pts, axis=0)
    norms = np.hypot(diffs[:, 0], diffs[:, 1])
    valid_mask = norms > 1e-4
    if np.sum(valid_mask) < 10:
        return {'is_valid': False}

    unit_vectors = diffs[valid_mask] / norms[valid_mask][:, None]
    crosses = unit_vectors[:-1, 0] * unit_vectors[1:, 1] - unit_vectors[:-1, 1] * unit_vectors[1:, 0]
    angle_changes = np.arcsin(np.clip(crosses, -1.0, 1.0))

    curvature_var = float(np.var(angle_changes))
    sign_arr = np.sign(angle_changes)
    sign_changes = int(np.sum(np.diff(sign_arr[sign_arr != 0]) != 0))

_dbg(f"[Cloud] curv_var={curvature_var:.5f} (min {CLOUD_CURVATURE_VAR_THRESHOLD}), "
              f"sign_changes={sign_changes} (min {CLOUD_MIN_SIGN_CHANGES}), "
              f"bbox={w:.0f}x{h:.0f}, arc={arc_length:.0f}")

    if curvature_var >= CLOUD_CURVATURE_VAR_THRESHOLD and sign_changes >= CLOUD_MIN_SIGN_CHANGES:
        return {
            'is_valid': True,
            'bbox': (float(min_xy[0]), float(min_xy[1]), w, h),
            'curvature_var': curvature_var,
            'sign_changes': sign_changes
        }

_dbg(f"[Cloud] Rejected: curv_var or sign_changes below threshold")
    return {'is_valid': False}


def classify_stroke_precheck(points: np.ndarray) -> tuple[bool, dict]:
    """
    Pre-check pure function: rejects micro/short strokes as handwriting before running
    any shape-specific fit. Raises minimum thresholds to prevent single letters from
    triggering shape recognition.
    """
    N = len(points)
    if N < 3:
        return (False, {'reason': 'too_few_points'})

    pts_eval = downsample_stroke(points, max_points=DOWNSAMPLE_MAX_POINTS)
    diffs = np.diff(pts_eval, axis=0)
    segment_lengths = np.hypot(diffs[:, 0], diffs[:, 1])
    total_length = float(np.sum(segment_lengths))
    if total_length < PRECHECK_MIN_ARC_LENGTH_PX:
_dbg(f"[Precheck] HANDWRITING: arc_length={total_length:.1f} < {PRECHECK_MIN_ARC_LENGTH_PX}")
        return (False, {'reason': 'micro_stroke'})

    min_xy = np.min(pts_eval, axis=0)
    max_xy = np.max(pts_eval, axis=0)
    bbox_w = float(max_xy[0] - min_xy[0])
    bbox_h = float(max_xy[1] - min_xy[1])
    bbox_diag = float(np.hypot(bbox_w, bbox_h))
    if bbox_diag < PRECHECK_MIN_BBOX_DIAG_PX:
_dbg(f"[Precheck] HANDWRITING: bbox_diag={bbox_diag:.1f} < {PRECHECK_MIN_BBOX_DIAG_PX}")
        return (False, {'reason': 'micro_bbox'})

    start_end_dist = float(np.hypot(*(pts_eval[-1] - pts_eval[0])))
    directness_ratio = start_end_dist / total_length if total_length > 0 else 0.0

    return (True, {
        'total_length': total_length,
        'bbox_w': bbox_w,
        'bbox_h': bbox_h,
        'bbox_diag': bbox_diag,
        'start_end_dist': start_end_dist,
        'directness_ratio': directness_ratio,
        'pts_eval': pts_eval
    })


def smooth_handwriting(points: np.ndarray,
                       smooth_factor: float = SPLINE_SMOOTH_FACTOR,
                       num_samples: int = 0) -> np.ndarray:
    """
    De-jitters handwriting using SciPy B-spline interpolation (splprep/splev).
    """
    N = len(points)
    if N < 4:
        return points

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
        tck, u = splprep([x, y], s=smooth_factor * M, k=k_degree)

        if num_samples <= 0:
            total_dist = np.sum(dists)
            num_samples = int(max(M, min(300, total_dist / 2.0)))

        u_new = np.linspace(0, 1, num_samples)
        x_smooth, y_smooth = splev(u_new, tck)
        return np.column_stack((x_smooth, y_smooth))
    except Exception:
        return points


def classify_stroke(points: np.ndarray) -> tuple[str, float, dict]:
    """
    Classifies an input stroke across all 7 supported shape types or 'handwriting'.
    Pure function — zero Qt dependencies.
    """
    is_candidate, metrics = classify_stroke_precheck(points)
    if not is_candidate:
        return ('handwriting', 1.0, {})

    pts_eval = metrics['pts_eval']
    start_end_dist = metrics['start_end_dist']
    bbox_diag = metrics['bbox_diag']
    directness_ratio = metrics['directness_ratio']
    bbox_w = metrics['bbox_w']
    bbox_h = metrics['bbox_h']

    is_closed = start_end_dist < max(CLOSED_LOOP_MAX_DIST_PX, bbox_diag * CLOSED_LOOP_RELATIVE_THRES)

    # 1. Circle / Ellipse Check (Closed smooth loops)
    circle_fit = fit_circle_kasa(pts_eval)
    if (circle_fit['is_valid'] and
        circle_fit['relative_error'] < CIRCLE_MAX_RELATIVE_ERROR and
        circle_fit['rmse'] < CIRCLE_MAX_RMSE_PX and
        is_closed):
        
        max_dim = max(bbox_w, bbox_h)
        diff_ratio = abs(bbox_w - bbox_h) / max_dim if max_dim > 0 else 0.0
        
        if diff_ratio <= SQUARE_TOLERANCE_RATIO:
_dbg(f"[Classify] CIRCLE — rmse={circle_fit['rmse']:.2f}, rel_err={circle_fit['relative_error']:.3f}")
            return ('shape', 0.94, {'shape_type': 'circle', 'fit': circle_fit})
        else:
            ellipse_fit = fit_ellipse(pts_eval)
_dbg(f"[Classify] ELLIPSE — rmse={circle_fit['rmse']:.2f}, ratio_diff={diff_ratio:.3f}")
            return ('shape', 0.91, {'shape_type': 'ellipse', 'fit': ellipse_fit})

    # 2. Rectangle / Square Check (4 Corners near 90° — MUST run BEFORE cloud)
    rect_fit = fit_rectangle_and_square(pts_eval)
    if rect_fit['is_valid']:
        shape_type = rect_fit['shape_type']
        if SHAPE_DEBUG:
            corners = detect_corners(pts_eval)
            print(f"[Classify] {shape_type.upper()} — corners_found={len(corners)}, bbox={rect_fit.get('bbox')}", flush=True)
        return ('shape', 0.92, {'shape_type': shape_type, 'fit': rect_fit})

    # 3. Cloud Check (Closed organic bump oscillation)
    cloud_fit = fit_cloud(pts_eval)
    if cloud_fit['is_valid']:
_dbg(f"[Classify] CLOUD — curv_var={cloud_fit['curvature_var']:.5f}, sign_changes={cloud_fit['sign_changes']}")
        return ('shape', 0.90, {'shape_type': 'cloud', 'fit': cloud_fit})

    # 4. Arrow Check (shaft line + endpoint V-flare)
    arrow_fit = fit_arrow(pts_eval)
    if arrow_fit['is_valid']:
_dbg(f"[Classify] ARROW — head_at={arrow_fit['head_at']}, flare_angle={arrow_fit.get('max_flare_angle', '?'):.1f}°")
        return ('shape', 0.95, {'shape_type': 'arrow', 'fit': arrow_fit})

    # 5. Straight Line Check
    line_fit = fit_line(pts_eval)
    if (line_fit['is_valid'] and
        line_fit['rmse'] < LINE_MAX_RMSE_PX and
        line_fit['max_error'] < LINE_MAX_ERROR_PX and
        directness_ratio > LINE_MIN_DIRECTNESS):
_dbg(f"[Classify] LINE — rmse={line_fit['rmse']:.2f}, directness={directness_ratio:.3f}")
        return ('shape', 0.95, {'shape_type': 'line', 'fit': line_fit})

    if SHAPE_DEBUG:
        corners = detect_corners(pts_eval)
        print(f"[Classify] HANDWRITING — corners={len(corners)}, directness={directness_ratio:.3f}, "
              f"line_rmse={line_fit.get('rmse', '?')}, closed={is_closed}", flush=True)
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
        self.raw_points: list[tuple[float, float, float, float]] = []

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

    def make_handwriting_item(self, pen: QPen, tool_mode: str = "pen"):
        """Builds and returns a smoothed freehand handwriting InkStroke."""
        if not self.raw_points:
            return None

        points_np = np.array([(p[0], p[1]) for p in self.raw_points], dtype=np.float64)

        smoothed_pts = smooth_handwriting(points_np, smooth_factor=SPLINE_SMOOTH_FACTOR) \
            if self.enable_smoothing and len(points_np) >= 4 else points_np

        path = QPainterPath()
        if len(smoothed_pts) > 0:
            path.moveTo(QPointF(float(smoothed_pts[0][0]), float(smoothed_pts[0][1])))
            for pt in smoothed_pts[1:]:
                path.lineTo(QPointF(float(pt[0]), float(pt[1])))

        from .items.ink_stroke import InkStroke
        item = InkStroke(path=path, tool_mode=tool_mode, color=pen.color().name(), width=pen.widthF())
        item.setPen(pen)
        item.raw_stroke = self.raw_points
        item.processed_stroke = [tuple(pt) for pt in smoothed_pts]
        item.stroke_type = "handwriting"
        item.classification_confidence = 1.0
        return item

    def process_stroke(self,
                       color: QColor = QColor("#1c1c1e"),
                       width: float = 3.0,
                       tool_mode: str = "pen"):
        """
        Called on pen RELEASE (non-hold path only).
        Always produces a handwriting item — shape snapping only happens via
        _on_hold_snap_timeout in the canvas, never on release.
        """
        if not self.raw_points:
            return None

        pressures = [p[2] for p in self.raw_points]
        avg_pressure = float(np.mean(pressures)) if pressures else 1.0

        pen = QPen(QColor(color), width * max(0.4, avg_pressure))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        if tool_mode == "highlighter":
            highlight_color = QColor(color)
            highlight_color.setAlpha(100)
            pen.setColor(highlight_color)
            pen.setWidthF(18.0)

        return self.make_handwriting_item(pen, tool_mode=tool_mode)

    def classify_and_snap(self,
                          color: QColor = QColor("#1c1c1e"),
                          width: float = 3.0,
                          tool_mode: str = "pen"):
        """
        Called ONLY from the hold-timer timeout. Runs shape classification and
        returns either a SmartShapeItem (if shape detected) or a handwriting item.
        """
        if not self.raw_points:
            return None

        points_np = np.array([(p[0], p[1]) for p in self.raw_points], dtype=np.float64)
        pressures = [p[2] for p in self.raw_points]
        avg_pressure = float(np.mean(pressures)) if pressures else 1.0

        pen = QPen(QColor(color), width * max(0.4, avg_pressure))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        classification, confidence, details = classify_stroke(points_np)

        if SHAPE_DEBUG:
            print(f"[HoldSnap] classify_stroke → {classification!r} (conf={confidence:.2f}) details={list(details.keys())}")

        if self.enable_smart_shapes and classification == 'shape':
            shape_type = details.get('shape_type')
            fit = details.get('fit', {})

            from .items.smart_shape_item import SmartShapeItem
            item = SmartShapeItem(
                shape_type=shape_type,
                fit_data=fit,
                pen=pen,
                raw_stroke=self.raw_points
            )
            item.classification_confidence = confidence
            return item

        return self.make_handwriting_item(pen, tool_mode=tool_mode)
