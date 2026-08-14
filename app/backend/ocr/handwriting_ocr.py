"""
Handwriting Recognition & Multimodal Vision OCR Backend Client.
Converts canvas ink strokes and diagrams to clean text/formulas using Gemini Multimodal AI.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()
load_dotenv("backend/.env")
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "backend", ".env"))


def recognize_handwriting(input_text_or_path: str = "", b64_image: str = "", stroke_count: int = 0) -> str:
    """
    Recognizes handwritten text, equations, or chemical structures from canvas.
    Supports direct text or base64 rendered ink images.
    """
    if input_text_or_path and not input_text_or_path.startswith("Recognized"):
        return input_text_or_path.strip()

    api_key = os.getenv("GOOGLE_API_KEY")

    if b64_image and api_key:
        models = ["models/gemini-flash-latest", "models/gemini-flash-lite-latest"]
        prompt = (
            "You are an expert handwritten OCR transcription system.\n"
            "Transcribe the handwritten math equation, chemical formula, chemical structure (e.g. Benzene ring), or question shown in this canvas image.\n"
            "Output ONLY the clean transcribed equation, formula (e.g. 'Formula for benzene C6H6' or 'x^2 + 5x + 6 = 0'), or topic. No conversational filler."
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": b64_image
                            }
                        }
                    ]
                }
            ]
        }
        for model in models:
            try:
                api_url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={api_key}"
                resp = requests.post(api_url, json=payload, timeout=3.5)
                if resp.status_code == 200:
                    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if text:
                        return text
            except Exception as e:
                print(f"[OCR] Vision Notice: {e}")
                continue

    return ""
