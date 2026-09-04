"""
Kestrel Bridge: Bidirectional synchronization between Kestrel Desktop and Mobile iOS App.
Bridges SQLite database (storage_data/kestrel.db) and boards (storage_data/boards/).
"""

import os
import sqlite3
import json
import uuid
import time
import base64
from datetime import datetime
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KESTREL_DB_PATH = os.path.join(BASE_DIR, "storage_data", "kestrel.db")
KESTREL_BOARDS_DIR = os.path.join(BASE_DIR, "storage_data", "boards")
KESTREL_NOTEBOOKS_INDEX = os.path.join(BASE_DIR, "storage_data", "notebooks_index.json")

def get_db_connection() -> sqlite3.Connection:
    """Returns a connection to Kestrel's shared SQLite database."""
    os.makedirs(os.path.dirname(KESTREL_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(KESTREL_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_user_and_subject() -> tuple[str, str]:
    """
    Ensures that a user and a sync subject exist in Kestrel DB.
    Returns (user_id, subject_id).
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Get or create user
    c.execute("SELECT id FROM users LIMIT 1")
    row = c.fetchone()
    if row:
        user_id = row["id"]
    else:
        user_id = uuid.uuid4().hex
        c.execute("INSERT INTO users (id, username, created_at) VALUES (?, ?, ?)",
                  (user_id, "student_01", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

    # 2. Get or create subject
    c.execute("SELECT id FROM subjects WHERE user_id = ? LIMIT 1", (user_id,))
    row = c.fetchone()
    if row:
        subject_id = row["id"]
    else:
        subject_id = uuid.uuid4().hex
        c.execute("INSERT INTO subjects (id, user_id, name, created_at) VALUES (?, ?, ?, ?)",
                  (subject_id, user_id, "General & Mobile Sync", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

    conn.close()
    return user_id, subject_id

def sync_pdf_to_kestrel_desktop(title: str, pdf_path: str) -> Optional[str]:
    """
    Registers a PDF into Kestrel Desktop's materials library (REFERENCE PDFS).
    Kestrel desktop app will instantly see this under Reference PDFs!
    """
    if not os.path.exists(pdf_path):
        return None
    try:
        _, subject_id = ensure_user_and_subject()
        conn = get_db_connection()
        c = conn.cursor()

        # Check if already registered
        c.execute("SELECT id FROM materials WHERE file_path = ? OR filename = ?", (pdf_path, title))
        existing = c.fetchone()
        if existing:
            conn.close()
            return existing["id"]

        mat_id = uuid.uuid4().hex
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            "INSERT INTO materials (id, subject_id, filename, file_path, created_at) VALUES (?, ?, ?, ?, ?)",
            (mat_id, subject_id, title, pdf_path, now_str)
        )
        conn.commit()
        conn.close()
        print(f"[KestrelBridge] Synced PDF '{title}' to Kestrel Desktop DB (material_id: {mat_id})")
        return mat_id
    except Exception as e:
        print(f"[KestrelBridge] Error syncing PDF to Kestrel: {e}")
        return None

def sync_image_to_kestrel_board(image_path: str, title: str) -> Optional[str]:
    """
    Converts captured image/scan into an ImageItem placed on Kestrel's whiteboard board.
    When Kestrel desktop app opens this board, the image appears right on the canvas!
    """
    if not os.path.exists(image_path):
        return None
    try:
        user_id, subject_id = ensure_user_and_subject()
        os.makedirs(KESTREL_BOARDS_DIR, exist_ok=True)

        board_id = "board_mobile_sync"
        board_file = os.path.join(KESTREL_BOARDS_DIR, f"{board_id}.json")

        # Encode image to base64
        with open(image_path, "rb") as f:
            b64_img = base64.b64encode(f.read()).decode("utf-8")

        # Load or initialize board
        if os.path.exists(board_file):
            try:
                with open(board_file, "r", encoding="utf-8") as f:
                    board_data = json.load(f)
            except Exception:
                board_data = {"board_id": board_id, "title": "Mobile Scans & Notes", "items": []}
        else:
            board_data = {"board_id": board_id, "title": "Mobile Scans & Notes", "items": []}

        # Calculate positioning to stack or arrange items
        items = board_data.get("items", [])
        offset_y = len(items) * 220 + 40

        new_image_item = {
            "type": "ImageItem",
            "x": 80.0,
            "y": float(offset_y),
            "scale": 0.6,
            "image_b64": b64_img,
            "title": title,
            "z_value": float(len(items) + 1)
        }
        items.append(new_image_item)
        board_data["items"] = items
        board_data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

        with open(board_file, "w", encoding="utf-8") as f:
            json.dump(board_data, f, indent=2)

        # Update Kestrel notebooks table in SQLite
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM notebooks WHERE id = ?", (board_id,))
        if not c.fetchone():
            c.execute(
                "INSERT INTO notebooks (id, subject_id, name, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (board_id, subject_id, "Mobile Scans & Notes", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
        conn.close()

        # Update notebooks_index.json if used by NotebookStorage
        _update_notebooks_index(board_id, "Mobile Scans & Notes")

        print(f"[KestrelBridge] Synced photo '{title}' onto Kestrel board '{board_id}'")
        return board_id
    except Exception as e:
        print(f"[KestrelBridge] Error syncing image to Kestrel board: {e}")
        return None

def _update_notebooks_index(board_id: str, name: str):
    """Updates Kestrel's notebooks_index.json so desktop dashboard recognizes it."""
    try:
        index = []
        if os.path.exists(KESTREL_NOTEBOOKS_INDEX):
            with open(KESTREL_NOTEBOOKS_INDEX, "r", encoding="utf-8") as f:
                index = json.load(f)
        
        # Check if already present
        existing = next((item for item in index if item.get("id") == board_id), None)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        if existing:
            existing["updated_at"] = now_str
        else:
            index.insert(0, {
                "id": board_id,
                "name": name,
                "folder_id": None,
                "created_at": now_str,
                "updated_at": now_str
            })
        with open(KESTREL_NOTEBOOKS_INDEX, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2)
    except Exception as e:
        print(f"[KestrelBridge] Error updating notebooks index: {e}")

def get_kestrel_desktop_materials() -> List[Dict[str, Any]]:
    """
    Fetches all Reference PDFs and study materials saved from Kestrel Desktop.
    """
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, subject_id, filename, file_path, created_at FROM materials ORDER BY created_at DESC")
        rows = c.fetchall()
        materials = []
        for r in rows:
            materials.append({
                "id": f"kestrel_mat_{r['id']}",
                "title": r["filename"],
                "file_path": r["file_path"],
                "created_at": str(r["created_at"])[:16],
                "type": "pdf",
                "source": "kestrel_desktop",
                "tags": ["Kestrel Desktop", "Reference PDF"]
            })
        conn.close()
        return materials
    except Exception as e:
        print(f"[KestrelBridge] Error loading materials from Kestrel DB: {e}")
        return []

def get_kestrel_desktop_boards() -> List[Dict[str, Any]]:
    """
    Fetches all whiteboard boards/notebooks created in Kestrel Desktop.
    """
    try:
        boards = []
        if os.path.exists(KESTREL_BOARDS_DIR):
            for fname in os.listdir(KESTREL_BOARDS_DIR):
                if fname.endswith(".json"):
                    fp = os.path.join(KESTREL_BOARDS_DIR, fname)
                    try:
                        with open(fp, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            boards.append({
                                "id": f"board_{data.get('board_id', fname[:-5])}",
                                "title": data.get("title", "Untitled Board"),
                                "file_path": fp,
                                "created_at": data.get("created_at", "")[:16],
                                "item_count": len(data.get("items", [])),
                                "type": "board",
                                "source": "kestrel_desktop",
                                "tags": ["Kestrel Board", "Whiteboard"]
                            })
                    except Exception:
                        pass
        return boards
    except Exception as e:
        print(f"[KestrelBridge] Error loading boards: {e}")
        return []

def get_sync_summary() -> Dict[str, Any]:
    """Returns summary stats of synced desktop items."""
    materials = get_kestrel_desktop_materials()
    boards = get_kestrel_desktop_boards()
    return {
        "desktop_materials_count": len(materials),
        "desktop_boards_count": len(boards),
        "synced": True,
        "last_sync": datetime.now().strftime("%H:%M:%S")
    }
