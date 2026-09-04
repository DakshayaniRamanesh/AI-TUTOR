import base64
import os
import re
from typing import Any, Dict, Iterable, List

from backend.video_generation.models import (
    BoardElement,
    BoardIR,
    BoardSelection,
    VideoJob,
)


_TEXT_KEYS = {
    "text", "title", "question", "raw_text", "caption", "label",
    "full_text", "content", "formula", "latex", "description",
}


class BoardUnderstandingAgent:
    """Convert a structured canvas selection into a normalized BoardIR."""

    def run(self, job: VideoJob) -> VideoJob:
        job.step = "board_understanding"
        job.progress_percentage = 22

        selection = job.board_selection
        if isinstance(selection, dict):
            selection = BoardSelection.from_dict(selection)
            job.board_selection = selection

        if not selection or not selection.has_content():
            job.board_ir = BoardIR(
                probable_topic=job.user_prompt,
                learning_intent=job.user_prompt,
                extracted_text=job.user_prompt,
                ambiguities=["No structured whiteboard selection was provided."],
            )
            return job

        elements: List[BoardElement] = []
        selected_ids: List[str] = []
        supporting_ids: List[str] = []
        extracted_text_parts: List[str] = []
        equations: List[str] = []
        questions: List[str] = []
        concepts: List[str] = []

        for is_selected, items in ((True, selection.selected_items), (False, selection.nearby_items)):
            for idx, raw in enumerate(items):
                if not isinstance(raw, dict):
                    continue
                element_id = str(raw.get("item_id") or f"{'sel' if is_selected else 'ctx'}_{idx}")
                element_type = self._normalize_type(raw)
                text = self._extract_text(raw)
                bbox = self._extract_bbox(raw)
                element = BoardElement(
                    id=element_id,
                    type=element_type,
                    selected=is_selected,
                    text=text,
                    bbox=bbox,
                    properties=self._safe_properties(raw),
                    confidence=1.0 if element_type != "ink_stroke" else 0.7,
                )
                elements.append(element)
                (selected_ids if is_selected else supporting_ids).append(element_id)

                if text:
                    extracted_text_parts.append(text)
                    equations.extend(self._find_equations(text))
                    questions.extend(self._find_questions(text))
                    concepts.extend(self._concept_tokens(text))

        vision_summary = self._describe_raster(selection.image_b64, selection.user_instruction)
        if vision_summary:
            extracted_text_parts.append(vision_summary)
            equations.extend(self._find_equations(vision_summary))
            questions.extend(self._find_questions(vision_summary))
            concepts.extend(self._concept_tokens(vision_summary))

        instruction = selection.user_instruction.strip() or job.user_prompt.strip()
        if instruction:
            extracted_text_parts.insert(0, instruction)

        extracted_text = "\n".join(dict.fromkeys(p.strip() for p in extracted_text_parts if p.strip()))[:9000]
        concepts = self._dedupe(concepts)[:20]
        equations = self._dedupe(equations)[:12]
        questions = self._dedupe(questions)[:10]

        probable_topic = self._topic_from_content(instruction, concepts, equations, vision_summary)
        ambiguities: List[str] = []
        if not extracted_text and any(e.type == "ink_stroke" for e in elements):
            ambiguities.append("Handwriting is present but could not be confidently interpreted.")
        if not elements and selection.image_b64:
            ambiguities.append("Only a raster crop was available; spatial object semantics are limited.")

        relations = self._extract_relations(elements)

        job.board_ir = BoardIR(
            elements=elements,
            relations=relations,
            concepts=concepts,
            equations=equations,
            questions=questions,
            selected_element_ids=selected_ids,
            supporting_element_ids=supporting_ids,
            probable_topic=probable_topic,
            learning_intent=instruction or "Explain the selected whiteboard region.",
            ambiguities=ambiguities,
            vision_summary=vision_summary,
            extracted_text=extracted_text,
        )
        return job

    def _normalize_type(self, raw: Dict[str, Any]) -> str:
        raw_type = str(raw.get("type", "unknown"))
        if raw_type == "InkStroke":
            return "ink_stroke"
        if raw_type == "SmartShapeItem":
            return str(raw.get("stroke_type", "shape"))
        lowered = raw_type.lower()
        if "text" in lowered or "note" in lowered or "bubble" in lowered:
            return "text"
        if "graph" in lowered:
            return "graph"
        if "image" in lowered:
            return "image"
        if "table" in lowered:
            return "table"
        if "video" in lowered:
            return "video"
        return lowered or "unknown"

    def _extract_text(self, data: Any) -> str:
        found: List[str] = []

        def walk(value: Any, key: str = "") -> None:
            if len(found) >= 20:
                return
            if isinstance(value, dict):
                for k, v in value.items():
                    if k in _TEXT_KEYS and isinstance(v, str) and v.strip():
                        found.append(v.strip())
                    elif isinstance(v, (dict, list, tuple)):
                        walk(v, k)
            elif isinstance(value, (list, tuple)):
                for item in value[:30]:
                    walk(item, key)

        walk(data)
        return " | ".join(dict.fromkeys(found))[:2500]

    def _extract_bbox(self, raw: Dict[str, Any]) -> Dict[str, float]:
        bbox = raw.get("scene_bbox")
        if isinstance(bbox, dict):
            return {k: float(v) for k, v in bbox.items() if k in {"x", "y", "width", "height"} and isinstance(v, (int, float))}

        x = raw.get("x")
        y = raw.get("y")
        dims = raw.get("dimensions_px", {}) if isinstance(raw.get("dimensions_px"), dict) else {}
        width = dims.get("width") or dims.get("side") or (2 * dims.get("radius", 0) if dims.get("radius") else None)
        height = dims.get("height") or dims.get("side") or (2 * dims.get("radius", 0) if dims.get("radius") else None)
        out: Dict[str, float] = {}
        for key, value in (("x", x), ("y", y), ("width", width), ("height", height)):
            if isinstance(value, (int, float)):
                out[key] = float(value)
        return out

    def _safe_properties(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        blocked = {"image_b64", "pixmap_b64"}
        props = {k: v for k, v in raw.items() if k not in blocked}
        elements = props.get("elements")
        if isinstance(elements, list) and len(elements) > 1200:
            props["elements"] = elements[:1200]
            props["elements_truncated"] = True
        return props

    def _find_equations(self, text: str) -> List[str]:
        lines = [line.strip() for line in re.split(r"[\n|]", text) if line.strip()]
        math_symbols = ("=", "∫", "Σ", "∑", "∂", "∇", "→", "^", "frac")
        return [line for line in lines if any(tok in line for tok in math_symbols) and len(line) <= 180]

    def _extract_relations(self, elements: List[BoardElement]) -> List[Any]:
        from backend.video_generation.models import BoardRelation
        import math
        
        relations = []
        for i, el1 in enumerate(elements):
            for j, el2 in enumerate(elements):
                if i == j: continue
                # Simple bounding box near heuristic
                x1, y1 = el1.bbox.get("x", 0), el1.bbox.get("y", 0)
                x2, y2 = el2.bbox.get("x", 0), el2.bbox.get("y", 0)
                dist = math.hypot(x1 - x2, y1 - y2)
                
                # if one is a line/arrow and another is an object
                if el1.type in ["arrow", "line"]:
                    p1 = el1.properties.get("fit_data", {}).get("p1", (x1, y1))
                    p2 = el1.properties.get("fit_data", {}).get("p2", (x1, y1))
                    dist_to_start = math.hypot(p1[0] - x2, p1[1] - y2)
                    dist_to_end = math.hypot(p2[0] - x2, p2[1] - y2)
                    if dist_to_start < 100:
                        relations.append(BoardRelation(source=el1.id, target=el2.id, relation="arrow_from", confidence=0.9))
                    elif dist_to_end < 100:
                        relations.append(BoardRelation(source=el1.id, target=el2.id, relation="arrow_to", confidence=0.9))
                
                # Spatial "contains"
                w1, h1 = el1.bbox.get("width", 0), el1.bbox.get("height", 0)
                w2, h2 = el2.bbox.get("width", 0), el2.bbox.get("height", 0)
                if x1 <= x2 and y1 <= y2 and x1 + w1 >= x2 + w2 and y1 + h1 >= y2 + h2 and el1.type != "ink_stroke":
                    relations.append(BoardRelation(source=el1.id, target=el2.id, relation="contains", confidence=0.9))
                    
                # Near / Label
                if dist < 150 and el1.type == "text" and el2.type != "text":
                    relations.append(BoardRelation(source=el1.id, target=el2.id, relation="label_for", confidence=0.7))
        return relations

    def _find_questions(self, text: str) -> List[str]:
        chunks = re.split(r"(?<=[?.!])\s+|\n", text)
        return [c.strip() for c in chunks if c.strip().endswith("?")][:10]

    def _concept_tokens(self, text: str) -> List[str]:
        words = re.findall(r"[A-Za-z][A-Za-z0-9_\-]{3,}", text.lower())
        stop = {
            "this", "that", "with", "from", "what", "when", "where", "which", "selected",
            "whiteboard", "region", "explain", "student", "using", "show", "into", "have",
            "about", "there", "their", "would", "could", "should", "does", "your",
        }
        return [w for w in words if w not in stop]

    def _topic_from_content(self, instruction: str, concepts: List[str], equations: List[str], vision_summary: str) -> str:
        if instruction and instruction.lower() not in {"explain the selected whiteboard region.", "explain this selection."}:
            return instruction[:180]
        if concepts:
            return " ".join(concepts[:5]).title()
        if equations:
            return equations[0][:180]
        if vision_summary:
            return vision_summary[:180]
        return "Selected Whiteboard Concept"

    def _describe_raster(self, image_b64: str, instruction: str) -> str:
        if not image_b64:
            return ""
        raw = image_b64.split(",", 1)[-1]
        try:
            image_bytes = base64.b64decode(raw)
        except Exception:
            return ""

        google_key = os.getenv("GOOGLE_API_KEY")
        if google_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=google_key)
                model = genai.GenerativeModel("gemini-3.5-flash-lite")
                prompt = (
                    "Analyze this selected smart-whiteboard region for a tutoring system. "
                    "Identify visible handwriting, equations, diagrams, arrows, labels, and the likely concept. "
                    "Be concise and factual; do not invent unreadable text. "
                    f"User instruction: {instruction or 'Explain this selection.'}"
                )
                response = model.generate_content([
                    prompt,
                    {"mime_type": "image/png", "data": image_bytes},
                ])
                if response and getattr(response, "text", None):
                    return response.text.strip()[:3500]
            except Exception as exc:
                print(f"[BoardUnderstandingAgent] Gemini vision unavailable: {exc}")

        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            try:
                from groq import Groq
                client = Groq(api_key=groq_key)
                data_url = f"data:image/png;base64,{base64.b64encode(image_bytes).decode('ascii')}"
                response = client.chat.completions.create(
                    model="llama-3.2-11b-vision-preview",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe the selected whiteboard content, equations and diagram accurately. Do not guess unreadable text."},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }],
                )
                return (response.choices[0].message.content or "").strip()[:3500]
            except Exception as exc:
                print(f"[BoardUnderstandingAgent] Groq vision unavailable: {exc}")
        return ""

    @staticmethod
    def _dedupe(values: Iterable[str]) -> List[str]:
        seen = set()
        out = []
        for value in values:
            key = value.strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append(value.strip())
        return out
