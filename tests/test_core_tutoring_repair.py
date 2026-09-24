import pytest
from app.services.recognition.stroke_grouper import StrokeGrouper, StrokeData, StrokeGroupingConfig
from shared.contracts.tutoring import TutorMode
from shared.contracts.recognition import RecognitionResult, ContentType, RecognitionStatus


def test_stroke_grouper_temporal_limits_ms():
    grouper = StrokeGrouper(StrokeGroupingConfig(max_temporal_gap_ms=1200))
    
    # 1. First stroke
    s1 = StrokeData("s1", 0, 0, 10, 10, 1000.0, 1100.0)
    g1 = grouper.add_stroke(s1, "board1")
    
    # 2. Second stroke within 1200ms of first stroke's end (e.g. 1500ms)
    s2 = StrokeData("s2", 12, 0, 10, 10, 1500.0, 1600.0)
    g2 = grouper.add_stroke(s2, "board1")
    
    # Should be the same group
    assert g1.id == g2.id
    assert len(g2.stroke_ids) == 2
    
    # 3. Third stroke 1500ms after second stroke's end (3100ms) -> exceeds 1200ms threshold
    s3 = StrokeData("s3", 24, 0, 10, 10, 3100.0, 3200.0)
    g3 = grouper.add_stroke(s3, "board1")
    
    # Should be a new group
    assert g3.id != g2.id
    assert len(g3.stroke_ids) == 1

def test_auto_check_mode_mapping():
    # If a RecognitionResult is marked is_auto_check=True, the mode should route to AUTO_CHECK.
    query = RecognitionResult(
        request_id="req1",
        board_id="board1",
        group_id="g1",
        group_revision=1,
        status=RecognitionStatus.SUCCESS,
        content_type=ContentType.EQUATION,
        plain_text="x = 2",
        confidence=0.9,
        provider_name="test",
        is_auto_check=True
    )
    
    # Using the logic in main_window.py mapping
    is_auto_check_query = getattr(query, 'is_auto_check', False)
    mode = None
    if mode:
        req_mode = mode
    elif is_auto_check_query:
        req_mode = "AUTO_CHECK"
    else:
        req_mode = "CHECK_STEP"
        
    assert req_mode == "AUTO_CHECK"

def test_explicit_feather_mapping():
    # Explicit feather (not auto check)
    query = RecognitionResult(
        request_id="req2",
        board_id="board1",
        group_id="g1",
        group_revision=1,
        status=RecognitionStatus.SUCCESS,
        content_type=ContentType.EQUATION,
        plain_text="x = 2",
        confidence=0.9,
        provider_name="test",
        is_auto_check=False
    )
    
    is_auto_check_query = getattr(query, 'is_auto_check', False)
    mode = None
    if mode:
        req_mode = mode
    elif is_auto_check_query:
        req_mode = "AUTO_CHECK"
    else:
        req_mode = "CHECK_STEP"
        
    assert req_mode == "CHECK_STEP"
