import os
import json
import requests
from dotenv import load_dotenv

load_dotenv("backend/.env")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

class GraphExtractor:
    def extract_graph_from_text(self, text: str) -> tuple[list[dict], list[dict]]:
        """
        Takes raw text, sends it to the AI, and returns structured (nodes, edges).
        Returns: (nodes, edges)
        nodes format: [{"name": "Calculus", "type": "subject", "description": "Study of change"}]
        edges format: [{"source": "Calculus", "target": "Limits", "relationship": "contains"}]
        """
        if not GOOGLE_API_KEY or not text.strip():
            print("[GraphExtractor] Missing API key or empty text.")
            return [], []

        # We take the first 30,000 characters to prevent huge API payloads for massive books
        text_sample = text[:30000]

        prompt = (
            "You are an expert tutor building a Knowledge Graph from a textbook/document.\n"
            "Extract the main concepts and their relationships from the text below.\n"
            "Return ONLY a raw JSON object with two keys: 'nodes' and 'edges'.\n\n"
            "Format:\n"
            "{\n"
            "  \"nodes\": [{\"term\": \"Concept 1\", \"category\": \"concept\", \"summary\": \"A concise 2-sentence summary of what this is.\"}]\n"
            "  \"edges\": [{\"source\": \"Concept 1\", \"target\": \"Concept 2\", \"relationship\": \"related_to\"}]\n"
            "}\n\n"
            "Keep the graph concise (maximum 20 most important nodes).\n"
            "IMPORTANT: Classify every node into one of these strict categories: 'concept', 'entity', 'tool', 'example'.\n\n"
            f"TEXT TO ANALYZE:\n{text_sample}"
        )


        models = ["gemini-3.5-flash-lite"]
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        }

        for model in models:
            try:
                print(f"[GraphExtractor] Asking {model} to extract concepts (this takes ~10 seconds)...")
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GOOGLE_API_KEY}"
                resp = requests.post(url, json=payload, timeout=15)
                
                print(f"[GraphExtractor] Received response! Status Code: {resp.status_code}")
                
                if resp.status_code == 200:
                    result_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    print(f"[GraphExtractor] AI Output snippet: {result_text[:100]}...") # Print first 100 chars
                    
                    # Clean up the AI output just in case it adds ```json ... ```
                    if result_text.startswith("```json"):
                        result_text = result_text[7:]
                    if result_text.startswith("```"):
                        result_text = result_text[3:]
                    if result_text.endswith("```"):
                        result_text = result_text[:-3]
                        
                    data = json.loads(result_text.strip())
                    return data.get("nodes", []), data.get("edges", [])
            except Exception as err:
                print(f"[GraphExtractor] API Error ({model}): {err}")
                
        return [], []
