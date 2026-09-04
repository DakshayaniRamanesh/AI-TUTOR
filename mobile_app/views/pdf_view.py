"""
iOS PDF Studio View for Kestrel Mobile
Save, import, compile images, extract text, and export PDF documents.
"""

import os
import time
import flet as ft
from mobile_app import storage
from mobile_app.services import pdf_service
from mobile_app.theme import (
    IOS_BLUE, IOS_GREEN, IOS_PURPLE, IOS_DARK_TEXT_PRIMARY, IOS_DARK_TEXT_SECONDARY,
    create_ios_card, create_ios_button
)

def build_pdf_view(page: ft.Page, update_app_cb=None) -> ft.Control:
    dark = page.theme_mode != ft.ThemeMode.LIGHT
    text_color = IOS_DARK_TEXT_PRIMARY if dark else "#000000"
    sec_color = IOS_DARK_TEXT_SECONDARY if dark else "#6C6C70"

    # Dialog / Status outputs
    pdf_text_display = ft.TextField(
        multiline=True,
        read_only=True,
        min_lines=6,
        max_lines=12,
        label="PDF Text & Summary Preview",
        text_size=12,
        bgcolor="#F2F2F7" if not dark else "#1C1C1E",
        border_color="#E0E0E5" if not dark else "#3A3A3C",
    )

    pdf_list_col = ft.Column(spacing=8)

    # Refresh list of PDFs
    def refresh_pdf_list():
        pdf_list_col.controls.clear()
        pdf_items = storage.get_items_by_type("pdf")
        
        if not pdf_items:
            pdf_list_col.controls.append(
                ft.Text("No saved PDFs. Tap 'Import PDF' or 'Compile Images' below!", size=13, color=sec_color)
            )
        else:
            for item in pdf_items:
                def view_pdf_action(e, path=item["file_path"], title=item["title"]):
                    text = pdf_service.extract_pdf_text(path)
                    pdf_text_display.value = f"{title}\n\n{text}"
                    pdf_text_display.update()

                def delete_pdf_action(e, item_id=item["id"]):
                    storage.delete_item(item_id)
                    refresh_pdf_list()
                    if update_app_cb:
                        update_app_cb()

                def send_pdf_to_canvas_action(e, path=item["file_path"], title=item["title"]):
                    from mobile_app import kestrel_bridge
                    kestrel_bridge.queue_item_for_canvas("pdf", file_path=path, title=title)
                    page.snack_bar = ft.SnackBar(ft.Text(f"PDF '{title}' sent to Desktop Canvas!"), bgcolor="#10B981")
                    page.snack_bar.open = True
                    try:
                        page.update()
                    except Exception:
                        pass

                pdf_card = create_ios_card(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Icon(ft.Icons.PICTURE_AS_PDF_ROUNDED, color="#FFFFFF", size=20),
                            bgcolor=IOS_BLUE,
                            padding=10,
                            border_radius=12,
                        ),
                        ft.Column([
                            ft.Row([
                                ft.Text(item["title"], size=13, weight=ft.FontWeight.BOLD, color=text_color, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1, expand=True),
                                ft.Container(
                                    content=ft.Text("DESKTOP SYNC" if item.get("is_desktop") else "MOBILE", size=8, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                                    bgcolor="#111111" if item.get("is_desktop") else "#48484A",
                                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                    border_radius=6
                                )
                            ], spacing=4),
                            ft.Text(f"{item['created_at']} • {item['size_str']}", size=11, color=sec_color),
                        ], expand=True, spacing=2),
                        ft.IconButton(
                            icon=ft.Icons.SCREEN_SHARE_ROUNDED,
                            icon_color=IOS_BLUE,
                            tooltip="Send to Desktop Canvas",
                            on_click=send_pdf_to_canvas_action
                        ),
                        ft.IconButton(
                            icon=ft.Icons.AUTO_AWESOME_ROUNDED,
                            icon_color=IOS_PURPLE,
                            tooltip="Read / Preview Text",
                            on_click=view_pdf_action
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINED,
                            icon_color=ft.Colors.RED_400,
                            tooltip="Delete PDF",
                            on_click=delete_pdf_action
                        ),
                    ]),
                    padding=10,
                    dark=dark
                )
                pdf_list_col.controls.append(pdf_card)
        try:
            pdf_list_col.update()
        except Exception:
            pass

    file_picker = ft.FilePicker()
    if hasattr(page, "services") and file_picker not in page.services:
        page.services.append(file_picker)

    # Action: Import PDF
    async def import_pdf_clicked(e):
        try:
            files = await file_picker.pick_files(
                allow_multiple=True,
                allowed_extensions=["pdf"],
                with_data=True,
                dialog_title="Select PDF Document to Save"
            )
            if files:
                saved_count = 0
                for picked_file in files:
                    target_filename = picked_file.name or f"imported_{int(time.time())}.pdf"
                    if not target_filename.lower().endswith(".pdf"):
                        target_filename += ".pdf"
                    target_path = os.path.join(storage.PDF_DIR, target_filename)

                    if picked_file.bytes:
                        with open(target_path, "wb") as f:
                            f.write(picked_file.bytes)
                        source = target_path
                    elif picked_file.path and os.path.exists(picked_file.path):
                        source = picked_file.path
                    else:
                        continue

                    storage.add_item(
                        title=picked_file.name or "Imported PDF",
                        item_type="pdf",
                        source_path=source,
                        tags=["Imported", "PDF"]
                    )
                    saved_count += 1

                if saved_count > 0:
                    refresh_pdf_list()
                    if update_app_cb:
                        update_app_cb()
                    page.snack_bar = ft.SnackBar(ft.Text(f"Saved {saved_count} PDF(s) & synced to Kestrel!"), bgcolor="#111111")
                    page.snack_bar.open = True
                    page.update()
        except Exception as ex:
            print(f"File picker error: {ex}")

    # Action: Create PDF from Images
    def compile_images_to_pdf(e):
        image_items = storage.get_items_by_type("image") + storage.get_items_by_type("scan")
        if not image_items:
            page.snack_bar = ft.SnackBar(ft.Text("No captured images found. Snap some photos first in Camera tab!"), bgcolor="#2C2C2E")
            page.snack_bar.open = True
            page.update()
            return
            
        img_paths = [i["file_path"] for i in image_items if os.path.exists(i["file_path"])]
        if img_paths:
            out_name = f"Scanned_Doc_{int(time.time())}.pdf"
            out_path = os.path.join(storage.PDF_DIR, out_name)
            if pdf_service.convert_images_to_pdf(img_paths, out_path):
                storage.add_item(
                    title=out_name,
                    item_type="pdf",
                    source_path=out_path,
                    tags=["Scanned", "Compiled"]
                )
                refresh_pdf_list()
                if update_app_cb:
                    update_app_cb()
                page.snack_bar = ft.SnackBar(ft.Text(f"Compiled {len(img_paths)} photos into '{out_name}'!"), bgcolor="#111111")
                page.snack_bar.open = True
                page.update()

    # Action: Export New PDF Note
    note_title_input = ft.TextField(label="PDF Note Title", value="Kestrel Study Note", text_size=12)
    note_body_input = ft.TextField(label="Note Body Text", value="Key formulas:\n• E = mc²\n• F = ma\n\nImportant study takeaways for exam review.", multiline=True, min_lines=3, text_size=12)
    
    def generate_pdf_note_clicked(e):
        t = note_title_input.value.strip() or "Study Note"
        c = note_body_input.value.strip() or "Notes"
        out_name = f"{t.replace(' ', '_')}.pdf"
        out_path = os.path.join(storage.PDF_DIR, out_name)
        if pdf_service.generate_notes_pdf(t, c, out_path):
            storage.add_item(
                title=out_name,
                item_type="pdf",
                source_path=out_path,
                tags=["AI Note", "Generated"]
            )
            refresh_pdf_list()
            if update_app_cb:
                update_app_cb()
            page.snack_bar = ft.SnackBar(ft.Text(f"Saved PDF Note '{out_name}'!"), bgcolor="#111111")
            page.snack_bar.open = True
            page.update()

    # Layout Assembly
    header = ft.Row([
        ft.Column([
            ft.Text("PDF STUDIO", size=11, weight=ft.FontWeight.W_700, color=sec_color),
            ft.Text("Save & Export PDF", size=24, weight=ft.FontWeight.BOLD, color=text_color),
        ], spacing=0),
        create_ios_button("Import PDF", icon=ft.Icons.UPLOAD_FILE_ROUNDED, color="#111111", on_click=import_pdf_clicked, height=38)
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    tools_row = ft.Row([
        create_ios_button("Compile Photos to PDF", icon=ft.Icons.COLLECTIONS_ROUNDED, color="#2C2C2E", on_click=compile_images_to_pdf, height=40),
    ])

    create_pdf_card = create_ios_card(
        content=ft.Column([
            ft.Text("CREATE STYLED PDF NOTE", size=12, weight=ft.FontWeight.W_700, color=sec_color),
            note_title_input,
            note_body_input,
            create_ios_button("Save as PDF Document", icon=ft.Icons.SAVE_ROUNDED, color="#111111", on_click=generate_pdf_note_clicked, height=40)
        ], spacing=8),
        padding=12,
        dark=dark
    )

    # Trigger initial populate
    refresh_pdf_list()

    return ft.ListView([
        header,
        tools_row,
        ft.Text("SAVED PDF DOCUMENTS", size=12, weight=ft.FontWeight.W_600, color=sec_color),
        pdf_list_col,
        pdf_text_display,
        create_pdf_card,
        ft.Container(height=40)
    ], spacing=14, padding=16, expand=True)
