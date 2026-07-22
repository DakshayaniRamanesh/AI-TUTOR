"""
Board State Serialization & Deserialization Model (JSON Storage)
"""

import json
import os
import time

BOARDS_DIR = os.path.abspath("storage_data/boards")

class BoardModel:
    def __init__(self, title: str = "Untitled Board", board_id: str = None):
        self.title = title
        self.board_id = board_id or f"board_{int(time.time())}"
        self.created_at = time.strftime("%Y-%m-%d %H:%M:%S")
        self.updated_at = self.created_at
        self.is_favourite = False
        self.is_shared = False
        self.items = [] # list of dict item data

    def to_dict(self) -> dict:
        return {
            "board_id": self.board_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_favourite": self.is_favourite,
            "is_shared": self.is_shared,
            "items": self.items
        }

    def save(self):
        os.makedirs(BOARDS_DIR, exist_ok=True)
        file_path = os.path.join(BOARDS_DIR, f"{self.board_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, board_id: str) -> "BoardModel":
        file_path = os.path.join(BOARDS_DIR, f"{board_id}.json")
        if not os.path.exists(file_path):
            return cls(title="New Board", board_id=board_id)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        board = cls(title=data.get("title", "Untitled"), board_id=data.get("board_id"))
        board.created_at = data.get("created_at", "")
        board.updated_at = data.get("updated_at", "")
        board.is_favourite = data.get("is_favourite", False)
        board.is_shared = data.get("is_shared", False)
        board.items = data.get("items", [])
        return board

    @classmethod
    def list_all_boards(cls) -> list[dict]:
        os.makedirs(BOARDS_DIR, exist_ok=True)
        boards = []
        for fn in os.listdir(BOARDS_DIR):
            if fn.endswith(".json"):
                fp = os.path.join(BOARDS_DIR, fn)
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    boards.append(data)
                except Exception:
                    pass
        return sorted(boards, key=lambda x: x.get("updated_at", ""), reverse=True)
