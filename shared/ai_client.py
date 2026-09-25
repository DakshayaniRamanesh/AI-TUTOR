import os
import json
import traceback
from typing import Optional, Dict, Any, Union
from pydantic import BaseModel
from .ai_config import get_model_config

# Lightweight wrapper around litellm or just direct requests, but since litellm might not be installed,
# we'll build a simple unified REST caller for the main providers (Gemini, Groq).
# For production safety we can use standard requests.

import requests


def _image_mime(image_b64: str) -> str:
    if image_b64.startswith("iVBOR"):
        return "image/png"
    return "image/jpeg"

class AIClient:
    def __init__(self):
        self.config = get_model_config

    def generate_content(
        self, 
        prompt: str, 
        system_instruction: str = "",
        image_b64: Optional[str] = None,
        json_schema: Optional[Dict] = None,
        temperature: float = 0.0
    ) -> str:
        """
        Unified method to call the configured model.
        Returns the text response.
        """
        provider = self.config.provider
        api_key = self.config.get_api_key()
        model_id = self.config.model_id

        # Primary call with graceful fallback across providers and models
        errors = []
        
        # 1. Try primary configured call
        if api_key:
            try:
                if provider == "groq":
                    return self._call_groq(api_key, model_id, prompt, system_instruction, image_b64, json_schema, temperature)
                elif provider in ["gemini", "google"]:
                    return self._call_gemini(api_key, model_id, prompt, system_instruction, image_b64, json_schema, temperature)
            except Exception as e:
                errors.append(f"Primary ({provider}/{model_id}): {e}")

        # 2. Try alternative Gemini models if Gemini was used or available
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if gemini_key:
            for alt_gemini in ["gemini-3-flash-preview", "gemini-flash-lite-latest", "gemini-flash-latest"]:
                if alt_gemini == model_id and provider in ["gemini", "google"]:
                    continue
                try:
                    return self._call_gemini(gemini_key, alt_gemini, prompt, system_instruction, image_b64, json_schema, temperature)
                except Exception as e:
                    errors.append(f"Gemini ({alt_gemini}): {e}")

        # 3. Fallback to Groq if not already attempted or failed
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key and not (provider == "groq" and model_id == "qwen/qwen3.8-27b"):
            try:
                return self._call_groq(groq_key, "qwen/qwen3.8-27b", prompt, system_instruction, image_b64, json_schema, temperature)
            except Exception as e:
                errors.append(f"Groq (qwen/qwen3.8-27b): {e}")

        raise RuntimeError(f"All AI generation providers failed:\n" + "\n".join(errors))

    def _call_groq(self, api_key: str, model_id: str, prompt: str, system_prompt: str, image_b64: str, json_schema: dict, temperature: float) -> str:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
            
        if image_b64:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{_image_mime(image_b64)};base64,{image_b64}"
                        }
                    }
                ]
            })
        else:
            messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature
        }
        
        if json_schema:
            payload["response_format"] = {"type": "json_object"}

        resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=self.config.request_timeout_seconds)
        if resp.status_code != 200:
            raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text}")
        
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def _call_gemini(self, api_key: str, model_id: str, prompt: str, system_prompt: str, image_b64: str, json_schema: dict, temperature: float) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        
        contents = []
        
        # Build user part
        user_parts = []
        if prompt:
            user_parts.append({"text": prompt})
        if image_b64:
            user_parts.append({
                "inline_data": {
                    "mime_type": _image_mime(image_b64),
                    "data": image_b64
                }
            })
            
        contents.append({"role": "user", "parts": user_parts})
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature
            }
        }
        
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }
            
        if json_schema:
            payload["generationConfig"]["responseMimeType"] = "application/json"
            # Optional: pass schema if strict enforcement needed
            # payload["generationConfig"]["responseSchema"] = json_schema

        resp = requests.post(url, headers=headers, json=payload, timeout=self.config.request_timeout_seconds)
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text}")
            
        data = resp.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise RuntimeError(f"Unexpected Gemini response format: {json.dumps(data)}")

# Global client
ai_client = AIClient()
