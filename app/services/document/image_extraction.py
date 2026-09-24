import os
import uuid
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
        
        # Phase 1/2: We do not fake OCR/Vision extraction.
        # Image analysis is deferred.
        return []
