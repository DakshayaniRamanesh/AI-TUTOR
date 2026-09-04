"""
iOS AI Tutor & Flashcards View for Kestrel Mobile
"""

import flet as ft
from mobile_app import storage
from mobile_app.services import ai_service, pdf_service
from mobile_app.theme import (
    IOS_BLUE, IOS_GREEN, IOS_INDIGO, IOS_PURPLE,
    IOS_DARK_CARD, IOS_DARK_TEXT_PRIMARY, IOS_DARK_TEXT_SECONDARY,
    create_ios_card, create_ios_button
)

def build_tutor_view(page: ft.Page, update_app_cb=None) -> ft.Control:
    dark = page.theme_mode != ft.ThemeMode.LIGHT
    text_color = IOS_DARK_TEXT_PRIMARY if dark else "#000000"
    sec_color = IOS_DARK_TEXT_SECONDARY if dark else "#6C6C70"

    messages_col = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
    user_input = ft.TextField(
        hint_text="Ask Kestrel AI Tutor anything...",
        expand=True,
        text_size=13,
        border_radius=20,
        content_padding=ft.Padding.symmetric(horizontal=14, vertical=10)
    )

    # Document attachment dropdown
    attachment_dropdown = ft.Dropdown(
        hint_text="Attach PDF or Image Context",
        options=[],
        text_size=11,
        expand=True
    )

    def populate_attachments():
        attachment_dropdown.options.clear()
        attachment_dropdown.options.append(ft.dropdown.Option("", "None (General Tutor)"))
        items = storage.get_all_items()
        for i in items:
            prefix = "PDF: " if i["type"] == "pdf" else "Photo: "
            attachment_dropdown.options.append(ft.dropdown.Option(i["id"], f"{prefix}{i['title']}"))
        try:
            attachment_dropdown.update()
        except Exception:
            pass

    # Add message bubble
    def add_message(sender: str, text: str, is_user: bool = False):
        bg = "#111111" if is_user else ("#FFFFFF" if not dark else "#1C1C1E")
        txt_c = "#FFFFFF" if is_user else text_color
        border_box = None if is_user else ft.Border.all(1, "#E0E0E5" if not dark else "#3A3A3C")
        alignment = ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START

        bubble = ft.Row([
            ft.Container(
                content=ft.Column([
                    ft.Text(sender, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.with_opacity(0.7, txt_c)),
                    ft.Text(text, size=13, color=txt_c, selectable=True),
                ], spacing=2),
                bgcolor=bg,
                border=border_box,
                padding=12,
                border_radius=16,
                width=300
            )
        ], alignment=alignment)

        messages_col.controls.append(bubble)
        try:
            messages_col.update()
        except Exception:
            pass

    # Handle Send Query
    def send_query_clicked(e):
        query = user_input.value.strip()
        if not query:
            if attachment_dropdown.value:
                query = "Please provide a comprehensive summary and 3 key study takeaways from this attached material."
            else:
                query = "Can you give me a quick overview of how you can help me study today?"
            
        user_input.value = ""
        user_input.update()
        add_message("YOU", query, is_user=True)

        # Context evaluation
        selected_id = attachment_dropdown.value
        context_text = ""
        image_path = None
        if selected_id:
            items = storage.get_all_items()
            target = next((i for i in items if i["id"] == selected_id), None)
            if target:
                if target["type"] == "pdf":
                    context_text = pdf_service.extract_pdf_text(target["file_path"])
                elif target["type"] in ["image", "scan"]:
                    image_path = target["file_path"]

        # Response from AI Tutor service
        response_text = ai_service.ask_ai_tutor(query, context_text=context_text, image_path=image_path)
        add_message("KESTREL AI", response_text, is_user=False)

    # Initial Welcome message
    add_message(
        "KESTREL AI TUTOR",
        "Hello! I am your iOS AI Study Companion. Ask me to explain concepts, summarize PDFs, or analyze captured photos!",
        is_user=False
    )

    # Flashcard Interactive View
    flashcard_card = ft.Container(visible=False)

    def show_flashcards_action(e):
        topic = user_input.value.strip() or "Quantum Physics & Math"
        cards = ai_service.generate_flashcards(topic)
        
        card_controls = []
        for idx, card in enumerate(cards):
            card_controls.append(
                create_ios_card(
                    content=ft.Column([
                        ft.Text(f"CARD #{idx+1}", size=10, weight=ft.FontWeight.BOLD, color=sec_color),
                        ft.Text(f"Q: {card['question']}", size=13, weight=ft.FontWeight.BOLD, color=text_color),
                        ft.Divider(height=1, color=sec_color),
                        ft.Text(f"A: {card['answer']}", size=12, color=text_color),
                    ], spacing=6),
                    padding=12,
                    dark=dark
                )
            )
            
        flashcard_card.content = ft.Column([
            ft.Row([
                ft.Text("INTERACTIVE FLASHCARDS", size=12, weight=ft.FontWeight.BOLD, color=text_color),
                ft.IconButton(ft.Icons.CLOSE_ROUNDED, on_click=lambda _: hide_flashcards())
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Column(card_controls, spacing=8)
        ])
        flashcard_card.visible = True
        flashcard_card.update()

    def hide_flashcards():
        flashcard_card.visible = False
        flashcard_card.update()

    header = ft.Column([
        ft.Text("AI TUTOR", size=11, weight=ft.FontWeight.W_700, color=sec_color),
        ft.Text("Smart Study Chat", size=24, weight=ft.FontWeight.BOLD, color=text_color),
    ], spacing=0)

    quick_pills = ft.Row([
        create_ios_button("Flashcards", icon=ft.Icons.STYLE_ROUNDED, color="#2C2C2E", on_click=show_flashcards_action, height=34),
        create_ios_button("Summarize Doc", icon=ft.Icons.SUMMARIZE_ROUNDED, color="#111111", on_click=lambda _: send_query_clicked(None), height=34),
    ], spacing=8)

    populate_attachments()

    return ft.Container(
        content=ft.Column([
            header,
            attachment_dropdown,
            quick_pills,
            flashcard_card,
            messages_col,
            ft.Row([
                user_input,
                ft.IconButton(
                    icon=ft.Icons.ARROW_UPWARD_ROUNDED,
                    icon_color="#FFFFFF",
                    bgcolor="#111111",
                    on_click=send_query_clicked
                )
            ], spacing=6),
            ft.Container(height=40)
        ], spacing=10, expand=True),
        padding=16,
        expand=True
    )
