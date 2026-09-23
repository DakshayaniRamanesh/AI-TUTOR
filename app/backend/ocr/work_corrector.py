"""
Work Corrector — AI Vision Analysis Engine for Student Canvas Work.

Sends a base64 canvas image to a vision-capable LLM and receives structured
Socratic feedback identifying mistakes with region, message, and progressive hints.

Primary:  Groq Vision (meta-llama/llama-4-scout-17b-16e-instruct)
Fallback: Google Gemini Vision (gemini-2.0-flash-lite)
"""

import os
import re
import json
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
load_dotenv("backend/.env")
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "backend", ".env"))

# ── Socratic Tutor System Prompt ───────────────────────────────────────────────

_SYSTEM_PROMPT = """You are KESTREL, a professional Socratic mathematics and science tutor embedded inside a student whiteboard application.

A student has written their work on a digital canvas. Your job is to:
1. Carefully READ and IDENTIFY what is written — equations, steps, diagrams, working, calculations.
2. Identify the subject (e.g. Algebra, Calculus, Geometry, Physics, Chemistry, Statistics) and the method being used.
3. Find ALL errors, sign mistakes, skipped steps, conceptual misunderstandings, or incorrect answers.
4. If there are errors, identify WHERE on the canvas the first/main error appears.
5. Respond with a JSON object (and ONLY the JSON object, no surrounding text).

IMPORTANT RULES:
- Be precise about what is actually written — do NOT invent errors that are not there.
- If the work is CORRECT, report mode "verified" and give an encouraging message.
- Keep the "spoken_message" concise (1-2 sentences), direct, and Socratic — guide the student to discover the error themselves rather than just stating the answer.
- The 3 hints must be progressive: hint 1 is a nudge, hint 2 is a relevant rule/formula, hint 3 reveals the correct step.
- The "error_region" describes roughly WHERE on the canvas the error appears (used to position the laser pointer):
    - "top_third"    — error is in the upper portion of the work
    - "middle"       — error is in the centre of the work
    - "bottom_third" — error is in the lower portion of the work
    - "full"         — the entire method/approach is wrong, or the canvas has only one item

Respond ONLY with this JSON schema (no markdown fences, no extra text):
{
  "has_errors": true,
  "subject": "<subject detected>",
  "method": "<technique or concept being used>",
  "error_description": "<precise internal description of the error for logging>",
  "error_region": "top_third|middle|bottom_third|full",
  "spoken_message": "<short Socratic message spoken to the student>",
  "hints": [
    "<hint 1: gentle nudge toward the error>",
    "<hint 2: relevant rule or formula>",
    "<hint 3: the corrected step or solution>"
  ],
  "mode": "error"
}

If no errors are found, respond with:
{
  "has_errors": false,
  "subject": "<subject>",
  "method": "<method>",
  "error_description": "No errors detected.",
  "error_region": "full",
  "spoken_message": "<encouraging message, e.g. Your working looks correct - excellent attention to signs!>",
  "hints": [],
  "mode": "verified"
}"""

_USER_PROMPT = (
    "Please analyse the student's work shown in this canvas image. "
    "Identify what subject and method is being used, locate any errors, "
    "and return the structured JSON feedback as instructed."
)


# ── Main Analysis Function ─────────────────────────────────────────────────────

def analyse_student_work(b64_image: str) -> dict:
    """
    Sends the canvas image to an AI vision model and returns a structured
    feedback dictionary.

    Returns a dict with keys: has_errors, subject, method, error_description,
    error_region, spoken_message, hints, mode.

    On failure, returns a safe error-state dict so the UI can handle it gracefully.
    """
    if not b64_image:
        return _empty_canvas_response()

    raw_response = (
        _call_groq_vision(b64_image) or
        _call_gemini_vision(b64_image)
    )

    if not raw_response:
        return _api_failure_response()

    return _parse_response(raw_response)


# ── Groq Vision API (Primary) ──────────────────────────────────────────────────

def _call_groq_vision(b64_image: str) -> Optional[str]:
    """Calls Groq Vision using llama-4-scout or llama-4-maverick."""
    groq_key = (
        os.environ.get("GROQ_API_KEY", "").strip() or
        os.getenv("GROQ_API_KEY", "").strip()
    )
    if not groq_key or groq_key.startswith("your_"):
        return None

    models = [
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "meta-llama/llama-4-maverick-17b-128e-instruct",
    ]

    for model in models:
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": _USER_PROMPT},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{b64_image}",
                                        "detail": "high"
                                    }
                                }
                            ]
                        }
                    ],
                    "temperature": 0.1,
                    "max_tokens": 700,
                    "response_format": {"type": "json_object"}
                },
                timeout=20.0
            )
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    text = choices[0].get("message", {}).get("content", "").strip()
                    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
                    if text:
                        print(f"[WorkCorrector] Groq Vision ({model}) responded OK.")
                        return text
            else:
                print(f"[WorkCorrector] Groq Vision ({model}) HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:
            print(f"[WorkCorrector] Groq Vision ({model}) error: {exc}")
            continue

    return None


# ── Gemini Vision API (Fallback) ───────────────────────────────────────────────

def _call_gemini_vision(b64_image: str) -> Optional[str]:
    """Calls Google Gemini Vision as a fallback."""
    gemini_key = (
        os.environ.get("GEMINI_API_KEY", "").strip() or
        os.environ.get("GOOGLE_API_KEY", "").strip() or
        os.getenv("GOOGLE_API_KEY", "").strip()
    )
    if not gemini_key or gemini_key.startswith("your_"):
        return None

    models = ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-flash-latest"]

    combined_prompt = _SYSTEM_PROMPT + "\n\n" + _USER_PROMPT

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": combined_prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": b64_image
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 700,
            "responseMimeType": "application/json"
        }
    }

    for model in models:
        try:
            api_url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={gemini_key}"
            )
            resp = requests.post(api_url, json=payload, timeout=20.0)
            if resp.status_code == 200:
                data = resp.json()
                text = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                    .strip()
                )
                text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
                if text:
                    print(f"[WorkCorrector] Gemini Vision ({model}) responded OK.")
                    return text
            else:
                print(f"[WorkCorrector] Gemini Vision ({model}) HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:
            print(f"[WorkCorrector] Gemini Vision ({model}) error: {exc}")
            continue

    return None


# ── Response Parsing ───────────────────────────────────────────────────────────

def _parse_response(raw: str) -> dict:
    """
    Parses the AI JSON response into a clean feedback dict.
    Falls back to a safe error message if parsing fails.
    """
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    raw = re.sub(r"```\s*$", "", raw.strip(), flags=re.MULTILINE)
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                print(f"[WorkCorrector] JSON parse fallback failed. Raw:\n{raw[:300]}")
                return _api_failure_response()
        else:
            print(f"[WorkCorrector] No JSON found. Raw:\n{raw[:300]}")
            return _api_failure_response()

    has_errors = bool(data.get("has_errors", True))
    mode = str(data.get("mode", "error")).lower()
    if mode not in ("error", "verified"):
        mode = "error" if has_errors else "verified"

    hints = data.get("hints", [])
    if not isinstance(hints, list):
        hints = []
    hints = [str(h) for h in hints[:3] if str(h).strip()]

    error_region = str(data.get("error_region", "full")).lower()
    if error_region not in ("top_third", "middle", "bottom_third", "full"):
        error_region = "full"

    spoken_message = str(data.get("spoken_message", "")).strip()
    if not spoken_message:
        spoken_message = (
            "Your work looks correct — great job!"
            if mode == "verified"
            else "There seems to be an issue with your working. Take a closer look."
        )

    return {
        "has_errors": has_errors,
        "subject": str(data.get("subject", "Mathematics")),
        "method": str(data.get("method", "")),
        "error_description": str(data.get("error_description", "")),
        "error_region": error_region,
        "spoken_message": spoken_message,
        "hints": hints,
        "mode": mode,
    }


# ── Safe Fallback Responses ────────────────────────────────────────────────────

def _empty_canvas_response() -> dict:
    return {
        "has_errors": False,
        "subject": "",
        "method": "",
        "error_description": "Canvas was empty — nothing to analyse.",
        "error_region": "full",
        "spoken_message": "Your canvas looks empty. Write out your working and then click Check Work again!",
        "hints": [],
        "mode": "empty",
    }


def _api_failure_response() -> dict:
    return {
        "has_errors": False,
        "subject": "",
        "method": "",
        "error_description": "AI analysis unavailable (API key missing or network error).",
        "error_region": "full",
        "spoken_message": "I could not connect to the AI tutor right now. Please check your API keys and try again.",
        "hints": [],
        "mode": "error",
    }
