import pytest
from app.services.recognition.stroke_grouper import StrokeGrouper, StrokeGroupingConfig, StrokeData
from shared.contracts.common import CoordinateSpace

def create_stroke(id: str, x: float, y: float, w: float, h: float, start_ts: float, end_ts: float) -> StrokeData:
    return StrokeData(id, x, y, w, h, start_ts, end_ts)

def test_stroke_grouper_temporal_proximity():
    config = StrokeGroupingConfig(max_temporal_gap_ms=1200)
    grouper = StrokeGrouper(config)

    # Stroke 1: 0ms to 100ms
    s1 = create_stroke("s1", 0, 0, 10, 10, 0, 100)
    g1 = grouper.add_stroke(s1, "board1")
    
    # Stroke 2: 500ms to 600ms (gap 400ms <= 1200ms)
    s2 = create_stroke("s2", 15, 0, 10, 10, 500, 600)
    g2 = grouper.add_stroke(s2, "board1")
    
    assert g1.id == g2.id
    assert g2.revision == 1
    assert len(g2.stroke_ids) == 2
    
    # Stroke 3: 2000ms to 2100ms (gap 1400ms > 1200ms)
    s3 = create_stroke("s3", 30, 0, 10, 10, 2000, 2100)
    g3 = grouper.add_stroke(s3, "board1")
    
    assert g3.id != g2.id
    assert g3.revision == 0
    assert len(g3.stroke_ids) == 1

def test_stroke_grouper_spatial_tolerance():
    config = StrokeGroupingConfig(max_temporal_gap_ms=1200, vertical_baseline_tolerance_px=40.0)
    grouper = StrokeGrouper(config)

    # Stroke 1
    s1 = create_stroke("s1", 0, 0, 10, 10, 0, 0.1)
    g1 = grouper.add_stroke(s1, "board1")
    
    # Stroke 2: Very fast but on a new line (y=100) -> gap is 100 > 2*40
    s2 = create_stroke("s2", 0, 100, 10, 10, 0.2, 0.3)
    g2 = grouper.add_stroke(s2, "board1")
    
    assert g1.id != g2.id

def test_explicit_grouping():
    grouper = StrokeGrouper()
    s1 = create_stroke("s1", 0, 0, 10, 10, 0, 0.1)
    s2 = create_stroke("s2", 15, 0, 10, 10, 0.5, 0.6)
    
    group = grouper.create_explicit_group([s1, s2], "board1")
    assert group.revision == 1
    assert len(group.stroke_ids) == 2
    assert group.bbox.width == 25
    assert grouper.active_group_id == group.id
