"""
iOS Camera & Document Scanner View for Kestrel Mobile
Take images, apply document scan filters (B&W contrast, grayscale, magic color), and save to gallery.
"""

import os
import time
import flet as ft
from mobile_app import storage
from mobile_app.services import image_service
from mobile_app.theme import (
    IOS_BLUE, IOS_GREEN, IOS_PURPLE, IOS_ORANGE,
    IOS_DARK_TEXT_PRIMARY, IOS_DARK_TEXT_SECONDARY,
    create_ios_card, create_ios_button
)

def build_camera_view(page: ft.Page, update_app_cb=None) -> ft.Control:
    dark = page.theme_mode != ft.ThemeMode.LIGHT
    text_color = IOS_DARK_TEXT_PRIMARY if dark else "#000000"
    sec_color = IOS_DARK_TEXT_SECONDARY if dark else "#6C6C70"

    current_raw_path = [""]
    selected_image_path = ft.Text("No image selected", size=11, color=sec_color)
    preview_img = ft.Image(src="", width=320, height=220, fit=ft.BoxFit.CONTAIN, border_radius=12, visible=False)
    filter_choice = ft.RadioGroup(
        content=ft.Row([
            ft.Radio(value="scan", label="Doc Scan"),
            ft.Radio(value="magic", label="Magic Color"),
            ft.Radio(value="grayscale", label="B&W"),
            ft.Radio(value="original", label="Original"),
        ], wrap=True, alignment=ft.MainAxisAlignment.SPACE_AROUND),
        value="scan"
    )

    gallery_grid = ft.Row(wrap=True, spacing=8)

    def refresh_gallery():
        gallery_grid.controls.clear()
        img_items = storage.get_items_by_type("image") + storage.get_items_by_type("scan")
        if not img_items:
            gallery_grid.controls.append(
                ft.Text("No photo scans in gallery. Tap 'Take / Select Photo' above!", size=12, color=sec_color)
            )
        else:
            for item in img_items[:8]:
                def delete_img(e, item_id=item["id"]):
                    storage.delete_item(item_id)
                    refresh_gallery()
                    if update_app_cb:
                        update_app_cb()

                thumb_uri = storage.get_image_data_uri(item["file_path"])
                gallery_grid.controls.append(
                    create_ios_card(
                        content=ft.Column([
                            ft.Image(src=thumb_uri, width=100, height=100, fit=ft.BoxFit.COVER, border_radius=8),
                            ft.Text(item["title"], size=10, weight=ft.FontWeight.BOLD, color=text_color, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1),
                            ft.IconButton(icon=ft.Icons.DELETE_OUTLINED, icon_color=ft.Colors.RED_400, icon_size=16, on_click=delete_img)
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                        padding=6,
                        dark=dark
                    )
                )
        try:
            gallery_grid.update()
        except Exception:
            pass

    file_picker = ft.FilePicker()
    if hasattr(page, "services") and file_picker not in page.services:
        page.services.append(file_picker)

    async def pick_image_action(e):
        try:
            files = await file_picker.pick_files(
                allow_multiple=False,
                allowed_extensions=["png", "jpg", "jpeg", "webp"],
                with_data=True,
                dialog_title="Take Photo or Pick Document Image"
            )
            if files and len(files) > 0:
                picked = files[0]
                target_path = os.path.join(storage.IMAGE_DIR, f"raw_{int(time.time())}_{picked.name or 'capture.png'}")
                if picked.bytes:
                    with open(target_path, "wb") as f:
                        f.write(picked.bytes)
                    current_raw_path[0] = target_path
                elif picked.path and os.path.exists(picked.path):
                    current_raw_path[0] = picked.path
                else:
                    return

                selected_image_path.value = f"Selected: {picked.name or 'Photo'}"
                preview_img.src = storage.get_image_data_uri(current_raw_path[0])
                preview_img.visible = True
                selected_image_path.update()
                preview_img.update()
                page.snack_bar = ft.SnackBar(ft.Text("Image loaded! Choose scanner filter and tap Save."), bgcolor="#111111")
                page.snack_bar.open = True
                page.update()
        except Exception as ex:
            print(f"Image picker error: {ex}")

    # Action: Save & Apply Scanner Filter
    def save_scanned_photo_action(e):
        if not current_raw_path[0] or not os.path.exists(current_raw_path[0]):
            page.snack_bar = ft.SnackBar(ft.Text("Please select or capture a photo first!"), bgcolor="#2C2C2E")
            page.snack_bar.open = True
            page.update()
            return
            
        ft_val = filter_choice.value or "scan"
        out_name = f"Scan_{ft_val}_{int(time.time())}.png"
        out_path = os.path.join(storage.IMAGE_DIR, out_name)
        
        if image_service.process_scanned_image(current_raw_path[0], out_path, filter_type=ft_val):
            storage.add_item(
                title=out_name,
                item_type="scan",
                source_path=out_path,
                tags=["Document Scan", ft_val]
            )
            refresh_gallery()
            if update_app_cb:
                update_app_cb()
            preview_img.src = storage.get_image_data_uri(out_path)
            preview_img.update()
            page.snack_bar = ft.SnackBar(ft.Text(f"Scan saved & synced to Kestrel Whiteboard: {out_name}"), bgcolor="#111111")
            page.snack_bar.open = True
            page.update()

    header = ft.Column([
        ft.Text("CAMERA & SCANNER", size=11, weight=ft.FontWeight.W_700, color=sec_color),
        ft.Text("Take Images & Scan", size=24, weight=ft.FontWeight.BOLD, color=text_color),
    ], spacing=0)

    scanner_controls_card = create_ios_card(
        content=ft.Column([
            ft.Text("DOCUMENT SCANNER CONTROLS", size=12, weight=ft.FontWeight.W_700, color=sec_color),
            create_ios_button("Take / Choose Image", icon=ft.Icons.CAMERA_ALT_ROUNDED, color="#111111", on_click=pick_image_action, height=42),
            selected_image_path,
            preview_img,
            ft.Text("SELECT ENHANCEMENT FILTER", size=11, weight=ft.FontWeight.W_600, color=sec_color),
            filter_choice,
            create_ios_button("Process & Save to Scan Gallery", icon=ft.Icons.AUTO_FIX_HIGH_ROUNDED, color="#2C2C2E", on_click=save_scanned_photo_action, height=42)
        ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        padding=14,
        dark=dark
    )

    refresh_gallery()

    return ft.ListView([
        header,
        scanner_controls_card,
        ft.Text("SCANNED PHOTO GALLERY", size=12, weight=ft.FontWeight.W_600, color=sec_color),
        gallery_grid,
        ft.Container(height=40)
    ], spacing=14, padding=16, expand=True)
