import time
import base64
import json
from PyQt6.QtCore import QThread, pyqtSignal
from shared.ai_client import ai_client

class ModelReadinessWorker(QThread):
    finished = pyqtSignal(dict)

    def run(self):
        results = {
            "provider": ai_client.config.provider,
            "model_id": ai_client.config.model_id,
            "start_time": time.time(),
            "tests": {},
            "overall_ready": True
        }

        def run_test(name, func):
            start = time.time()
            try:
                # Use temperature 0 for tests
                res = func()
                latency = time.time() - start
                results["tests"][name] = {
                    "pass": True,
                    "latency": latency,
                    "error": None
                }
            except Exception as e:
                latency = time.time() - start
                results["tests"][name] = {
                    "pass": False,
                    "latency": latency,
                    "error": str(e)
                }
                results["overall_ready"] = False

        # 1. Text health
        def text_health():
            resp = ai_client.generate_content("Say 'OK'", temperature=0.0)
            if not resp or len(resp) > 50:
                raise ValueError("Unexpected text response")

        run_test("Text", text_health)

        # 2. Structured JSON
        def structured_json():
            schema = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
            resp = ai_client.generate_content("Return JSON with name='Kestrel'. Use exact schema.", json_schema=schema, temperature=0.0)
            # Remove markdown if any
            clean = resp.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean)
            if data.get("name") != "Kestrel":
                raise ValueError("JSON content mismatch")
                
        run_test("Structured output", structured_json)

        # 3. Vision
        def vision_test():
            if not ai_client.config.supports_vision:
                raise ValueError("Model configuration declares no vision support")
            try:
                with open("equation.jpg", "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode('utf-8')
            except FileNotFoundError:
                from PIL import Image, ImageDraw
                img = Image.new('RGB', (200, 50), color=(255, 255, 255))
                d = ImageDraw.Draw(img)
                d.text((10, 10), '2(x+3)=10', fill=(0, 0, 0))
                img.save("equation.jpg")
                with open("equation.jpg", "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode('utf-8')

            resp = ai_client.generate_content("Transcribe this equation. Do not solve it.", image_b64=img_b64, temperature=0.0)
            if "2" not in resp or "x" not in resp:
                raise ValueError(f"Vision transcription failed: {resp}")

        run_test("Vision", vision_test)

        # 4. Exact LaTeX
        def exact_latex():
            prompt = "Convert this to LaTeX exactly as written, do not solve: 2(x + 3) = 10"
            resp = ai_client.generate_content(prompt, temperature=0.0)
            if "6" in resp or "2x" in resp:
                raise ValueError("Model solved or simplified the equation instead of exact transcription.")
                
        run_test("Exact LaTeX", exact_latex)

        # 5. Grounded response
        def grounded_response():
            prompt = "Use the following evidence to answer what color the sky is. Evidence: [Doc1] The sky on planet X is green."
            resp = ai_client.generate_content(prompt, temperature=0.0)
            if "green" not in resp.lower():
                raise ValueError("Model failed to ground response in evidence.")
                
        run_test("Grounded response", grounded_response)

        # 6. Semantic extraction
        def semantic_extraction():
            prompt = "Extract concepts as JSON. Text: Mitochondria is the powerhouse of the cell."
            resp = ai_client.generate_content(prompt, json_schema={"type": "object"}, temperature=0.0)
            if "mitochondria" not in resp.lower():
                raise ValueError("Model failed semantic extraction.")
                
        run_test("Semantic extraction", semantic_extraction)

        # 7. Video plan
        def video_plan():
            prompt = "Create a JSON video scene plan for a 10 second clip about addition."
            resp = ai_client.generate_content(prompt, json_schema={"type": "object"}, temperature=0.0)
            if "{" not in resp:
                raise ValueError("Model failed to generate video plan JSON.")
                
        run_test("Video plan", video_plan)

        results["finish_time"] = time.time()
        self.finished.emit(results)
