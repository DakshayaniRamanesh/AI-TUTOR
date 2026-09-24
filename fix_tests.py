import os
import glob

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix test_recognition_contracts.py and test_ocr_consolidation.py
    if 'RecognitionResult(' in content:
        content = content.replace(
            'request_id="test",\n            status=', 
            'request_id="test",\n            board_id="b1",\n            group_id="g1",\n            group_revision=1,\n            status='
        )
        content = content.replace(
            'request_id="req_123",\n        status=', 
            'request_id="req_123",\n        board_id="b1",\n        group_id="g1",\n        group_revision=1,\n        status='
        )
        content = content.replace(
            'request_id="req_2",\n        status=', 
            'request_id="req_2",\n        board_id="b1",\n        group_id="g1",\n        group_revision=1,\n        source_stroke_ids=["s1"],\n        status='
        )

    # Fix test_ocr_consolidation.py: test_canvas_scene_exactly_once_submission
    # scene.trigger_ai_on_dirty_ink() is returning False. 
    # Why? CanvasScene has a notebook_id check now, or because it has no group?
    # Let's fix test_canvas_scene_exactly_once_submission by adding notebook_id
    if 'scene = CanvasScene()' in content:
        content = content.replace('scene = CanvasScene()', 'scene = CanvasScene()\n    scene.set_notebook_id("test_notebook")\n    scene.board_id = "test_board"')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for root, _, files in os.walk('tests'):
    for file in files:
        if file.endswith('.py'):
            fix_file(os.path.join(root, file))

print("Fixed tests!")
