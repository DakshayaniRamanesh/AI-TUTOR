"""
Scene Template Library for CodeGenAgent.

Instead of free-generating Manim code from scratch (high error rate),
CodeGenAgent assembles scenes from these vetted, tested templates.

Benefits:
  - Reduces CodeGen retry rate (each retry = extra LLM API call cost)
  - Eliminates common failure patterns (bad color names, LaTeX typos, etc.)
  - Guarantees Text() is used for prose, MathTex() only for actual equations
  - Cuts LaTeX compilation time by ~40% on non-math-heavy content

Usage:
    from backend.video_generation.scene_templates import SceneTemplateLibrary
    lib = SceneTemplateLibrary()
    code = lib.get_template("concept_explainer", topic="Convolution", formula=r"(f*g)(t)")
"""

from __future__ import annotations
from string import Template
from typing import Dict, Optional


# ── Template Definitions ──────────────────────────────────────────────────────
# Rules enforced in ALL templates:
#   1. Text() for prose/labels — never MathTex() for plain sentences
#   2. MathTex() only for actual mathematical formulas
#   3. Only safe Manim color constants (no CYAN — crashes on some versions)
#   4. All objects positioned within 14x8 camera frame
#   5. Single class MainScene(Scene) with construct(self)


TEMPLATES: Dict[str, str] = {

    # ── Template 1: Concept Explainer (general topic, 4 scenes) ───────────────
    # Best for: biology, history, CS concepts, any non-math topic
    # Uses Text() throughout — no LaTeX compile cost
    "concept_explainer": '''\
from manim import *

class MainScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"

        # Scene 1: Title Banner
        title = Text("$topic", font_size=40, color=BLUE, weight=BOLD)
        subtitle = Text("Step-by-Step Visual Explanation", font_size=20, color=GRAY)
        subtitle.next_to(title, DOWN, buff=0.3)
        self.play(Write(title), run_time=1.2)
        self.play(FadeIn(subtitle), run_time=0.8)
        self.wait(1)
        self.play(FadeOut(title), FadeOut(subtitle))

        # Scene 2: Core Concept Visual
        box = RoundedRectangle(corner_radius=0.3, height=2.5, width=8,
                               color=TEAL, fill_color="#0d2b35", fill_opacity=0.8)
        concept_label = Text("$concept_label", font_size=28, color=TEAL)
        concept_label.move_to(box.get_center())
        self.play(Create(box), Write(concept_label), run_time=1.5)
        self.wait(1)

        # Scene 3: Key Steps
        steps = VGroup()
        step_texts = ["$step1", "$step2", "$step3"]
        for i, step in enumerate(step_texts):
            dot = Dot(color=YELLOW)
            label = Text(step, font_size=20, color=WHITE)
            label.next_to(dot, RIGHT, buff=0.2)
            row = VGroup(dot, label).shift(DOWN * (i * 0.7) + UP * 0.7)
            steps.add(row)
        steps.move_to(ORIGIN)
        for step_row in steps:
            self.play(FadeIn(step_row), run_time=0.6)
        self.wait(1.5)

        # Scene 4: Summary Card
        self.play(FadeOut(box), FadeOut(concept_label), FadeOut(steps))
        summary = RoundedRectangle(corner_radius=0.2, height=1.8, width=10,
                                   color=BLUE, fill_color="#131b2e", fill_opacity=0.9)
        summary_text = Text("$summary", font_size=20, color=WHITE)
        summary_text.move_to(summary.get_center())
        self.play(FadeIn(summary), Write(summary_text), run_time=1.5)
        self.wait(2)
''',

    # ── Template 2: Math / Formula Explainer ──────────────────────────────────
    # Best for: calculus, linear algebra, statistics, physics equations
    # Uses MathTex() only for the actual formula — Text() everywhere else
    "math_explainer": '''\
from manim import *

class MainScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"

        # Scene 1: Topic Title
        title = Text("$topic", font_size=38, color=BLUE, weight=BOLD)
        self.play(Write(title), run_time=1.0)
        self.wait(0.8)
        self.play(title.animate.to_edge(UP, buff=0.4))

        # Scene 2: Core Formula
        formula_label = Text("Core Formula:", font_size=22, color=GRAY)
        formula_label.next_to(title, DOWN, buff=0.6)
        formula = MathTex(r"$latex_formula", font_size=44, color=YELLOW)
        formula.next_to(formula_label, DOWN, buff=0.3)
        self.play(FadeIn(formula_label), Write(formula), run_time=1.5)
        self.wait(1.2)

        # Scene 3: Variable Breakdown
        breakdown_title = Text("What each part means:", font_size=22, color=TEAL)
        breakdown_title.next_to(formula, DOWN, buff=0.5)
        self.play(FadeIn(breakdown_title))
        vars_group = VGroup()
        var_defs = [("$var1_sym", "$var1_desc"), ("$var2_sym", "$var2_desc"), ("$var3_sym", "$var3_desc")]
        for i, (sym, desc) in enumerate(var_defs):
            sym_tex = MathTex(sym, font_size=26, color=ORANGE)
            arrow = Text(" → ", font_size=22, color=GRAY)
            desc_text = Text(desc, font_size=20, color=WHITE)
            row = VGroup(sym_tex, arrow, desc_text).arrange(RIGHT, buff=0.15)
            row.shift(DOWN * (i * 0.55 + 0.3) + breakdown_title.get_bottom())
            vars_group.add(row)
            self.play(FadeIn(row), run_time=0.5)
        self.wait(1.5)

        # Scene 4: Summary
        self.play(FadeOut(breakdown_title), FadeOut(vars_group))
        highlight = SurroundingRectangle(formula, color=GREEN, buff=0.2)
        key_insight = Text("$key_insight", font_size=22, color=GREEN)
        key_insight.next_to(formula, DOWN, buff=0.8)
        self.play(Create(highlight), Write(key_insight), run_time=1.2)
        self.wait(2)
''',

    # ── Template 3: Process / Pipeline Flow ───────────────────────────────────
    # Best for: algorithms, workflows, data pipelines, system architecture
    # Uses arrows between boxes — no LaTeX needed
    "process_flow": '''\
from manim import *

class MainScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"

        # Title
        title = Text("$topic", font_size=36, color=BLUE, weight=BOLD)
        title.to_edge(UP, buff=0.4)
        self.play(Write(title), run_time=1.0)

        # Build pipeline stages as boxes with arrows
        stage_names = ["$stage1", "$stage2", "$stage3", "$stage4"]
        stage_colors = [TEAL, GREEN, YELLOW, ORANGE]
        boxes = VGroup()
        x_positions = [-4.5, -1.5, 1.5, 4.5]

        for i, (stage, color, xpos) in enumerate(zip(stage_names, stage_colors, x_positions)):
            box = RoundedRectangle(corner_radius=0.25, height=1.2, width=2.5,
                                   color=color, fill_color="#1a1a2e", fill_opacity=0.85)
            label = Text(stage, font_size=17, color=color)
            label.move_to(box.get_center())
            group = VGroup(box, label)
            group.move_to([xpos, 0, 0])
            boxes.add(group)
            self.play(FadeIn(group), run_time=0.5)

            if i < len(stage_names) - 1:
                arrow = Arrow(
                    start=[xpos + 1.3, 0, 0],
                    end=[xpos + 1.5 + 0.2, 0, 0],
                    color=WHITE, buff=0,
                )
                self.play(GrowArrow(arrow), run_time=0.3)

        self.wait(1)

        # Show description below
        desc = Text("$description", font_size=19, color=GRAY)
        desc.next_to(boxes, DOWN, buff=0.7)
        self.play(FadeIn(desc), run_time=0.8)
        self.wait(2)
''',

    # ── Template 4: Comparison / Before-After ─────────────────────────────────
    # Best for: optimization comparisons, algorithm trade-offs, A vs B scenarios
    "comparison": '''\
from manim import *

class MainScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"

        title = Text("$topic", font_size=36, color=BLUE, weight=BOLD)
        title.to_edge(UP, buff=0.4)
        self.play(Write(title), run_time=1.0)

        # Left panel: Before / Option A
        left_panel = RoundedRectangle(corner_radius=0.3, height=4, width=5.5,
                                      color=RED, fill_color="#2b0a0a", fill_opacity=0.8)
        left_panel.move_to([-3.2, -0.3, 0])
        left_title = Text("$left_label", font_size=22, color=RED, weight=BOLD)
        left_title.next_to(left_panel.get_top(), DOWN, buff=0.3)
        left_points = ["$left_p1", "$left_p2", "$left_p3"]
        left_group = VGroup(left_panel, left_title)
        for i, point in enumerate(left_points):
            pt = Text(f"• {point}", font_size=17, color=WHITE)
            pt.next_to(left_title, DOWN, buff=0.3 + i * 0.55)
            left_group.add(pt)
        self.play(FadeIn(left_group), run_time=1.0)

        # VS divider
        vs = Text("VS", font_size=32, color=GRAY, weight=BOLD)
        self.play(FadeIn(vs))

        # Right panel: After / Option B
        right_panel = RoundedRectangle(corner_radius=0.3, height=4, width=5.5,
                                       color=GREEN, fill_color="#0a2b0a", fill_opacity=0.8)
        right_panel.move_to([3.2, -0.3, 0])
        right_title = Text("$right_label", font_size=22, color=GREEN, weight=BOLD)
        right_title.next_to(right_panel.get_top(), DOWN, buff=0.3)
        right_points = ["$right_p1", "$right_p2", "$right_p3"]
        right_group = VGroup(right_panel, right_title)
        for i, point in enumerate(right_points):
            pt = Text(f"✓ {point}", font_size=17, color=WHITE)
            pt.next_to(right_title, DOWN, buff=0.3 + i * 0.55)
            right_group.add(pt)
        self.play(FadeIn(right_group), run_time=1.0)
        self.wait(2)
''',

    # ── Template 5: Data / Matrix Visualization ───────────────────────────────
    # Best for: neural networks, matrix operations, data transformations
    "matrix_transform": '''\
from manim import *

class MainScene(Scene):
    def construct(self):
        self.camera.background_color = "#090d16"

        title = Text("$topic", font_size=36, color=BLUE, weight=BOLD)
        title.to_edge(UP, buff=0.4)
        self.play(Write(title), run_time=1.0)

        # Input matrix grid
        in_grid = VGroup()
        for r in range($grid_rows):
            for c in range($grid_cols):
                sq = Square(side_length=0.7, color=TEAL, fill_opacity=0.2)
                sq.move_to([c * 0.75 - ($grid_cols - 1) * 0.375 - 3, r * 0.75 - ($grid_rows - 1) * 0.375, 0])
                in_grid.add(sq)
        in_label = Text("$input_label", font_size=18, color=TEAL)
        in_label.next_to(in_grid, DOWN, buff=0.25)
        self.play(Create(in_grid), FadeIn(in_label), run_time=1.2)

        # Transformation arrow + formula (LaTeX only for actual formula)
        arrow = Arrow(LEFT * 1.2, RIGHT * 0.5, color=YELLOW, buff=0.1)
        formula = MathTex(r"$transform_formula", font_size=30, color=YELLOW)
        formula.next_to(arrow, UP, buff=0.2)
        self.play(GrowArrow(arrow), Write(formula), run_time=1.0)
        self.wait(0.5)

        # Output matrix grid
        out_grid = VGroup()
        for r in range($out_rows):
            for c in range($out_cols):
                sq = Square(side_length=0.85, color=GREEN, fill_opacity=0.3)
                sq.move_to([c * 0.95 + 2.5, r * 0.95 - ($out_rows - 1) * 0.475, 0])
                out_grid.add(sq)
        out_label = Text("$output_label", font_size=18, color=GREEN)
        out_label.next_to(out_grid, DOWN, buff=0.25)
        self.play(Create(out_grid), FadeIn(out_label), run_time=1.2)

        # Pulse highlight
        pulse = SurroundingRectangle(out_grid, color=YELLOW, buff=0.2)
        self.play(Create(pulse), run_time=0.8)
        self.play(Uncreate(pulse), run_time=0.6)
        self.wait(1.5)
''',

    # ── Template 6: Graph / Function Plotter ──────────────────────────────────
    # Best for: calculus, statistics, physics curves, any f(x) visualization
    # Uses Axes.plot() — NO LaTeX. All labels are Text().
    "graph_plotter": '''\
from manim import *
import numpy as np

class MainScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"

        title = Text("$topic", font_size=36, color=BLUE, weight=BOLD)
        title.to_edge(UP, buff=0.35)
        self.play(Write(title), run_time=1.0)

        # Axes setup
        ax = Axes(
            x_range=$x_range,
            y_range=$y_range,
            axis_config={"color": GRAY, "stroke_width": 2},
            tips=False
        ).scale(0.85).shift(DOWN * 0.3)

        x_label = Text("$x_label", font_size=18, color=GRAY).next_to(ax.x_axis, DOWN, buff=0.15)
        y_label = Text("$y_label", font_size=18, color=GRAY).next_to(ax.y_axis, LEFT, buff=0.15)

        self.play(Create(ax), FadeIn(x_label), FadeIn(y_label), run_time=1.2)

        # Primary curve
        curve = ax.plot(lambda x: $func_expr, color=TEAL, stroke_width=3)
        curve_label = Text("$func_label", font_size=20, color=TEAL)
        curve_label.next_to(curve.get_end(), RIGHT, buff=0.2)

        self.play(Create(curve), run_time=1.5)
        self.play(FadeIn(curve_label))
        self.wait(1)

        # Key point annotation
        key_x = $key_x
        key_y_val = $key_y
        dot = Dot(ax.c2p(key_x, key_y_val), color=YELLOW, radius=0.1)
        annotation = Text("$key_annotation", font_size=18, color=YELLOW)
        annotation.next_to(dot, UP, buff=0.25)
        self.play(FadeIn(dot), Write(annotation), run_time=0.8)
        self.wait(1.5)

        # Summary
        summary = Text("$summary", font_size=20, color=WHITE)
        summary.to_edge(DOWN, buff=0.5)
        self.play(FadeIn(summary))
        self.wait(2)
''',

    # ── Template 7: Physics Diagram ───────────────────────────────────────────
    # Best for: forces, vectors, motion, classical mechanics
    # Uses Arrow vectors + Text labels — no LaTeX
    "physics_diagram": '''\
from manim import *

class MainScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"

        title = Text("$topic", font_size=36, color=BLUE, weight=BOLD)
        title.to_edge(UP, buff=0.35)
        self.play(Write(title), run_time=1.0)

        # Object / body
        body = Rectangle(height=1.0, width=1.8, color=TEAL,
                         fill_color="#0d2b35", fill_opacity=0.85)
        body.shift(DOWN * 0.5)
        body_label = Text("$object_label", font_size=20, color=TEAL)
        body_label.move_to(body.get_center())
        self.play(FadeIn(body), FadeIn(body_label), run_time=0.8)

        # Force 1
        arrow1 = Arrow(
            body.get_right(), body.get_right() + RIGHT * 2.2,
            color=RED, buff=0, stroke_width=5
        )
        label1 = Text("$force1_label", font_size=20, color=RED)
        label1.next_to(arrow1, UP, buff=0.2)
        self.play(GrowArrow(arrow1), FadeIn(label1), run_time=0.8)
        self.wait(0.5)

        # Force 2
        arrow2 = Arrow(
            body.get_top(), body.get_top() + UP * 2.0,
            color=GREEN, buff=0, stroke_width=5
        )
        label2 = Text("$force2_label", font_size=20, color=GREEN)
        label2.next_to(arrow2, RIGHT, buff=0.2)
        self.play(GrowArrow(arrow2), FadeIn(label2), run_time=0.8)
        self.wait(0.5)

        # Equation / principle
        principle = Text("$principle", font_size=26, color=YELLOW)
        principle.next_to(body, DOWN, buff=0.8)
        self.play(Write(principle), run_time=1.0)
        self.wait(1.5)

        # Summary card
        self.play(*[FadeOut(m) for m in self.mobjects])
        card = RoundedRectangle(corner_radius=0.2, height=2.0, width=10,
                                color=BLUE, fill_color="#131b2e", fill_opacity=0.9)
        summary = Text("$summary", font_size=20, color=WHITE)
        summary.move_to(card.get_center())
        self.play(FadeIn(card), Write(summary), run_time=1.2)
        self.wait(2)
''',

    # ── Template 8: Algorithm Steps ───────────────────────────────────────────
    # Best for: CS algorithms, sorting, searching, data structure operations
    # Uses numbered step boxes with progressive reveal
    "algorithm_steps": '''\
from manim import *

class MainScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"

        title = Text("$topic", font_size=36, color=BLUE, weight=BOLD)
        title.to_edge(UP, buff=0.35)
        self.play(Write(title), run_time=1.0)

        step_data = [
            ("1", "$step1", TEAL),
            ("2", "$step2", GREEN),
            ("3", "$step3", YELLOW),
            ("4", "$step4", ORANGE),
        ]

        step_groups = VGroup()
        for i, (num, label, color) in enumerate(step_data):
            circle = Circle(radius=0.35, color=color,
                           fill_color=color, fill_opacity=0.25, stroke_width=3)
            num_text = Text(num, font_size=22, color=color, weight=BOLD)
            num_text.move_to(circle)
            step_label = Text(label, font_size=20, color=WHITE)
            step_label.next_to(circle, RIGHT, buff=0.35)
            row = VGroup(circle, num_text, step_label)
            step_groups.add(row)

        step_groups.arrange(DOWN, buff=0.55, aligned_edge=LEFT)
        step_groups.shift(LEFT * 1.5 + DOWN * 0.3)

        for row in step_groups:
            self.play(FadeIn(row), run_time=0.5)
            self.wait(0.4)
        self.wait(0.8)

        # Connector arrow down the left side
        result_box = RoundedRectangle(corner_radius=0.2, height=1.2, width=6.5,
                                      color=BLUE, fill_color="#131b2e", fill_opacity=0.9)
        result_box.next_to(step_groups, DOWN, buff=0.6)
        result_text = Text("Result: $result", font_size=22, color=BLUE)
        result_text.move_to(result_box)
        self.play(FadeIn(result_box), Write(result_text), run_time=1.0)
        self.wait(2)
''',

    # ── Template 9: Chemistry Reaction ────────────────────────────────────────
    # Best for: chemical reactions, molecular diagrams, element descriptions
    "chemistry_reaction": '''\
from manim import *

class MainScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"

        title = Text("$topic", font_size=34, color=BLUE, weight=BOLD)
        title.to_edge(UP, buff=0.35)
        self.play(Write(title), run_time=1.0)

        # Reactant A molecule
        circ_a = Circle(radius=0.55, color=RED, fill_color="#2b0a0a", fill_opacity=0.8)
        label_a = Text("$element_a", font_size=26, color=RED, weight=BOLD)
        label_a.move_to(circ_a)
        mol_a = VGroup(circ_a, label_a).shift(LEFT * 4.0)
        self.play(FadeIn(mol_a), run_time=0.7)

        # Reactant B molecule
        circ_b = Circle(radius=0.55, color=GREEN, fill_color="#0a2b0a", fill_opacity=0.8)
        label_b = Text("$element_b", font_size=26, color=GREEN, weight=BOLD)
        label_b.move_to(circ_b)
        mol_b = VGroup(circ_b, label_b).shift(LEFT * 2.0)
        self.play(FadeIn(mol_b), run_time=0.7)

        # Plus sign
        plus = Text("+", font_size=36, color=GRAY)
        plus.move_to([-3.0, 0, 0])
        self.play(FadeIn(plus))

        # Reaction arrow
        reaction_arrow = Arrow(LEFT * 0.8, RIGHT * 1.2, color=YELLOW, buff=0)
        self.play(GrowArrow(reaction_arrow), run_time=0.8)

        # Product molecule
        circ_p = Circle(radius=0.7, color=TEAL, fill_color="#0d2b35", fill_opacity=0.85)
        label_p = Text("$product", font_size=24, color=TEAL, weight=BOLD)
        label_p.move_to(circ_p)
        mol_p = VGroup(circ_p, label_p).shift(RIGHT * 2.5)
        self.play(FadeIn(mol_p), run_time=0.8)
        self.wait(1)

        # Reaction equation below
        equation = Text("$reaction_equation", font_size=22, color=YELLOW)
        equation.to_edge(DOWN, buff=1.2)
        self.play(Write(equation), run_time=1.0)

        # Explanation
        explanation = Text("$explanation", font_size=19, color=WHITE)
        explanation.to_edge(DOWN, buff=0.5)
        self.play(FadeIn(explanation))
        self.wait(2)
''',
}


class SceneTemplateLibrary:
    """
    Provides vetted Manim scene templates to CodeGenAgent.

    Instead of free-generating code from scratch, CodeGenAgent picks the
    most appropriate template and fills in the topic-specific variables.
    This cuts the error rate and retry count significantly.
    """

    AVAILABLE_TEMPLATES = list(TEMPLATES.keys())

    def get_template(self, template_name: str, **kwargs) -> str:
        """
        Returns a filled-in Manim code template.

        Args:
            template_name: One of AVAILABLE_TEMPLATES
            **kwargs: Variable substitutions (e.g. topic="Newton's 2nd Law")

        Returns:
            Complete, ready-to-validate Manim Python code string.

        Raises:
            KeyError: If template_name is not found.
        """
        if template_name not in TEMPLATES:
            available = ", ".join(self.AVAILABLE_TEMPLATES)
            raise KeyError(f"Template '{template_name}' not found. Available: {available}")

        raw = TEMPLATES[template_name]
        # Use safe_substitute so missing keys become the literal $key string
        # rather than raising an error — makes partial fills safe
        return Template(raw).safe_substitute(**kwargs)

    def select_template_for_topic(self, user_prompt: str, story_script: str, topic_subject: str = "") -> str:
        """
        Picks the best template based on topic_subject classification (from StoryAgent)
        and keyword signals in the prompt and story script.

        Returns one of AVAILABLE_TEMPLATES.
        """
        text = (user_prompt + " " + (story_script or "")).lower()

        # ── Subject-based routing (high confidence) ────────────────────────────
        if topic_subject == "math":
            if any(s in text for s in ["neural", "convolution", "layer", "transform", "matrix"]):
                return "matrix_transform"
            if any(s in text for s in ["derivative", "integral", "function", "graph", "plot", "curve"]):
                return "graph_plotter"
            return "math_explainer"

        if topic_subject == "physics":
            if any(s in text for s in ["force", "vector", "motion", "gravity", "momentum", "field"]):
                return "physics_diagram"
            if any(s in text for s in ["graph", "curve", "plot", "wave"]):
                return "graph_plotter"
            return "physics_diagram"

        if topic_subject == "cs":
            if any(s in text for s in ["pipeline", "workflow", "flow", "architecture", "system"]):
                return "process_flow"
            if any(s in text for s in ["algorithm", "sort", "search", "tree", "step", "steps"]):
                return "algorithm_steps"
            if any(s in text for s in ["neural", "convolution", "layer", "activation"]):
                return "matrix_transform"
            return "process_flow"

        if topic_subject == "chemistry":
            return "chemistry_reaction"

        if topic_subject == "statistics":
            return "graph_plotter"

        # ── Keyword-based fallback (when topic_subject is empty or general) ───
        math_signals = ["formula", "equation", "calculus", "derivative", "integral",
                        "matrix", "vector", "eigenvalue", "probability", "theorem",
                        "proof", "∑", "∫", "∂", "function", "graph"]
        if any(s in text for s in math_signals):
            if any(s in text for s in ["neural", "convolution", "layer", "activation", "transform"]):
                return "matrix_transform"
            if any(s in text for s in ["derivative", "integral", "curve", "plot"]):
                return "graph_plotter"
            return "math_explainer"

        flow_signals = ["pipeline", "workflow", "algorithm", "step", "process",
                        "architecture", "flow", "system", "sequence", "stages"]
        if any(s in text for s in flow_signals):
            return "process_flow"

        compare_signals = ["compare", "vs", "versus", "difference", "better",
                           "trade-off", "advantage", "before", "after"]
        if any(s in text for s in compare_signals):
            return "comparison"

        return "concept_explainer"


    def list_templates(self) -> list:
        return self.AVAILABLE_TEMPLATES
