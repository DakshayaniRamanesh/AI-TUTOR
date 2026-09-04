import ast
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from backend.video_generation.models import BoardSelection, SceneSpec, VideoJob
from backend.video_generation.agents.board_understanding_agent import BoardUnderstandingAgent
from backend.video_generation.agents.scene_compile_agent import SceneCompileAgent


def test_board_selection_builds_board_ir_from_native_items():
    selection = BoardSelection(
        selected_items=[
            {
                "item_id": "shape_1",
                "type": "SmartShapeItem",
                "stroke_type": "arrow",
                "x": 10,
                "y": 20,
                "dimensions_px": {"length": 100},
            },
            {
                "item_id": "text_1",
                "type": "TextBoxItem",
                "text": "v = u + at",
                "x": 50,
                "y": 50,
            },
        ],
        user_instruction="Explain why acceleration changes velocity.",
    )
    job = VideoJob(job_id="j1", user_prompt=selection.user_instruction, board_selection=selection)
    out = BoardUnderstandingAgent().run(job)
    assert out.board_ir is not None
    assert "v = u + at" in out.board_ir.equations
    assert "shape_1" in out.board_ir.selected_element_ids
    assert "text_1" in out.board_ir.selected_element_ids


def test_scene_spec_compiles_to_main_scene_without_llm_python():
    job = VideoJob(job_id="j2", user_prompt="divergence")
    job.scene_specs = [
        SceneSpec(
            scene_id="scene_1",
            title="Divergence",
            objects=[
                {"id": "field", "type": "vector_field", "pattern": "radial_outward", "position": "center"},
                {"id": "label", "type": "equation", "text": "div F > 0", "position": "bottom"},
            ],
            actions=[
                {"type": "create", "target": "field"},
                {"type": "write", "target": "label"},
            ],
        )
    ]
    out = SceneCompileAgent().run(job)
    assert "class MainScene(Scene):" in out.manim_code
    assert "vector_field" not in out.manim_code
    assert "div F > 0" in out.manim_code
    assert "MathTex" not in out.manim_code
    ast.parse(out.manim_code)
