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
                # ── Backgrounds ──────────────────────────────────────────
                "bg_app":       "#0a0a0f",
                "bg_card":      "#111116",
                "bg_sidebar":   "#080808",
                "bg_titlebar":  "#0a0a0f",
                "bg_toolbar":   "#111116",
                # ── Text ─────────────────────────────────────────────────
                "text_primary":   "#f0f0f0",
                "text_secondary": "#888888",
                # ── Borders ──────────────────────────────────────────────
                "border_color": "#252525",
                # ── Canvas ───────────────────────────────────────────────
                "canvas_bg":   "#0f0f14",
                "canvas_grid": "#1a1a1f",
                # ── Accent (monochrome: white in dark mode) ───────────────
                "accent":       "#f0f0f0",
                "accent_hover": "#cccccc",
                "accent_text":  "#0a0a0a",   # text ON the accent fill
                # ── Surfaces ─────────────────────────────────────────────
                "panel_card_bg": "#1a1a1f",
                "input_bg":      "#1a1a1f",
                "editor_bg":     "#0a0a0f",
                # ── Sidebar icons ─────────────────────────────────────────
                "sidebar_icon":        "#6a6a7a",
                "sidebar_active_bg":   "#0a0a0f",
                "sidebar_active_icon": "#f0f0f0",
                # ── Tag pills (subtle, muted) ─────────────────────────────
                "tag_pill_bg":   "#252525",
                "tag_pill_text": "#888888",
                # ── Typography ───────────────────────────────────────────
                "mono_font": '"Courier New", "Consolas", "Lucida Console", monospace',
            }
        else:
            return {
                # ── Backgrounds ──────────────────────────────────────────
                "bg_app":       "#ffffff",
                "bg_card":      "#ffffff",
                "bg_sidebar":   "#0d0d12",   # dark sidebar in light mode (Figma ref)
                "bg_titlebar":  "#ffffff",
                "bg_toolbar":   "#ffffff",
                # ── Text ─────────────────────────────────────────────────
                "text_primary":   "#0a0a0a",
                "text_secondary": "#888888",
                # ── Borders ──────────────────────────────────────────────
                "border_color": "#e0e0e0",
                # ── Canvas ───────────────────────────────────────────────
                "canvas_bg":   "#fafafa",
                "canvas_grid": "#e8e8e8",
                # ── Accent (monochrome: black in light mode) ──────────────
                "accent":       "#0a0a0a",
                "accent_hover": "#333333",
                "accent_text":  "#ffffff",   # text ON the accent fill
                # ── Surfaces ─────────────────────────────────────────────
                "panel_card_bg": "#f5f5f5",
                "input_bg":      "#ffffff",
                "editor_bg":     "#fafafa",
                # ── Sidebar icons ─────────────────────────────────────────
                "sidebar_icon":        "#9a9aaa",
                "sidebar_active_bg":   "#1e1e26",
                "sidebar_active_icon": "#ffffff",
                # ── Tag pills (subtle, muted) ─────────────────────────────
                "tag_pill_bg":   "#f0f0f0",
                "tag_pill_text": "#555555",
                # ── Typography ───────────────────────────────────────────
                "mono_font": '"Courier New", "Consolas", "Lucida Console", monospace',
            }
