"""
Kestrel Mobile iOS App
Main Entry Point built with Flet in Python
Screen Aspect Ratio: Authentic iOS Mobile Viewport (393 x 852 / 410 x 860)
"""

import sys
import os
import socket
import flet as ft
from datetime import datetime

# Ensure root workspace is on path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from mobile_app import storage
from mobile_app.theme import (
    IOS_BLUE, IOS_DARK_BG, IOS_DARK_CARD, IOS_DARK_BORDER,
    IOS_LIGHT_BG, IOS_LIGHT_CARD, IOS_LIGHT_BORDER,
    get_ios_theme
)
from mobile_app.views.home_view import build_home_view
from mobile_app.views.pdf_view import build_pdf_view
from mobile_app.views.camera_view import build_camera_view
from mobile_app.views.tutor_view import build_tutor_view
from mobile_app.views.settings_view import build_settings_view

def main(page: ft.Page):
    # Initialize Storage
    storage.init_storage()

    # Window & Page Setup for iPhone Screen Ratio
    page.title = "Kestrel Mobile iOS"
    page.window.width = 410
    page.window.height = 860
    page.window.resizable = True
    page.padding = 0
    page.spacing = 0
    
    # Load Theme preference (Defaults to Light Monochromatic)
    user_settings = storage.get_settings()
    saved_theme = user_settings.get("theme", "light")
    page.theme_mode = ft.ThemeMode.DARK if saved_theme == "dark" else ft.ThemeMode.LIGHT
    page.theme = get_ios_theme(dark=(page.theme_mode == ft.ThemeMode.DARK))

    active_tab = [0]
    content_area = ft.Container(expand=True)

    def get_current_bg():
        return IOS_DARK_BG if page.theme_mode == ft.ThemeMode.DARK else IOS_LIGHT_BG

    def get_card_bg():
        return IOS_DARK_CARD if page.theme_mode == ft.ThemeMode.DARK else IOS_LIGHT_CARD

    # iOS Top Status Bar & Dynamic Island Notch
    status_time = ft.Text(
        datetime.now().strftime("%H:%M"),
        size=13,
        weight=ft.FontWeight.BOLD,
        color="#FFFFFF" if page.theme_mode == ft.ThemeMode.DARK else "#000000"
    )

    dynamic_island = ft.Container(
        content=ft.Row([
            ft.Container(width=8, height=8, border_radius=4, bgcolor="#8E8E93"),
            ft.Text("Kestrel iOS", size=10, weight=ft.FontWeight.W_600, color="#FFFFFF"),
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
        width=120,
        height=26,
        bgcolor="#000000",
        border_radius=15,
        alignment=ft.Alignment.CENTER,
    )

    status_bar = ft.Container(
        content=ft.Row([
            status_time,
            dynamic_island,
            ft.Row([
                ft.Icon(ft.Icons.WIFI, size=14, color="#FFFFFF" if page.theme_mode == ft.ThemeMode.DARK else "#000000"),
                ft.Icon(ft.Icons.BATTERY_FULL_ROUNDED, size=16, color="#FFFFFF" if page.theme_mode == ft.ThemeMode.DARK else "#000000"),
            ], spacing=4)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        padding=ft.Padding.only(left=18, right=18, top=10, bottom=4),
        bgcolor=get_current_bg(),
    )

    def navigate_to_tab(tab_index: int):
        active_tab[0] = tab_index
        render_current_view()
        render_bottom_nav()

    def update_app():
        page.theme = get_ios_theme(dark=(page.theme_mode == ft.ThemeMode.DARK))
        status_bar.bgcolor = get_current_bg()
        render_current_view()
        render_bottom_nav()
        page.update()

    def render_current_view():
        idx = active_tab[0]
        if idx == 0:
            content_area.content = build_home_view(page, navigate_to_tab_cb=navigate_to_tab)
        elif idx == 1:
            content_area.content = build_pdf_view(page, update_app_cb=update_app)
        elif idx == 2:
            content_area.content = build_camera_view(page, update_app_cb=update_app)
        elif idx == 3:
            content_area.content = build_tutor_view(page, update_app_cb=update_app)
        elif idx == 4:
            content_area.content = build_settings_view(page, update_app_cb=update_app)
        content_area.bgcolor = get_current_bg()
        try:
            content_area.update()
        except Exception:
            pass

    # Bottom iOS Cupertino Navigation Bar
    bottom_nav_container = ft.Container()

    def render_bottom_nav():
        dark = page.theme_mode == ft.ThemeMode.DARK
        bg = get_card_bg()
        border_col = IOS_DARK_BORDER if dark else IOS_LIGHT_BORDER
        active_c = IOS_BLUE
        inactive_c = "#8E8E93" if dark else "#6C6C70"

        tabs_data = [
            ("Home", ft.Icons.HOME_ROUNDED, 0),
            ("PDF Studio", ft.Icons.PICTURE_IN_PICTURE_ALT_ROUNDED, 1),
            ("Camera", ft.Icons.CAMERA_ALT_ROUNDED, 2),
            ("AI Tutor", ft.Icons.AUTO_AWESOME_ROUNDED, 3),
            ("Settings", ft.Icons.SETTINGS_ROUNDED, 4),
        ]

        nav_items = []
        for name, icon, idx in tabs_data:
            is_active = (active_tab[0] == idx)
            color = active_c if is_active else inactive_c
            
            nav_items.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(icon, color=color, size=22),
                        ft.Text(name, size=10, weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.NORMAL, color=color),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                    on_click=lambda _, i=idx: navigate_to_tab(i),
                    padding=ft.Padding.symmetric(vertical=6),
                    expand=True
                )
            )

        bottom_nav_container.content = ft.Container(
            content=ft.Column([
                ft.Row(nav_items, alignment=ft.MainAxisAlignment.SPACE_AROUND),
                # Home Indicator Bar (iOS Home Pill)
                ft.Container(
                    width=130,
                    height=4,
                    border_radius=2,
                    bgcolor=inactive_c,
                    alignment=ft.Alignment.CENTER,
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
            padding=ft.Padding.only(top=8, bottom=6),
            bgcolor=bg,
            border=ft.Border.only(top=ft.BorderSide(1, border_col))
        )
        try:
            bottom_nav_container.update()
        except Exception:
            pass

    # Prepare initial views
    render_current_view()
    render_bottom_nav()

    # Initial Render to Page
    page.add(
        ft.Column([
            status_bar,
            content_area,
            bottom_nav_container
        ], expand=True, spacing=0)
    )

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def find_free_port(starting_port=8550):
    port = starting_port
    while port < starting_port + 20:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                port += 1
    return starting_port

if __name__ == "__main__":
    if "--web" in sys.argv or "--network" in sys.argv:
        port = find_free_port(8550)
        lan_ip = get_lan_ip()
        lan_url = f"http://{lan_ip}:{port}"
        local_url = f"http://localhost:{port}"
        
        print("\n" + "=" * 60)
        print("  KESTREL MOBILE iOS APP - NETWORK MODE ACTIVE")
        print("=" * 60)
        print(f"  Local Access:    {local_url}")
        print(f"  Mobile / Wi-Fi:  {lan_url}")
        print("=" * 60)
        print("  Scan this QR code with your iPhone / Android camera:")
        print("=" * 60)
        
        try:
            import qrcode
            qr = qrcode.QRCode(border=1)
            qr.add_data(lan_url)
            for row in qr.get_matrix():
                print("".join("  " if col else "##" for col in row))
                
            # Also save QR code image for visual viewing
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_path = os.path.join(os.path.dirname(__file__), "assets", "mobile_qr.png")
            os.makedirs(os.path.dirname(qr_path), exist_ok=True)
            qr_img.save(qr_path)
            print(f"\n[+] Saved QR Code image to: {qr_path}")
        except Exception as e:
            pass

        print("\n  Instructions for iPhone / iPad:")
        print("  1. Connect your phone to the same Wi-Fi network.")
        print(f"  2. Open Safari and navigate to: {lan_url}")
        print("  3. Tap 'Share' -> 'Add to Home Screen' for fullscreen iOS app mode!")
        print("=" * 60 + "\n")
        
        ft.run(main, view=ft.AppView.WEB_BROWSER, host="0.0.0.0", port=port)
    else:
        ft.run(main)

