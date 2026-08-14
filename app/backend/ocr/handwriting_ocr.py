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
        models = ["gemini-flash-lite-latest", "gemma-4-26b-a4b-it", "gemini-flash-latest"]
        prompt = (
            "You are an expert OCR transcription engine.\n"
            "Transcribe the handwritten text, formula, question, or diagram topic shown in this canvas image.\n"
            "Output ONLY the clean transcribed question, formula, or sketch request (e.g. 'sketch cross section of heart and mark the parts' or 'formula for benzene C6H6'). No conversation."
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
                api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                resp = requests.post(api_url, json=payload, timeout=4.0)
                if resp.status_code == 200:
                    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if text:
                        return text
            except Exception:
                continue

    return ""
