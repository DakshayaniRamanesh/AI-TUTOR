import os

def fix_test_phase2a():
    filepath = 'tests/recognition/test_phase2a.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix test_vision_recognizer_success
    content = content.replace(
        'import json\n    mock_resp = json.dumps({"content_type": "EQUATION", "latex": "2x = 4", "confidence": 0.99, "plain_text": "2x = 4"})\n    client = MockProviderClient(response={"text": mock_resp})',
        'client = MockProviderClient(response={"text": "2x = 4", "content_type": "EQUATION", "confidence": 0.99})'
    )
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def fix_test_ocr_consolidation():
    filepath = 'tests/recognition/test_ocr_consolidation.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix test_empty_recognition_returns_failure missing fields
    content = content.replace(
        'request_id="test",\n        status="SUCCESS",\n        provider_name="groq",\n        plain_text="   ",\n        source_stroke_ids=["s1"]',
        'request_id="test",\n        board_id="b1",\n        group_id="g1",\n        group_revision=1,\n        status="SUCCESS",\n        provider_name="groq",\n        plain_text="   ",\n        source_stroke_ids=["s1"]'
    )
    
    # Fix test_valid_recognition_returns_success missing fields
    content = content.replace(
        'request_id="test",\n        status="SUCCESS",\n        provider_name="groq",\n        plain_text="x = 2",\n        source_stroke_ids=["s1"]',
        'request_id="test",\n        board_id="b1",\n        group_id="g1",\n        group_revision=1,\n        status="SUCCESS",\n        provider_name="groq",\n        plain_text="x = 2",\n        source_stroke_ids=["s1"]'
    )

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

fix_test_phase2a()
fix_test_ocr_consolidation()
