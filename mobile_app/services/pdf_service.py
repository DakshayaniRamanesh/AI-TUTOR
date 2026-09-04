"""
PDF Service for Kestrel Mobile App
Extracts text from PDF, converts images/scans to multi-page PDF, and generates PDF notes.
"""

import os
from typing import List, Dict, Any, Optional
from pypdf import PdfReader, PdfWriter
from fpdf import FPDF
from PIL import Image

def extract_pdf_text(pdf_path: str, max_pages: int = 10) -> str:
    """Extract text content from a PDF file."""
    if not os.path.exists(pdf_path):
        return "PDF file not found."
    try:
        reader = PdfReader(pdf_path)
        extracted = []
        num_pages = min(len(reader.pages), max_pages)
        for i in range(num_pages):
            page_text = reader.pages[i].extract_text() or ""
            extracted.append(f"--- Page {i+1} ---\n{page_text.strip()}")
        return "\n\n".join(extracted)
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

def convert_images_to_pdf(image_paths: List[str], output_pdf_path: str) -> bool:
    """Convert one or multiple image files into a single high-quality PDF document."""
    try:
        valid_images = []
        for img_path in image_paths:
            if os.path.exists(img_path):
                img = Image.open(img_path)
                if img.mode != "RGB":
                    img = img.convert("RGB")
                valid_images.append(img)
                
        if not valid_images:
            return False
            
        first_image = valid_images[0]
        other_images = valid_images[1:]
        first_image.save(output_pdf_path, "PDF", resolution=100.0, save_all=True, append_images=other_images)
        return True
    except Exception as e:
        print(f"Error converting images to PDF: {e}")
        return False

def generate_notes_pdf(title: str, content: str, output_path: str) -> bool:
    """Generate a clean, styled PDF document for study notes."""
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 18)
        
        # Title header
        pdf.cell(0, 12, title, new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(5)
        
        # Divider line
        pdf.set_draw_color(0, 122, 255) # iOS Blue
        pdf.set_line_width(1)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(8)
        
        # Content
        pdf.set_font("Helvetica", "", 12)
        lines = content.split("\n")
        for line in lines:
            # Handle unicode/accented characters safely for basic FPDF
            clean_line = line.encode("latin-1", "replace").decode("latin-1")
            pdf.multi_cell(0, 7, clean_line)
            
        pdf.output(output_path)
        return True
    except Exception as e:
        print(f"Error generating PDF notes: {e}")
        return False
