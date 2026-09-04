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

    # ── Desktop Canvas Connection & Diagnostic Card ────────────────────────
    from mobile_app import kestrel_bridge
    conn_info = kestrel_bridge.check_desktop_connection()

    diag_text = ft.Text(
        f"Status: {'ONLINE (Connected to ' + conn_info.get('active_board_title', 'Canvas') + ')' if conn_info.get('desktop_online') else 'OFFLINE (Queue Active)'}\n"
        f"Storage Link: {'Connected' if conn_info.get('storage_connected') else 'Error'}\n"
        f"Canvas Items: {conn_info.get('canvas_items_count', 0)}\n"
        f"Pending Queue: {conn_info.get('pending_inbox_count', 0)} item(s)",
        size=11,
        color=text_color
    )

    def run_diag_action(e):
        fresh = kestrel_bridge.check_desktop_connection()
        online = fresh.get("desktop_online", False)
        diag_text.value = (
            f"Status: {'ONLINE (Connected to ' + fresh.get('active_board_title', 'Canvas') + ')' if online else 'OFFLINE (Queue Active)'}\n"
            f"Storage Link: {'Connected' if fresh.get('storage_connected') else 'Error'}\n"
            f"Canvas Items: {fresh.get('canvas_items_count', 0)}\n"
            f"Pending Queue: {fresh.get('pending_inbox_count', 0)} item(s)\n"
            f"Last Ping: {fresh.get('last_ping')}"
        )
        page.snack_bar = ft.SnackBar(
            ft.Text(f"Connection Diagnostic: {'SUCCESS - Canvas is ONLINE!' if online else 'Storage connected. Desktop Canvas currently offline.'}"),
            bgcolor="#10B981" if online else "#1F2937"
        )
        page.snack_bar.open = True
        try:
            diag_text.update()
            page.update()
        except Exception:
            pass

    def send_note_action(e):
        kestrel_bridge.send_test_item_to_canvas("sticky_note")
        page.snack_bar = ft.SnackBar(ft.Text("Test Sticky Note queued to Desktop Canvas!"), bgcolor="#111111")
        page.snack_bar.open = True
        try:
            page.update()
        except Exception:
            pass

    def send_scan_action(e):
        kestrel_bridge.send_test_item_to_canvas("image")
        page.snack_bar = ft.SnackBar(ft.Text("Test Photo Scan queued to Desktop Canvas!"), bgcolor="#111111")
        page.snack_bar.open = True
        try:
            page.update()
        except Exception:
            pass

    canvas_conn_card = create_ios_card(
        content=ft.Column([
            ft.Row([
                ft.Row([
                    ft.Icon(ft.Icons.SCREEN_SHARE_ROUNDED, color="#10B981" if conn_info.get("desktop_online") else "#F59E0B", size=20),
                    ft.Text("DESKTOP & CANVAS CONNECTION", size=12, weight=ft.FontWeight.W_700, color=sec_color),
                ], spacing=8),
                ft.Container(
                    content=ft.Text("ONLINE" if conn_info.get("desktop_online") else "STANDBY", size=9, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                    bgcolor="#10B981" if conn_info.get("desktop_online") else "#F59E0B",
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=4
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            diag_text,
            ft.Row([
                ft.OutlinedButton("Check Connection", icon=ft.Icons.REFRESH_ROUNDED, on_click=run_diag_action),
                ft.ElevatedButton("Send Test Note", icon=ft.Icons.NOTE_ALT_ROUNDED, on_click=send_note_action, bgcolor="#111111" if not dark else "#2C2C2E", color="#FFFFFF"),
                ft.ElevatedButton("Send Test Photo", icon=ft.Icons.IMAGE_ROUNDED, on_click=send_scan_action, bgcolor="#111111" if not dark else "#2C2C2E", color="#FFFFFF"),
            ], wrap=True, spacing=6)
        ], spacing=10),
        padding=14, dark=dark
    )

    about_card = create_ios_card(
        content=ft.Column([
            ft.Text("Kestrel Mobile iOS", size=14, weight=ft.FontWeight.BOLD, color=text_color),
            ft.Text("Version 1.0 • Built with Python & Flet", size=11, color=sec_color),
            ft.Text("Live bidirectional synchronization with Kestrel Desktop Canvas.", size=11, color=sec_color),
        ], spacing=4),
        padding=14, dark=dark
    )

    return ft.ListView([
        header,
        canvas_conn_card,
        theme_card,
        api_card,
        storage_card,
        about_card,
        ft.Container(height=40)
    ], spacing=14, padding=16, expand=True)
