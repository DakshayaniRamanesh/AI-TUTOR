"""
Handwriting Recognition & Multimodal Vision OCR Backend Client.
Converts canvas ink strokes and diagrams to clean text/formulas using Groq Vision (primary) and Gemini Vision (fallback).
"""

import os
import re
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
    Uses Groq Vision (qwen/qwen3.8-27b, qwen/qwen3.6-27b) as the primary fast engine,
    with Google Gemini Vision as fallback.
    """
    if input_text_or_path and not input_text_or_path.startswith("Recognized"):
        return input_text_or_path.strip()

    if not b64_image:
        return ""

    prompt = (
        "You are an expert OCR transcription engine for mathematics and science handwriting.\n"
        "Transcribe the handwritten text, formula, question, or diagram topic shown in this canvas image.\n"
        "Output ONLY the clean transcribed question or formula (e.g. 'integrate 5x dx' or 'differentiate 5x^3' or 'formula for benzene C6H6'). "
        "Do NOT output thinking process, conversational text, quotes, or markdown backticks."
    )

    # 1. PRIMARY: Groq Vision (fast, high accuracy, active API key)
    groq_key = (
        os.environ.get("GROQ_API_KEY", "").strip() or
        os.getenv("GROQ_API_KEY", "").strip()
    )
    if groq_key and not groq_key.startswith("your_"):
        for model in ["qwen/qwen3.8-27b", "qwen/qwen3.6-27b"]:
            try:
                resp = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {groq_key}"},
                    json={
                        "model": model,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}}
                                ]
                            }
                        ],
                        "temperature": 0.1,
                        "max_tokens": 300
                    },
                    timeout=8.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        raw = choices[0].get("message", {}).get("content", "").strip()
                        raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
                        raw = raw.strip('"`\'')
                        if raw:
                            return raw
            except Exception as e:
                print(f"[Handwriting OCR Groq Vision] Error: {e}")
                continue

    # 2. SECONDARY / FALLBACK: Google Gemini Vision
    gemini_key = (
        os.environ.get("GEMINI_API_KEY", "").strip() or
        os.environ.get("GOOGLE_API_KEY", "").strip() or
        os.getenv("GOOGLE_API_KEY", "").strip()
    )
    if gemini_key and not gemini_key.startswith("your_"):
        models = ["gemini-flash-latest", "gemini-flash-lite-latest"]
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
                api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
                resp = requests.post(api_url, json=payload, timeout=6.0)
                if resp.status_code == 200:
                    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
                    if text:
                        return text
            except Exception:
                continue

    return ""
