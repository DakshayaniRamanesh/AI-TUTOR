import json
import os
import re
from typing import Any, Dict, List

from backend.video_generation.models import SceneSpec, Storyboard, VideoJob


_ALLOWED_OBJECT_TYPES = {
    "text", "equation", "term_equation", "circle", "rectangle", "line", "arrow", "vector",
    "axes", "plot", "matrix", "vector_field", "path", "board_stroke",
}
_ALLOWED_ACTION_TYPES = {
    "create", "write", "fade_in", "fade_out", "highlight", "indicate",
    "translate", "rotate", "scale", "transform",
    "AskQuestion", "RevealRule", "HighlightTerm", "MapTerms", "SubstituteValues"
}


class StoryboardPlannerAgent:
    """Turn a teaching plan into a compact declarative storyboard."""

    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")

    def run(self, job: VideoJob) -> VideoJob:
        job.step = "storyboard_planner"
        job.progress_percentage = 46
        board = job.board_ir
        plan = job.teaching_plan
        if not board or not plan:
            return job

        context = job.metadata.get("teaching_context", {})
        prompt = f"""You are designing the most efficient visual storyboard for a smart-whiteboard tutor.
The output is NOT Python. Use only the declarative scene vocabulary below.
Create at least one scene per TeachingStep to animate the rule and transition. Every scene must teach something; avoid decorative filler.

TEXT RULES:
- SEPARATE NARRATION: 'narration' is spoken aloud. Visible text (e.g., AskQuestion, RevealRule) must be extremely concise. Do not dump the narration onto the screen.

LEARNING OBJECTIVE:
{plan.learning_objective}

TEACHING STEPS:
{json.dumps([s.__dict__ for s in plan.steps], indent=2)}

SELECTED BOARD CONTENT:
{board.extracted_text[:4500]}

VISIBLE EQUATIONS:
{json.dumps(board.equations[:8])}

TEXTBOOK CONTEXT:
{str(context.get('rag_context', ''))[:3500]}

Allowed object types:
{sorted(_ALLOWED_OBJECT_TYPES)}
Allowed action types:
{sorted(_ALLOWED_ACTION_TYPES)}
* For transform actions, you MUST include a 'reason' field explaining why the transformation is valid.

For vector_field, pattern must be one of: radial_outward, radial_inward, rotational, uniform.
For plot, curve must be one of: parabola, sine, cosine, linear.
Positions should be one of: center, top, bottom, left, right, upper_left, upper_right, lower_left, lower_right.
Use `term_equation` to break equations into terms for mapping or substitution: `{{"type": "term_equation", "terms": [{{"id":"t1","value":"x^2"}}, {{"id":"t2","value":"+2x"}}]}}`
Use `layout` to hint at screen arrangement (e.g. "equation_with_rule_below", "side_by_side", "default").

Return ONLY JSON in this exact structure:
{{
  "title": "lesson title",
  "rationale": "why this is the shortest clear visual sequence",
  "scenes": [
    {{
      "scene_id": "scene_1",
      "title": "short title",
      "learning_goal": "what becomes clear in this scene",
      "duration_seconds": 8,
      "layout": "equation_with_rule_below",
      "objects": [
        {{"id":"eq1","type":"term_equation","terms":[{{"id":"t1","value":"x^2"}}],"position":"top"}}
      ],
      "actions": [
        {{"type":"write","target":"eq1"}},
        {{"type":"AskQuestion","question":"Why is this a perfect square?"}},
        {{"type":"RevealRule","rule":"a^2 + 2ab + b^2"}},
        {{"type":"MapTerms","source":"eq1","target":"t1"}}
      ],
      "narration": "brief narration"
    }}
  ]
}}
"""

        data = self._generate_json(prompt)
        scenes = self._normalize_scenes(data.get("scenes", []) if data else [])
        if not scenes:
            scenes = self._fallback_scenes(job)
            data = {"title": board.probable_topic, "rationale": "Deterministic fallback storyboard."}

        job.scene_specs = scenes
        job.storyboard = Storyboard(
            title=str(data.get("title", board.probable_topic))[:200],
            scenes=scenes,
            rationale=str(data.get("rationale", ""))[:1000],
        )
        # Preserve a readable legacy story_script for free-generation fallback and status UI.
        job.story_script = self._as_script(job.storyboard)
        return job

    def _normalize_scenes(self, raw_scenes: Any) -> List[SceneSpec]:
        if not isinstance(raw_scenes, list):
            return []
        out: List[SceneSpec] = []
        for idx, raw in enumerate(raw_scenes[:5]):
            if not isinstance(raw, dict):
                continue
            objects = []
            seen_ids = set()
            for obj_idx, obj in enumerate(raw.get("objects", [])[:20]):
                if not isinstance(obj, dict):
                    continue
                obj_type = str(obj.get("type", "text"))
                if obj_type not in _ALLOWED_OBJECT_TYPES:
                    obj_type = "text"
                oid = re.sub(r"[^A-Za-z0-9_]", "_", str(obj.get("id") or f"obj_{obj_idx}"))[:50]
                if not oid or oid[0].isdigit():
                    oid = f"obj_{oid}"
                if oid in seen_ids:
                    oid = f"{oid}_{obj_idx}"
                seen_ids.add(oid)
                clean = dict(obj)
                clean["id"] = oid
                clean["type"] = obj_type
                clean["position"] = str(obj.get("position", "center"))
                if obj_type == "vector_field":
                    pattern = str(obj.get("pattern", "uniform"))
                    clean["pattern"] = pattern if pattern in {"radial_outward", "radial_inward", "rotational", "uniform"} else "uniform"
                if obj_type == "plot":
                    curve = str(obj.get("curve", "parabola"))
                    clean["curve"] = curve if curve in {"parabola", "sine", "cosine", "linear"} else "parabola"
                if obj_type == "term_equation":
                    clean["terms"] = obj.get("terms", [])
                
                objects.append(clean)

            valid_targets = {o["id"] for o in objects}
            actions = []
            for action in raw.get("actions", [])[:30]:
                if not isinstance(action, dict):
                    continue
                atype = str(action.get("type", "create"))
                target = str(action.get("target", ""))
                if atype in _ALLOWED_ACTION_TYPES and target in valid_targets:
                    clean_action = dict(action)
                    clean_action["type"] = atype
                    clean_action["target"] = target
                    reason = action.get("reason")
                    if atype == "transform" and not reason:
                        clean_action["reason"] = "Direct transition"
                    if atype in {"transform", "MapTerms", "SubstituteValues"}:
                        clean_action["source"] = str(action.get("source", target))
                        clean_action["to"] = str(action.get("to", ""))
                    if atype == "AskQuestion":
                        clean_action["question"] = str(action.get("question", ""))
                    if atype == "RevealRule":
                        clean_action["rule"] = str(action.get("rule", ""))

                    actions.append(clean_action)

            if not objects:
                continue
            try:
                duration = max(4.0, min(20.0, float(raw.get("duration_seconds", 8))))
            except Exception:
                duration = 8.0
            out.append(SceneSpec(
                scene_id=str(raw.get("scene_id") or f"scene_{idx+1}"),
                title=str(raw.get("title", ""))[:160],
                learning_goal=str(raw.get("learning_goal", ""))[:500],
                duration_seconds=duration,
                layout=str(raw.get("layout", "default")),
                objects=objects,
                actions=actions,
                narration=str(raw.get("narration", ""))[:1200],
            ))
        return out

    def _fallback_scenes(self, job: VideoJob) -> List[SceneSpec]:
        topic = job.board_ir.probable_topic if job.board_ir else "the selected concept"
        return [
            SceneSpec(
                scene_id="fallback_1",
                title="Introduction",
                learning_goal=f"Introduce {topic}",
                duration_seconds=5.0,
                objects=[
                    {"id": "t1", "type": "text", "text": f"Let's explore {topic}.", "position": "center", "color": "WHITE"}
                ],
                actions=[
                    {"type": "write", "target": "t1"}
                ],
                narration=f"Let's break down {topic} step by step."
            )
        ]

    def _generate_json(self, prompt: str) -> Dict[str, Any]:
        text = ""
        # Groq first — fastest for structured JSON output (0.2s vs 2-3s for Gemini)
        if self.groq_api_key:
            try:
                from groq import Groq
                response = Groq(api_key=self.groq_api_key).chat.completions.create(
                    model="qwen/qwen3.8-27b",
                    messages=[{"role": "user", "content": prompt}],
                    timeout=30.0,
                )
                text = response.choices[0].message.content or ""
                if text:
                    print("[StoryboardPlannerAgent] Groq JSON generation succeeded")
            except Exception as exc:
                print(f"[StoryboardPlannerAgent] Groq error: {exc}")

        # Gemini fallback
        if not text and self.google_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.google_api_key)
                response = genai.GenerativeModel("gemini-3.5-flash-lite").generate_content(prompt)
                text = response.text if response else ""
                if text:
                    print("[StoryboardPlannerAgent] Gemini JSON generation succeeded")
            except Exception as exc:
                print(f"[StoryboardPlannerAgent] Gemini error: {exc}")

        if not text:
            return {}
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _as_script(storyboard: Storyboard) -> str:
        lines = [f"# {storyboard.title}"]
        for idx, scene in enumerate(storyboard.scenes, start=1):
            lines.append(f"\n## Scene {idx}: {scene.title}")
            if scene.learning_goal:
                lines.append(f"Goal: {scene.learning_goal}")
            for obj in scene.objects:
                desc = obj.get("text") or obj.get("type")
                lines.append(f"- Visual: {desc}")
            if scene.narration:
                lines.append(f"Narration: {scene.narration}")
        return "\n".join(lines)
