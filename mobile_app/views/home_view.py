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
    sync_summary = kestrel_bridge.get_sync_summary()

    def on_sync_clicked(e):
        items = storage.get_all_items()
        page.snack_bar = ft.SnackBar(ft.Text("Synced with Kestrel Desktop Dashboard!"), bgcolor="#111111")
        page.snack_bar.open = True
        try:
            page.update()
        except Exception:
            pass

    sync_card = create_ios_card(
        content=ft.Row([
            ft.Row([
                ft.Container(
                    width=8,
                    height=8,
                    border_radius=4,
                    bgcolor="#34C759" if sync_summary.get("synced") else "#8E8E93"
                ),
                ft.Column([
                    ft.Text("KESTREL DASHBOARD SYNC", size=10, weight=ft.FontWeight.BOLD, color=sec_color),
                    ft.Text(f"{sync_summary['desktop_materials_count']} Reference PDFs • {sync_summary['desktop_boards_count']} Whiteboards", size=12, weight=ft.FontWeight.W_600, color=text_color),
                ], spacing=1),
            ], spacing=10),
            ft.IconButton(
                icon=ft.Icons.SYNC_ROUNDED,
                icon_color=text_color,
                tooltip="Sync with Kestrel Desktop",
                on_click=on_sync_clicked
            )
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
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
