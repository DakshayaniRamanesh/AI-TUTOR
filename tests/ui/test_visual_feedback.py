import pytest
import sys
import os
from PyQt6.QtWidgets import QApplication, QGraphicsScene
from PyQt6.QtCore import QPointF
from unittest.mock import MagicMock, patch

from app.ui.canvas_scene import CanvasScene
from shared.contracts.tutoring import TutorFeedback
from shared.contracts.reasoning import CanvasAnchor
from app.ui.widgets.socratic_hint_bubble import SocraticHintBubble
from app.ui.items.ghost_chalk_item import GhostChalkItem

app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

def test_present_tutor_feedback_creates_visual_items():
    scene = CanvasScene()
    
    feedback = TutorFeedback(
        feedback_text="This is correct!",
        socratic_hints=["Did you carry the 1?"],
        anchors=[
            CanvasAnchor(item_ids=["stroke1"], board_id="test_board")
        ]
    )
    
    scene.present_tutor_feedback(feedback, QPointF(200, 200), ["stroke1", "stroke2"])
    
    items = scene.items()
    
    has_hint = False
    has_chalk = False
    
    for item in items:
        if hasattr(item, "widget") and callable(item.widget):
            widget = item.widget()
            if isinstance(widget, SocraticHintBubble):
                has_hint = True
        if isinstance(item, GhostChalkItem):
            has_chalk = True
            
    assert has_hint, "SocraticHintBubble was not added to the scene"
    assert has_chalk, "GhostChalkItem was not added to the scene"

def test_architectural_guard_no_work_corrector():
    # Phase 4 restriction: ensure work_corrector is not imported or present
    import sys
    assert "app.services.models.work_corrector" not in sys.modules, "work_corrector was incorrectly imported!"
    assert not os.path.exists("app/services/models/work_corrector.py"), "work_corrector.py should not be in the codebase!"

def test_architectural_guard_no_correction_prompts():
    # Phase 4 restriction: ensure correction_prompts is not imported or present
    import sys
    assert "app.services.prompts.correction_prompts" not in sys.modules, "correction_prompts was incorrectly imported!"
    assert not os.path.exists("app/services/prompts/correction_prompts.py"), "correction_prompts.py should not be in the codebase!"
