import ast

from backend.video_generation.agents.scene_compile_agent import SceneCompileAgent
from backend.video_generation.agents.storyboard_agent import StoryboardPlannerAgent
from backend.video_generation.models import SceneSpec


def test_multiple_scene_specs_compile_to_one_main_scene():
    scenes = [
        SceneSpec(
            scene_id="one",
            objects=[{"id": "a", "type": "text", "text": "First"}],
            actions=[{"type": "write", "target": "a"}],
        ),
        SceneSpec(
            scene_id="two",
            objects=[{"id": "b", "type": "text", "text": "Second"}],
            actions=[{"type": "write", "target": "b"}],
        ),
    ]
    code = SceneCompileAgent().compile(scenes)
    ast.parse(code)
    assert code.count("class MainScene(Scene):") == 1
    assert "class Scene_" not in code
    assert "First" in code and "Second" in code


def test_storyboard_keeps_targetless_teaching_actions_and_nested_terms():
    raw = [
        {
            "scene_id": "s1",
            "objects": [
                {
                    "id": "eq",
                    "type": "term_equation",
                    "terms": [
                        {"id": "t1", "value": "x^2"},
                        {"id": "t2", "value": "+2x"},
                    ],
                }
            ],
            "actions": [
                {"type": "AskQuestion", "question": "Why?"},
                {"type": "RevealRule", "rule": "a^2+2ab+b^2=(a+b)^2"},
                {"type": "HighlightTerm", "target": "t1"},
                {"type": "MapTerms", "source": "t1", "target": "t2"},
            ],
        }
    ]
    scenes = StoryboardPlannerAgent()._normalize_scenes(raw)
    action_types = [a["type"] for a in scenes[0].actions]
    assert "AskQuestion" in action_types
    assert "RevealRule" in action_types
    assert "HighlightTerm" in action_types
    assert "MapTerms" in action_types


def test_storyboard_does_not_invent_transform_reason():
    raw = [
        {
            "scene_id": "s1",
            "objects": [
                {"id": "before", "type": "text", "text": "A"},
                {"id": "after", "type": "text", "text": "B"},
            ],
            "actions": [
                {"type": "transform", "target": "before", "to": "after"}
            ],
        }
    ]
    scenes = StoryboardPlannerAgent()._normalize_scenes(raw)
    assert all(a.get("type") != "transform" for a in scenes[0].actions)
