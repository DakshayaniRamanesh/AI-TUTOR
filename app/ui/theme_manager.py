"""
Global Theme Manager for Kestrel AI Notebook
Manages Light / Dark mode themes and persists user preference.
"""

import os
import json
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor

class ThemeManager(QObject):
    theme_changed = pyqtSignal(str) # Emits "light" or "dark"

    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "storage_data"
        )
        self.config_file = os.path.join(self.config_dir, "theme_config.json")
        self._current_theme = self._load_saved_theme()

    def _load_saved_theme(self) -> str:
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    theme = data.get("theme", "light")
                    if theme in ["light", "dark"]:
                        return theme
        except Exception:
            pass
        return "light"

    def _save_theme(self):
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump({"theme": self._current_theme}, f)
        except Exception as e:
            print(f"[ThemeManager] Error saving theme config: {e}")

    @property
    def current_theme(self) -> str:
        return self._current_theme

    @current_theme.setter
    def current_theme(self, value: str):
        if value in ["light", "dark"] and value != self._current_theme:
            self._current_theme = value
            self._save_theme()
            self.theme_changed.emit(value)

    def toggle_theme(self) -> str:
        new_theme = "dark" if self._current_theme == "light" else "light"
        self.current_theme = new_theme
        return new_theme

    def is_dark(self) -> bool:
        return self._current_theme == "dark"

    def get_colors(self) -> dict:
        if self.is_dark():
            return {
                "bg_app": "#0f0f11",
                "bg_card": "#18181b",
                "bg_sidebar": "#121215",
                "bg_titlebar": "#1c1c20",
                "bg_toolbar": "#18181b",
                "text_primary": "#f4f4f5",
                "text_secondary": "#a1a1aa",
                "border_color": "#27272a",
                "canvas_bg": "#18181c",
                "canvas_grid": "#27272a",
                "accent": "#38bdf8",
                "accent_hover": "#0284c7",
                "panel_card_bg": "#27272a",
                "input_bg": "#27272a",
                "editor_bg": "#121215"
            }
        else:
            return {
                "bg_app": "#f2f2f7",
                "bg_card": "#ffffff",
                "bg_sidebar": "#f8f8fa",
                "bg_titlebar": "#f2f2f7",
                "bg_toolbar": "#ffffff",
                "text_primary": "#1c1c1e",
                "text_secondary": "#6e6e73",
                "border_color": "#d1d1d6",
                "canvas_bg": "#fcfbf7",
                "canvas_grid": "#e5e5ea",
                "accent": "#007aff",
                "accent_hover": "#0056b3",
                "panel_card_bg": "#ffffff",
                "input_bg": "#ffffff",
                "editor_bg": "#f8f9fa"
            }
