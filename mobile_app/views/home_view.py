"""
iOS Home View for Kestrel Mobile
"""

import os
import flet as ft
from mobile_app import storage
from mobile_app.theme import (
    IOS_BLUE, IOS_GREEN, IOS_INDIGO, IOS_ORANGE, IOS_PURPLE,
    IOS_DARK_CARD, IOS_DARK_TEXT_PRIMARY, IOS_DARK_TEXT_SECONDARY,
    create_ios_card, create_ios_button
)

def build_home_view(page: ft.Page, navigate_to_tab_cb) -> ft.Control:
    stats = storage.get_stats()
    items = storage.get_all_items()
    dark = page.theme_mode != ft.ThemeMode.LIGHT
    text_color = IOS_DARK_TEXT_PRIMARY if dark else "#000000"
    sec_color = IOS_DARK_TEXT_SECONDARY if dark else "#6C6C70"

    # Header / Greeting
    header_col = ft.Column(
        controls=[
            ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text("STUDY COMPANION", size=11, weight=ft.FontWeight.W_700, color=sec_color),
                            ft.Text("Kestrel iOS", size=28, weight=ft.FontWeight.BOLD, color=text_color),
                        ],
                        spacing=0,
                    ),
                    ft.Container(
                        content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=text_color, size=20),
                        bgcolor="#E5E5EA" if not dark else "#2C2C2E",
                        padding=10,
                        border_radius=20,
                    )
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
        ],
        spacing=4,
    )

    # Quick Action Buttons Grid (2x2)
    def action_card(title: str, subtitle: str, icon: str, color: str, tab_index: int):
        return create_ios_card(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(icon, color="#FFFFFF", size=20),
                        bgcolor=color,
                        padding=10,
                        border_radius=14,
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(title, size=14, weight=ft.FontWeight.W_700, color=text_color),
                            ft.Text(subtitle, size=11, color=sec_color),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=sec_color, size=18)
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=12,
            dark=dark,
            on_click=lambda _: navigate_to_tab_cb(tab_index)
        )

    quick_actions = ft.Column(
        controls=[
            ft.Text("QUICK ACTIONS", size=12, weight=ft.FontWeight.W_600, color=sec_color),
            ft.Column(
                controls=[
                    action_card("Save & Manage PDF", "Import, compile & read PDFs", ft.Icons.PICTURE_IN_PICTURE_ALT_ROUNDED, "#111111", 1),
                    action_card("Take & Scan Photo", "Camera capture & doc scanner", ft.Icons.CAMERA_ALT_ROUNDED, "#2C2C2E", 2),
                    action_card("AI Tutor Chat", "Ask questions & flashcards", ft.Icons.AUTO_AWESOME_ROUNDED, "#3A3A3C", 3),
                    action_card("App Settings", "API key, theme & storage", ft.Icons.SETTINGS_ROUNDED, "#48484A", 4),
                ],
                spacing=8,
            )
        ],
        spacing=8,
    )

    # Study Stats Row
    stat_cards = ft.Row(
        controls=[
            create_ios_card(
                content=ft.Column([
                    ft.Text(str(stats.get("pdfs_saved", 0)), size=22, weight=ft.FontWeight.BOLD, color=text_color),
                    ft.Text("PDFs Saved", size=11, color=sec_color),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                padding=12, dark=dark, expand=True
            ),
            create_ios_card(
                content=ft.Column([
                    ft.Text(str(stats.get("photos_captured", 0)), size=22, weight=ft.FontWeight.BOLD, color=text_color),
                    ft.Text("Photo Scans", size=11, color=sec_color),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                padding=12, dark=dark, expand=True
            ),
            create_ios_card(
                content=ft.Column([
                    ft.Text(str(stats.get("notes_created", 0)), size=22, weight=ft.FontWeight.BOLD, color=text_color),
                    ft.Text("AI Notes", size=11, color=sec_color),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                padding=12, dark=dark, expand=True
            ),
        ],
        spacing=8,
    )

    # Recent Documents Carousel
    recent_controls = []
    if items:
        for item in items[:4]:
            icon = ft.Icons.PICTURE_AS_PDF_ROUNDED if item["type"] == "pdf" else ft.Icons.IMAGE_ROUNDED
            color = "#111111" if item["type"] == "pdf" else "#2C2C2E"
            recent_controls.append(
                create_ios_card(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Icon(icon, color="#FFFFFF", size=18),
                            bgcolor=color,
                            padding=8,
                            border_radius=10,
                        ),
                        ft.Column([
                            ft.Text(item["title"], size=13, weight=ft.FontWeight.W_600, color=text_color, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1),
                            ft.Text(f"{item['created_at']} • {item['size_str']}", size=10, color=sec_color),
                        ], expand=True, spacing=2),
                    ]),
                    padding=10,
                    dark=dark,
                    on_click=lambda _, i=item: navigate_to_tab_cb(1 if i["type"] == "pdf" else 2)
                )
            )
    else:
        recent_controls.append(
            ft.Text("No saved documents yet. Tap Quick Actions above to begin!", size=12, color=sec_color)
        )

    # Kestrel Dashboard Sync Status
    from mobile_app import kestrel_bridge
    # ── Live Desktop Canvas Connection Check & Sync Card ────────────────────
    conn_info = kestrel_bridge.check_desktop_connection()
    is_desktop_online = conn_info.get("desktop_online", False)

    status_dot = ft.Container(
        width=10,
        height=10,
        border_radius=5,
        bgcolor="#10B981" if is_desktop_online else "#F59E0B"
    )
    status_title = ft.Text(
        f"Canvas Online • {conn_info.get('active_board_title', 'Notebook')}" if is_desktop_online else "Desktop Canvas Offline (Queue Active)",
        size=12,
        weight=ft.FontWeight.BOLD,
        color=text_color
    )
    status_desc = ft.Text(
        f"{conn_info.get('canvas_items_count', 0)} items on canvas • Uploads sync live" if is_desktop_online else "Uploads will queue & sync when Desktop opens",
        size=10,
        color=sec_color
    )

    def on_check_conn_clicked(e):
        fresh = kestrel_bridge.check_desktop_connection()
        online = fresh.get("desktop_online", False)
        status_dot.bgcolor = "#10B981" if online else "#F59E0B"
        status_title.value = f"Canvas Online • {fresh.get('active_board_title', 'Notebook')}" if online else "Desktop Canvas Offline (Queue Active)"
        status_desc.value = f"{fresh.get('canvas_items_count', 0)} items on canvas • Checked at {fresh.get('checked_at')}" if online else f"Pending queue: {fresh.get('pending_inbox_count', 0)} items"
        page.snack_bar = ft.SnackBar(
            ft.Text(
                f"Connection Check: Canvas is ONLINE on '{fresh.get('active_board_title')}'!" if online else "Connection Check: Storage linked! (Desktop Canvas is currently closed)."
            ),
            bgcolor="#10B981" if online else "#1F2937"
        )
        page.snack_bar.open = True
        try:
            status_dot.update()
            status_title.update()
            status_desc.update()
            page.update()
        except Exception:
            pass

    def on_send_test_note_clicked(e):
        kestrel_bridge.send_test_item_to_canvas("sticky_note")
        page.snack_bar = ft.SnackBar(
            ft.Text("Test Sticky Note pushed to Canvas inbox! Check your desktop canvas."),
            bgcolor="#111111"
        )
        page.snack_bar.open = True
        try:
            page.update()
        except Exception:
            pass

    sync_card = create_ios_card(
        content=ft.Column([
            ft.Row([
                ft.Row([
                    status_dot,
                    ft.Column([
                        ft.Text("KESTREL DESKTOP & CANVAS SYNC", size=10, weight=ft.FontWeight.BOLD, color=sec_color),
                        status_title,
                        status_desc,
                    ], spacing=1),
                ], spacing=10),
                ft.IconButton(
                    icon=ft.Icons.REFRESH_ROUNDED,
                    icon_color=text_color,
                    tooltip="Check Connection",
                    on_click=on_check_conn_clicked
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([
                ft.OutlinedButton(
                    "Check Connection",
                    icon=ft.Icons.WIFI_ROUNDED,
                    on_click=on_check_conn_clicked,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding.symmetric(horizontal=10, vertical=4))
                ),
                ft.ElevatedButton(
                    "Send Test Note to Canvas",
                    icon=ft.Icons.SCREEN_SHARE_ROUNDED,
                    on_click=on_send_test_note_clicked,
                    color="#FFFFFF",
                    bgcolor="#111111" if not dark else "#2C2C2E",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding.symmetric(horizontal=10, vertical=4))
                ),
            ], alignment=ft.MainAxisAlignment.END, spacing=6)
        ], spacing=8),
        padding=12,
        dark=dark
    )

    recents_sec = ft.Column(
        controls=[
            ft.Row([
                ft.Text("RECENT & SYNCED LIBRARY", size=12, weight=ft.FontWeight.W_600, color=sec_color),
                ft.TextButton("View All", on_click=lambda _: navigate_to_tab_cb(1)),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Column(recent_controls, spacing=6)
        ],
        spacing=4
    )

    return ft.ListView(
        controls=[
            header_col,
            ft.Divider(height=1, color=ft.Colors.TRANSPARENT),
            stat_cards,
            sync_card,
            quick_actions,
            recents_sec,
            ft.Container(height=40) # Spacing for bottom navbar
        ],
        spacing=16,
        padding=ft.Padding.all(16),
        expand=True,
    )
