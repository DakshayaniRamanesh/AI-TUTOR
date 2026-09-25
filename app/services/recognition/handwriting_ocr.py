"""Handwriting recognition through Kestrel's single configured AI model."""

import json
import re

from shared.ai_client import ai_client


_OCR_SCHEMA = {
    "type": "object",
    "properties": {
        "content_type": {"type": "string", "enum": ["EQUATION", "TEXT", "DIAGRAM", "UNKNOWN"]},
        "text": {"type": "string"},
        "latex": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["content_type", "text", "confidence"],
}


def recognize_handwriting(input_text_or_path: str = "", b64_image: str = "", stroke_count: int = 0) -> dict:
    if input_text_or_path and not input_text_or_path.startswith("Recognized"):
        return {"text": input_text_or_path.strip(), "content_type": "TEXT", "confidence": 1.0}
    if not b64_image:
        raise ValueError("No handwriting image was supplied.")

    prompt = (
        "Transcribe the handwriting exactly. Do not solve, simplify, correct, or infer a next step. "
        "Preserve brackets, exponents, operators, equals signs, and line order. "
        "Classify it as EQUATION, TEXT, DIAGRAM, or UNKNOWN. Return only JSON with "
        "content_type, text, latex, and confidence. Use UNKNOWN and low confidence when uncertain."
    )
    raw = ai_client.generate_content(
        prompt,
        system_instruction="You are a precise mathematics and science handwriting OCR engine.",
        image_b64=b64_image,
        json_schema=_OCR_SCHEMA,
        temperature=0.0,
    ).strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE | re.DOTALL)
    parsed = json.loads(raw)
    content_type = str(parsed.get("content_type", "UNKNOWN")).upper()
    if content_type not in {"EQUATION", "TEXT", "DIAGRAM", "UNKNOWN"}:
        content_type = "UNKNOWN"
    text = str(parsed.get("text", "")).strip()
    if not text:
        raise ValueError("The OCR model returned no transcription.")
    confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.0))))
    return {
        "content_type": content_type,
        "text": text,
        "latex": str(parsed.get("latex") or text).strip(),
        "confidence": confidence,
    }
