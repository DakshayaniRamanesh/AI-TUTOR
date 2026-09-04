"""
Notebook Persistence & Storage Manager
Handles lightweight index listing, full notebook serialization, folder hierarchy, and file I/O with error safety.

Folder data model (folders_index.json):
  [{id, name, parent_id, created_at, updated_at}, ...]

Notebook index entry:
  {id, name, folder_id, created_at, updated_at}
"""

import os
import json
import time
import traceback

_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BOARDS_DIR = os.path.join(_BASE_DIR, "storage_data", "boards")
INDEX_FILE = os.path.join(_BASE_DIR, "storage_data", "notebooks_index.json")
FOLDERS_FILE = os.path.join(_BASE_DIR, "storage_data", "folders_index.json")

MAX_FOLDER_DEPTH = 10


class NotebookStorage:
    @staticmethod
    def _ensure_dirs():
        os.makedirs(BOARDS_DIR, exist_ok=True)

    # ─── Notebook Index ────────────────────────────────────────────────────────

    @classmethod
    def get_index(cls) -> list[dict]:
        """
        Loads the lightweight notebook index. Returns list sorted by updated_at desc.
        Each entry includes folder_id (None = root).
        """
        cls._ensure_dirs()
        if not os.path.exists(INDEX_FILE):
            return []
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                index = json.load(f)
            # Backfill folder_id for legacy entries
            for entry in index:
                entry.setdefault("folder_id", None)
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

    # ─── Folder Index ─────────────────────────────────────────────────────────

    @classmethod
    def get_folders(cls) -> list[dict]:
        """
        Returns the full flat folder list. Each entry: {id, name, parent_id, created_at, updated_at}.
        Parent_id=None means root-level folder.
        """
        cls._ensure_dirs()
        if not os.path.exists(FOLDERS_FILE):
            return []
        try:
            with open(FOLDERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    @classmethod
    def _save_folders(cls, folders: list[dict]):
        cls._ensure_dirs()
        with open(FOLDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(folders, f, indent=2)

    @classmethod
    def get_folder_tree(cls) -> list[dict]:
        """
        Returns full folder list sorted by name for building trees.
        """
        return sorted(cls.get_folders(), key=lambda f: f.get("name", "").lower())

    @classmethod
    def create_folder(cls, name: str, parent_id: str = None) -> dict:
        """
        Creates a new folder. parent_id=None creates a root-level folder.
        Enforces MAX_FOLDER_DEPTH=10.
        """
        if parent_id:
            depth = cls._get_folder_depth(parent_id)
            if depth >= MAX_FOLDER_DEPTH:
                raise ValueError(f"Maximum folder nesting depth ({MAX_FOLDER_DEPTH}) reached.")

        folder_id = f"fld_{int(time.time()*1000)}"
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        folder = {
            "id": folder_id,
            "name": name.strip() or "New Folder",
            "parent_id": parent_id,
            "created_at": now_str,
            "updated_at": now_str,
        }
        folders = cls.get_folders()
        folders.append(folder)
        cls._save_folders(folders)
        return folder

    @classmethod
    def rename_folder(cls, folder_id: str, new_name: str) -> bool:
        folders = cls.get_folders()
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        for f in folders:
            if f["id"] == folder_id:
                f["name"] = new_name.strip() or f["name"]
                f["updated_at"] = now_str
                cls._save_folders(folders)
                return True
        return False

    @classmethod
    def delete_folder_cascade(cls, folder_id: str) -> dict:
        """
        Cascade-deletes a folder and all its descendants (sub-folders + notebooks inside them).
        Returns summary dict: {deleted_folders: int, deleted_notebooks: int}
        """
        all_folders = cls.get_folders()
        all_notebooks = cls.get_index()

        # Collect all descendant folder ids
        desc_ids = cls._get_all_descendant_ids(folder_id, all_folders)
        target_ids = {folder_id} | desc_ids

        # Delete notebook files and entries for notebooks in any target folder
        deleted_nbs = 0
        remaining_nbs = []
        for nb in all_notebooks:
            if nb.get("folder_id") in target_ids:
                f_path = os.path.join(BOARDS_DIR, f"{nb['id']}.json")
                if os.path.exists(f_path):
                    try:
                        os.remove(f_path)
                    except Exception:
                        pass
                deleted_nbs += 1
            else:
                remaining_nbs.append(nb)

        # Remove target folders
        remaining_folders = [f for f in all_folders if f["id"] not in target_ids]

        cls._save_index(remaining_nbs)
        cls._save_folders(remaining_folders)
        return {"deleted_folders": len(target_ids), "deleted_notebooks": deleted_nbs}

    @classmethod
    def get_cascade_preview(cls, folder_id: str) -> dict:
        """
        Returns a preview of what cascade-delete will remove without deleting anything.
        Returns {folder_names: [str], notebook_names: [str]}
        """
        all_folders = cls.get_folders()
        all_notebooks = cls.get_index()

        desc_ids = cls._get_all_descendant_ids(folder_id, all_folders)
        target_ids = {folder_id} | desc_ids

        folder_names = [f["name"] for f in all_folders if f["id"] in target_ids]
        notebook_names = [nb["name"] for nb in all_notebooks if nb.get("folder_id") in target_ids]
        return {"folder_names": folder_names, "notebook_names": notebook_names}

    @classmethod
    def move_folder(cls, folder_id: str, new_parent_id: str = None) -> bool:
        """
        Moves a folder to a new parent (None = root level).
        Blocks if new_parent_id is a descendant of folder_id (circular reference).
        """
        if new_parent_id is not None:
            all_folders = cls.get_folders()
            desc_ids = cls._get_all_descendant_ids(folder_id, all_folders)
            if new_parent_id in desc_ids or new_parent_id == folder_id:
                raise ValueError("Cannot move a folder into its own descendant (circular reference).")

        folders = cls.get_folders()
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        for f in folders:
            if f["id"] == folder_id:
                f["parent_id"] = new_parent_id
                f["updated_at"] = now_str
                cls._save_folders(folders)
                return True
        return False

    # ─── Notebook Operations ──────────────────────────────────────────────────

    @classmethod
    def create_notebook(cls, name: str = "Untitled Notebook", folder_id: str = None) -> dict:
        """
        Creates a new notebook entry in index and saves a blank board file.
        """
        cls._ensure_dirs()
        nb_id = f"nb_{int(time.time()*1000)}"
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        meta = {
            "id": nb_id,
            "name": name or "Untitled Notebook",
            "folder_id": folder_id,
            "created_at": now_str,
            "updated_at": now_str,
        }

        file_path = os.path.join(BOARDS_DIR, f"{nb_id}.json")
        board_payload = {
            "board_id": nb_id,
            "title": meta["name"],
            "created_at": now_str,
            "updated_at": now_str,
            "items": [],
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(board_payload, f, indent=2)

        index = cls.get_index()
        index.append(meta)
        cls._save_index(index)
        return meta

    @classmethod
    def save_notebook(cls, notebook_id: str, name: str, items_data: list) -> dict:
        """
        Saves full canvas content for notebook_id and updates index entry.
        Always UPDATES the existing record — never creates a duplicate notebook.
        Raises on write failure (caller should handle and surface to user).
        """
        cls._ensure_dirs()
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        file_path = os.path.join(BOARDS_DIR, f"{notebook_id}.json")
        payload = {
            "board_id": notebook_id,
            "title": name,
            "updated_at": now_str,
            "items": items_data or [],
        }
        tmp_path = file_path + ".tmp"
        try:
            # Large boards contain thousands of stroke points and sometimes base64 images.
            # Compact JSON cuts autosave allocations and disk I/O substantially.
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp_path, file_path)
        except Exception as err:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            print(f"[NotebookStorage] ERROR writing notebook {notebook_id} to disk: {err}")
            traceback.print_exc()
            raise

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
                "folder_id": None,
                "created_at": now_str,
                "updated_at": now_str,
            })

        cls._save_index(index)
        return payload


    @classmethod
    def rename_notebook(cls, notebook_id: str, new_name: str) -> bool:
        index = cls.get_index()
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        for entry in index:
            if entry["id"] == notebook_id:
                entry["name"] = new_name.strip() or entry["name"]
                entry["updated_at"] = now_str
                cls._save_index(index)
                return True
        return False

    @classmethod
    def move_notebook(cls, notebook_id: str, target_folder_id: str = None) -> bool:
        """
        Moves a notebook into a folder (target_folder_id=None → root level).
        """
        index = cls.get_index()
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        for entry in index:
            if entry["id"] == notebook_id:
                entry["folder_id"] = target_folder_id
                entry["updated_at"] = now_str
                cls._save_index(index)
                return True
        return False

    @classmethod
    def load_notebook(cls, notebook_id: str) -> dict:
        cls._ensure_dirs()
        file_path = os.path.join(BOARDS_DIR, f"{notebook_id}.json")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Notebook {notebook_id} file not found.")
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def delete_notebook(cls, notebook_id: str) -> bool:
        cls._ensure_dirs()
        file_path = os.path.join(BOARDS_DIR, f"{notebook_id}.json")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as err:
                print(f"[NotebookStorage] Notice deleting file: {err}")

        index = cls.get_index()
        new_index = [entry for entry in index if entry["id"] != notebook_id]
        cls._save_index(new_index)
        return True

    # ─── Breadcrumb ───────────────────────────────────────────────────────────

    @classmethod
    def get_breadcrumb_path(cls, folder_id: str = None) -> list[dict]:
        """
        Returns the breadcrumb path from root to the given folder.
        Returns [{id: None, name: 'Notebooks'}, {id: 'fld_...', name: 'Maths'}, ...]
        """
        path = [{"id": None, "name": "Notebooks"}]
        if not folder_id:
            return path

        all_folders = {f["id"]: f for f in cls.get_folders()}
        chain = []
        current_id = folder_id
        visited = set()

        while current_id and current_id not in visited:
            visited.add(current_id)
            folder = all_folders.get(current_id)
            if not folder:
                break
            chain.append({"id": folder["id"], "name": folder["name"]})
            current_id = folder.get("parent_id")

        path.extend(reversed(chain))
        return path

    # ─── Internal Helpers ─────────────────────────────────────────────────────

    @classmethod
    def _get_all_descendant_ids(cls, folder_id: str, all_folders: list[dict]) -> set:
        """Returns the set of all descendant folder IDs (not including folder_id itself)."""
        children_map = {}
        for f in all_folders:
            pid = f.get("parent_id")
            children_map.setdefault(pid, []).append(f["id"])

        result = set()
        queue = list(children_map.get(folder_id, []))
        while queue:
            cid = queue.pop()
            result.add(cid)
            queue.extend(children_map.get(cid, []))
        return result

    @classmethod
    def _get_folder_depth(cls, folder_id: str) -> int:
        """Returns depth of a folder (root children = depth 1)."""
        all_folders = {f["id"]: f for f in cls.get_folders()}
        depth = 0
        current_id = folder_id
        visited = set()
        while current_id and current_id not in visited:
            visited.add(current_id)
            folder = all_folders.get(current_id)
            if not folder:
                break
            current_id = folder.get("parent_id")
            depth += 1
        return depth
