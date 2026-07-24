"""
Saved Generated Videos Downloads Manager
"""

import os
import json
import time

_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOWNLOADS_DIR = os.path.join(_BASE_DIR, "downloads")
INDEX_FILE = os.path.join(DOWNLOADS_DIR, "downloads_index.json")

class DownloadsManager:
    def __init__(self):
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        self.items = self._load_index()

    def _load_index(self) -> list[dict]:
        if os.path.exists(INDEX_FILE):
            try:
                with open(INDEX_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_index(self):
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(self.items, f, indent=2)

    def add_download(self, title: str, file_path: str, duration: str = "0:30") -> dict:
        entry = {
            "id": f"dl_{int(time.time()*1000)}",
            "title": title,
            "file_path": file_path,
            "filename": os.path.basename(file_path),
            "date": time.strftime("%Y-%m-%d %H:%M"),
            "duration": duration
        }
        self.items.insert(0, entry)
        self._save_index()
        return entry

    def get_all(self) -> list[dict]:
        return self.items

    def delete_download(self, item_id: str):
        self.items = [i for i in self.items if i["id"] != item_id]
        self._save_index()
