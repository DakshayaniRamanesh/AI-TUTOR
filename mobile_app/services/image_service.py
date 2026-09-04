"""
Image & Document Scanner Service for Kestrel Mobile
Applies document enhancement filters (B&W scan, high contrast, grayscale) and resizes photos.
"""

import os
from typing import Optional
from PIL import Image, ImageEnhance, ImageOps, ImageFilter

def process_scanned_image(image_path: str, output_path: str, filter_type: str = "scan") -> bool:
    """
    Applies image processing filters to clean up document photos into crisp scans.
    filter_type: 'scan' (High contrast document), 'grayscale' (B&W), 'magic' (Color boost), 'original'
    """
    try:
        if not os.path.exists(image_path):
            return False
            
        img = Image.open(image_path)
        if img.mode != "RGB":
            img = img.convert("RGB")
            
        if filter_type == "scan":
            # Convert to grayscale first
            gray = ImageOps.grayscale(img)
            # Boost contrast aggressively for document text readability
            enhancer = ImageEnhance.Contrast(gray)
            high_contrast = enhancer.enhance(2.2)
            # Sharpen edges slightly
            sharpened = high_contrast.filter(ImageFilter.SHARPEN)
            sharpened.save(output_path, "PNG", quality=95)
            
        elif filter_type == "grayscale":
            gray = ImageOps.grayscale(img)
            gray.save(output_path, "PNG", quality=95)
            
        elif filter_type == "magic":
            # Color and sharpness boost
            c_enhancer = ImageEnhance.Color(img)
            color_boost = c_enhancer.enhance(1.4)
            cnt_enhancer = ImageEnhance.Contrast(color_boost)
            final_img = cnt_enhancer.enhance(1.3)
            final_img.save(output_path, "PNG", quality=95)
            
        else:
            # Original
            img.save(output_path, "PNG", quality=95)
            
        return True
    except Exception as e:
        print(f"Error processing image scan: {e}")
        return False

def generate_thumbnail(image_path: str, thumb_path: str, size: tuple = (300, 300)) -> bool:
    """Generate a lightweight square thumbnail for fast carousel rendering."""
    try:
        if not os.path.exists(image_path):
            return False
        img = Image.open(image_path)
        img.thumbnail(size)
        img.save(thumb_path, "PNG")
        return True
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return False
