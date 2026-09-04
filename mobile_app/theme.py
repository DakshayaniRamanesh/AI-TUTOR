"""
iOS Human Interface Guidelines (HIG) Theme - Monochromatic Light Theme
Clean Apple Minimalist Aesthetic: Black, White, Charcoal, and Slate Silver
"""

import flet as ft

# Monochromatic Apple Palette
MONO_BLACK = "#111111"
MONO_CHARCOAL = "#2C2C2E"
MONO_SLATE = "#3A3A3C"
MONO_DARK_GRAY = "#48484A"
MONO_MID_GRAY = "#8E8E93"
MONO_LIGHT_GRAY = "#E5E5EA"
MONO_BORDER = "#E0E0E5"
MONO_CARD = "#FFFFFF"
MONO_BG = "#F2F2F7"

# Aliases for compatibility (mapped to sleek monochrome)
IOS_BLUE = MONO_BLACK
IOS_GREEN = MONO_CHARCOAL
IOS_INDIGO = MONO_SLATE
IOS_ORANGE = MONO_DARK_GRAY
IOS_PINK = MONO_CHARCOAL
IOS_TEAL = MONO_SLATE
IOS_PURPLE = MONO_CHARCOAL

# Dark Theme Colors
IOS_DARK_BG = "#000000"
IOS_DARK_CARD = "#1C1C1E"
IOS_DARK_CARD_ALT = "#2C2C2E"
IOS_DARK_TEXT_PRIMARY = "#FFFFFF"
IOS_DARK_TEXT_SECONDARY = "#8E8E93"
IOS_DARK_BORDER = "#3A3A3C"

# Light Theme Colors (Default Monochromatic)
IOS_LIGHT_BG = MONO_BG
IOS_LIGHT_CARD = MONO_CARD
IOS_LIGHT_CARD_ALT = MONO_LIGHT_GRAY
IOS_LIGHT_TEXT_PRIMARY = "#000000"
IOS_LIGHT_TEXT_SECONDARY = "#6C6C70"
IOS_LIGHT_BORDER = MONO_BORDER

def get_ios_theme(dark: bool = False):
    """Returns iOS themed Flet Theme configuration (Defaults to Monochromatic Light)."""
    card = IOS_DARK_CARD if dark else IOS_LIGHT_CARD
    text = IOS_DARK_TEXT_PRIMARY if dark else IOS_LIGHT_TEXT_PRIMARY
    
    return ft.Theme(
        color_scheme=ft.ColorScheme(
            surface=card,
            primary=MONO_BLACK if not dark else "#FFFFFF",
            on_primary="#FFFFFF" if not dark else "#000000",
            secondary=MONO_CHARCOAL,
            on_surface=text,
        ),
        use_material3=True,
    )

def create_ios_card(content: ft.Control, padding: int = 16, border_radius: int = 18, dark: bool = False, on_click=None, expand: bool = False, **kwargs) -> ft.Container:
    """Helper to wrap controls inside authentic iOS rounded frosted-style cards."""
    card_bg = IOS_DARK_CARD if dark else IOS_LIGHT_CARD
    border_color = IOS_DARK_BORDER if dark else IOS_LIGHT_BORDER
    
    return ft.Container(
        content=content,
        padding=padding,
        border_radius=border_radius,
        bgcolor=card_bg,
        border=ft.Border.all(1, border_color),
        on_click=on_click,
        expand=expand,
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT_CUBIC),
        **kwargs
    )

def create_ios_button(text: str, icon: str = None, color: str = MONO_BLACK, text_color: str = "#FFFFFF", on_click=None, height: int = 46, expand: bool = False, **kwargs) -> ft.Container:
    """Helper for Apple sleek pill action button."""
    content_list = []
    if icon:
        content_list.append(ft.Icon(icon, color=text_color, size=18))
    content_list.append(ft.Text(text, color=text_color, weight=ft.FontWeight.W_600, size=14))
    
    return ft.Container(
        content=ft.Row(content_list, alignment=ft.MainAxisAlignment.CENTER, spacing=8),
        bgcolor=color,
        border_radius=23,
        height=height,
        padding=ft.Padding.symmetric(horizontal=16),
        on_click=on_click,
        expand=expand,
        animate=ft.Animation(150, ft.AnimationCurve.EASE_IN_OUT),
        **kwargs
    )
