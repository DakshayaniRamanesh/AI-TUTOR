"""
Storage management for Kestrel Mobile iOS App
Manages local file storage for PDFs, images, notes, and metadata database.
"""

import os
import json
import shutil
import base64
from datetime import datetime
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_ROOT = os.path.join(BASE_DIR, "storage_data")

PDF_DIR = os.path.join(STORAGE_ROOT, "pdfs")
IMAGE_DIR = os.path.join(STORAGE_ROOT, "images")
NOTES_DIR = os.path.join(STORAGE_ROOT, "notes")
THUMB_DIR = os.path.join(STORAGE_ROOT, "thumbnails")
DB_FILE = os.path.join(STORAGE_ROOT, "db.json")

def init_storage():
    """Ensure all required storage directories exist and db.json is initialized."""
    for d in [STORAGE_ROOT, PDF_DIR, IMAGE_DIR, NOTES_DIR, THUMB_DIR]:
        os.makedirs(d, exist_ok=True)
        
    if not os.path.exists(DB_FILE):
        default_db = {
            "items": [],
            "settings": {
                "theme": "light",
                "gemini_api_key": ""
            },
            "stats": {
                "pdfs_saved": 0,
                "photos_captured": 0,
                "scans_completed": 0,
                "notes_created": 0
            }
        }
        _save_db(default_db)
        _seed_sample_data()

def _load_db() -> Dict[str, Any]:
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"items": [], "settings": {}, "stats": {}}

def _save_db(db: Dict[str, Any]):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def _seed_sample_data():
    """Create sample initial items so the app is immediately rich and interactive."""
    sample_items = [
        {
            "id": "sample_pdf_1",
            "title": "Quantum Physics Summary.pdf",
            "type": "pdf",
            "file_path": os.path.join(PDF_DIR, "Quantum_Physics_Summary.pdf"),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "size_str": "1.2 MB",
            "tags": ["Physics", "Study Guide"],
            "summary": "Comprehensive overview of wave-particle duality, Schrödinger equation, and quantum entanglement."
        },
        {
            "id": "sample_img_1",
            "title": "Calculus Notes Scan",
            "type": "image",
            "file_path": os.path.join(IMAGE_DIR, "Calculus_Notes_Scan.png"),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "size_str": "850 KB",
            "tags": ["Math", "Scanned"],
            "summary": "Handwritten calculus integration rules and derivative practice problems."
        }
    ]
    db = _load_db()
    db["items"].extend(sample_items)
    db["stats"]["pdfs_saved"] = 1
    db["stats"]["photos_captured"] = 1
    _save_db(db)

from mobile_app import kestrel_bridge

def get_all_items() -> List[Dict[str, Any]]:
    db = _load_db()
    local_items = db.get("items", [])
    
    # Merge with Kestrel Desktop Reference PDFs and Boards
    desktop_mats = kestrel_bridge.get_kestrel_desktop_materials()
    desktop_boards = kestrel_bridge.get_kestrel_desktop_boards()
    
    seen_paths = {i.get("file_path") for i in local_items if i.get("file_path")}
    merged = list(local_items)
    
    for mat in desktop_mats:
        if mat["file_path"] not in seen_paths:
            seen_paths.add(mat["file_path"])
            size = 0
            if os.path.exists(mat["file_path"]):
                size = os.path.getsize(mat["file_path"])
            size_str = f"{round(size/1024, 1)} KB" if size < 1024*1024 else f"{round(size/(1024*1024), 1)} MB"
            merged.append({
                "id": mat["id"],
                "title": mat["title"],
                "type": "pdf",
                "file_path": mat["file_path"],
                "created_at": mat["created_at"],
                "size_str": size_str,
                "tags": ["Kestrel Desktop", "Synced PDF"],
                "summary": "Reference PDF from Kestrel Desktop Dashboard",
                "is_desktop": True
            })

    for board in desktop_boards:
        if board["file_path"] not in seen_paths:
            seen_paths.add(board["file_path"])
            merged.append({
                "id": board["id"],
                "title": board["title"],
                "type": "board",
                "file_path": board["file_path"],
                "created_at": board["created_at"],
                "size_str": f"{board['item_count']} items",
                "tags": ["Kestrel Board", "Whiteboard"],
                "summary": "Kestrel Canvas Whiteboard Notebook",
                "is_desktop": True
            })
            
    return merged

def get_items_by_type(item_type: str) -> List[Dict[str, Any]]:
    items = get_all_items()
    return [item for item in items if item.get("type") == item_type]

def add_item(title: str, item_type: str, source_path: Optional[str] = None, content_bytes: Optional[bytes] = None, tags: Optional[List[str]] = None, summary: str = "") -> Dict[str, Any]:
    db = _load_db()
    item_id = f"{item_type}_{int(datetime.now().timestamp())}"
    
    dest_dir = PDF_DIR if item_type == "pdf" else (IMAGE_DIR if item_type in ["image", "scan"] else NOTES_DIR)
    file_ext = ".pdf" if item_type == "pdf" else (".png" if item_type in ["image", "scan"] else ".txt")
    
    clean_filename = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).rstrip()
    if not clean_filename.endswith(file_ext):
        clean_filename += file_ext
        
    dest_path = os.path.join(dest_dir, clean_filename)
    
    file_size = 0
    if source_path and os.path.exists(source_path):
        shutil.copy2(source_path, dest_path)
        file_size = os.path.getsize(dest_path)
    elif content_bytes:
        with open(dest_path, "wb") as f:
            f.write(content_bytes)
        file_size = len(content_bytes)
    else:
        # Create empty placeholder file if needed
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(summary or title)
        file_size = os.path.getsize(dest_path)

    size_str = f"{round(file_size / 1024, 1)} KB" if file_size < 1024 * 1024 else f"{round(file_size / (1024*1024), 1)} MB"

    new_item = {
        "id": item_id,
        "title": title,
        "type": item_type,
        "file_path": dest_path,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "size_str": size_str,
        "tags": tags or ["General"],
        "summary": summary
    }

    db["items"].insert(0, new_item)
    
    # Update stats
    if item_type == "pdf":
        db["stats"]["pdfs_saved"] = db["stats"].get("pdfs_saved", 0) + 1
    elif item_type in ["image", "scan"]:
        db["stats"]["photos_captured"] = db["stats"].get("photos_captured", 0) + 1
    elif item_type == "note":
        db["stats"]["notes_created"] = db["stats"].get("notes_created", 0) + 1

    _save_db(db)

    # ── Automatic Bidirectional Sync to Kestrel Desktop ──
    try:
        if item_type == "pdf":
            kestrel_bridge.sync_pdf_to_kestrel_desktop(title, dest_path)
        elif item_type in ["image", "scan"]:
            kestrel_bridge.sync_image_to_kestrel_board(dest_path, title)
    except Exception as e:
        print(f"[Storage] Notice: Sync to Kestrel desktop: {e}")

    return new_item

def delete_item(item_id: str) -> bool:
    db = _load_db()
    items = db.get("items", [])
    item_to_remove = next((i for i in items if i["id"] == item_id), None)
    
    if item_to_remove:
        file_path = item_to_remove.get("file_path")
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        db["items"] = [i for i in items if i["id"] != item_id]
        _save_db(db)
        return True
    return False

def get_stats() -> Dict[str, int]:
    db = _load_db()
    return db.get("stats", {"pdfs_saved": 0, "photos_captured": 0, "scans_completed": 0, "notes_created": 0})

def get_settings() -> Dict[str, Any]:
    db = _load_db()
    return db.get("settings", {"theme": "dark", "gemini_api_key": ""})

def save_settings(settings: Dict[str, Any]):
    db = _load_db()
    db["settings"].update(settings)
    _save_db(db)

def get_image_data_uri(path_or_bytes: Any) -> str:
    """Convert an image path or bytes to a base64 data URI for universal rendering on web, mobile, and desktop."""
    if not path_or_bytes:
        return ""
    if isinstance(path_or_bytes, bytes):
        b64 = base64.b64encode(path_or_bytes).decode("ascii")
        return f"data:image/png;base64,{b64}"
    if isinstance(path_or_bytes, str) and os.path.exists(path_or_bytes):
        try:
            with open(path_or_bytes, "rb") as f:
                data = f.read()
            b64 = base64.b64encode(data).decode("ascii")
            ext = os.path.splitext(path_or_bytes)[1].lower().replace(".", "") or "png"
            if ext == "jpg":
                ext = "jpeg"
            return f"data:image/{ext};base64,{b64}"
        except Exception:
            return path_or_bytes
    return str(path_or_bytes)

