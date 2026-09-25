import os
import base64
from typing import Optional

class ImageExtractionAdapter:
    """
    Adapter for extracting text and structure from an image file using existing vision infrastructure.
    In Phase 1, we just return basic OCR fallback if no provider is configured, or use MockProviderClient for tests.
    """
    
    def extract(self, image_path: str, subject_id: str, document_title: Optional[str] = None) -> list[dict]:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")
            
        title = document_title or os.path.basename(image_path)
        
        from shared.ai_client import ai_client
        with open(image_path, "rb") as image_file:
            image_b64 = base64.b64encode(image_file.read()).decode("ascii")
        text = ai_client.generate_content(
            "Transcribe all visible educational content exactly. Preserve headings, formulas, labels, and notes. "
            "Do not invent content and do not solve questions. Return plain text only.",
            system_instruction="You are a faithful OCR system for study materials.",
            image_b64=image_b64,
            temperature=0.0,
        ).strip()
        if not text:
            return []
        return [{
            "document_title": title,
            "chapter": "Image Material",
            "section": title,
            "page_number": 1,
            "content_type": "image_ocr",
            "text": text,
        }]
