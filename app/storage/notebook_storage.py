"""
Notebook Persistence & Storage Manager
Handles lightweight index listing, full notebook serialization, and file I/O operations with error safety.
"""

import os
import json
import time

_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BOARDS_DIR = os.path.join(_BASE_DIR, "storage_data", "boards")
INDEX_FILE = os.path.join(_BASE_DIR, "storage_data", "notebooks_index.json")

class NotebookStorage:
    @staticmethod
    def _ensure_dirs():
        os.makedirs(BOARDS_DIR, exist_ok=True)

    @classmethod
    def get_index(cls) -> list[dict]:
        """
        Loads the lightweight index list (id, name, created_at, updated_at).
        Returns a list of dicts sorted by updated_at descending.
        """
        cls._ensure_dirs()
        if not os.path.exists(INDEX_FILE):
            return []
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                index = json.load(f)
            return sorted(index, key=lambda x: x.get("updated_at", ""), reverse=True)
        except Exception as err:
            print(f"[NotebookStorage] Notice reading index: {err}")
            return []

    @classmethod
    def _save_index(cls, index: list[dict]):
        cls._ensure_dirs()
        try:
            with open(INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2)
        except Exception as err:
            print(f"[NotebookStorage] Notice saving index: {err}")
            raise err

    @classmethod
    def create_notebook(cls, name: str = "Untitled Notebook") -> dict:
        """
        Creates a new notebook entry in index and saves a blank board file.
        """
        cls._ensure_dirs()
        nb_id = f"nb_{int(time.time()*1000)}"
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        
        meta = {
            "id": nb_id,
            "name": name or "Untitled Notebook",
            "created_at": now_str,
            "updated_at": now_str
        }

        # Save blank file
        file_path = os.path.join(BOARDS_DIR, f"{nb_id}.json")
        board_payload = {
            "board_id": nb_id,
            "title": meta["name"],
            "created_at": now_str,
            "updated_at": now_str,
            "items": []
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(board_payload, f, indent=2)

        # Update index
        index = cls.get_index()
        index.append(meta)
        cls._save_index(index)

        return meta

    @classmethod
    def save_notebook(cls, notebook_id: str, name: str, items_data: list) -> dict:
        """
        Saves full canvas content for notebook_id and updates index entry.
        """
        cls._ensure_dirs()
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. Update board JSON file
        file_path = os.path.join(BOARDS_DIR, f"{notebook_id}.json")
        payload = {
            "board_id": notebook_id,
            "title": name,
            "updated_at": now_str,
            "items": items_data or []
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        # 2. Update index
        index = cls.get_index()
        found = False
        for entry in index:
            if entry["id"] == notebook_id:
                entry["name"] = name
                entry["updated_at"] = now_str
                found = True
                break
                
        if not found:
            index.append({
                "id": notebook_id,
                "name": name,
                "created_at": now_str,
                "updated_at": now_str
            })

        cls._save_index(index)
        return payload

    @classmethod
    def load_notebook(cls, notebook_id: str) -> dict:
        """
        Loads the full payload (items, title, etc.) for notebook_id.
        """
        cls._ensure_dirs()
        file_path = os.path.join(BOARDS_DIR, f"{notebook_id}.json")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Notebook {notebook_id} file not found.")
            
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def delete_notebook(cls, notebook_id: str) -> bool:
        """
        Deletes a notebook JSON file and removes it from index.
        """
        cls._ensure_dirs()
        file_path = os.path.join(BOARDS_DIR, f"{notebook_id}.json")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as err:
                print(f"[NotebookStorage] Notice deleting file: {err}")

        # Update index
        index = cls.get_index()
        new_index = [entry for entry in index if entry["id"] != notebook_id]
        cls._save_index(new_index)
        return True
