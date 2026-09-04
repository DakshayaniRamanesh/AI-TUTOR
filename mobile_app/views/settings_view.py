"""
iOS Settings View for Kestrel Mobile
"""

import flet as ft
from mobile_app import storage
from mobile_app.theme import (
    IOS_BLUE, IOS_GREEN, IOS_ORANGE, IOS_PINK,
    IOS_DARK_TEXT_PRIMARY, IOS_DARK_TEXT_SECONDARY,
    create_ios_card, create_ios_button
)

def build_settings_view(page: ft.Page, update_app_cb=None) -> ft.Control:
    dark = page.theme_mode != ft.ThemeMode.LIGHT
    text_color = IOS_DARK_TEXT_PRIMARY if dark else "#000000"
    sec_color = IOS_DARK_TEXT_SECONDARY if dark else "#6C6C70"

    settings = storage.get_settings()
    stats = storage.get_stats()

    api_key_input = ft.TextField(
        label="Gemini API Key",
        value=settings.get("gemini_api_key", ""),
        password=True,
        can_reveal_password=True,
        text_size=12,
        hint_text="AI key from Google AI Studio"
    )

    def save_key_action(e):
        k = api_key_input.value.strip()
        storage.save_settings({"gemini_api_key": k})
        page.snack_bar = ft.SnackBar(ft.Text("Gemini API Key saved!"), bgcolor="#111111")
        page.snack_bar.open = True
        page.update()

    def toggle_theme_action(e):
        page.theme_mode = ft.ThemeMode.LIGHT if page.theme_mode == ft.ThemeMode.DARK else ft.ThemeMode.DARK
        storage.save_settings({"theme": "light" if page.theme_mode == ft.ThemeMode.LIGHT else "dark"})
        if update_app_cb:
            update_app_cb()

    header = ft.Column([
        ft.Text("SETTINGS", size=11, weight=ft.FontWeight.W_700, color=sec_color),
        ft.Text("App & Preferences", size=24, weight=ft.FontWeight.BOLD, color=text_color),
    ], spacing=0)

    theme_card = create_ios_card(
        content=ft.Row([
            ft.Row([
                ft.Icon(ft.Icons.DARK_MODE_ROUNDED, color=text_color, size=20),
                ft.Text("Dark Mode", size=14, weight=ft.FontWeight.W_600, color=text_color),
            ], spacing=10),
            ft.Switch(
                value=dark,
                on_change=toggle_theme_action,
                active_color="#111111"
            )
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        padding=12, dark=dark
    )

    api_card = create_ios_card(
        content=ft.Column([
            ft.Text("GEMINI API CONFIGURATION", size=12, weight=ft.FontWeight.W_700, color=sec_color),
            api_key_input,
            create_ios_button("Save API Key", icon=ft.Icons.KEY_ROUNDED, color="#111111", on_click=save_key_action, height=38)
        ], spacing=10),
        padding=14, dark=dark
    )

    storage_card = create_ios_card(
        content=ft.Column([
            ft.Text("STORAGE USAGE STATS", size=12, weight=ft.FontWeight.W_700, color=sec_color),
            ft.Text(f"• PDFs Saved: {stats.get('pdfs_saved', 0)}", size=12, color=text_color),
            ft.Text(f"• Photo Scans: {stats.get('photos_captured', 0)}", size=12, color=text_color),
            ft.Text(f"• Notes & Flashcards: {stats.get('notes_created', 0)}", size=12, color=text_color),
            ft.Text(f"Local Path: {storage.STORAGE_ROOT}", size=10, color=sec_color),
        ], spacing=6),
        padding=14, dark=dark
    )

    about_card = create_ios_card(
        content=ft.Column([
            ft.Text("Kestrel Mobile iOS", size=14, weight=ft.FontWeight.BOLD, color=text_color),
            ft.Text("Version 1.0 • Built with Python & Flet", size=11, color=sec_color),
            ft.Text("Designed for authentic iOS mobile screen ratio & HIG aesthetics.", size=11, color=sec_color),
        ], spacing=4),
        padding=14, dark=dark
    )

    return ft.ListView([
        header,
        theme_card,
        api_card,
        storage_card,
        about_card,
        ft.Container(height=40)
    ], spacing=14, padding=16, expand=True)
