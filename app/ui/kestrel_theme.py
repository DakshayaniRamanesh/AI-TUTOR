"""
Kestrel Centralized Theme — Monochrome / Brutalist / Technical Aesthetic
Provides get_global_qss(c) and helper functions consumed by every UI module.

Usage:
    from .kestrel_theme import get_global_qss, MONO_FONT
    ThemeManager.instance().theme_changed.connect(lambda _: self.setStyleSheet(get_global_qss(...)))
"""

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------
MONO_FONT = '"Courier New", "Consolas", "Lucida Console", monospace'
DISPLAY_FONT = '"Segoe UI", "SF Pro Display", sans-serif'


# ---------------------------------------------------------------------------
# Helpers — reusable QSS sub-snippets
# ---------------------------------------------------------------------------

def menu_qss(c: dict) -> str:
    """Monochrome context menu / dropdown popup styling."""
    return f"""
        QMenu {{
            background-color: {c['bg_card']};
            border: 1px solid {c['border_color']};
            border-radius: 2px;
            padding: 2px;
            font-family: {MONO_FONT};
            font-size: 12px;
        }}
        QMenu::item {{
            padding: 7px 16px;
            color: {c['text_primary']};
        }}
        QMenu::item:selected {{
            background-color: {c['accent']};
            color: {c['accent_text']};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {c['border_color']};
            margin: 2px 8px;
        }}
    """


def card_qss(c: dict, object_name: str = "", radius: int = 2) -> str:
    """Thin-bordered card / panel frame."""
    sel = f"QFrame#{object_name}" if object_name else "QFrame"
    return f"""
        {sel} {{
            background-color: {c['bg_card']};
            border: 1px solid {c['border_color']};
            border-radius: {radius}px;
        }}
    """


def pill_qss(c: dict, radius: int = 8) -> str:
    """HUD pill / floating container."""
    return f"""
        QWidget {{
            background-color: {c['bg_toolbar']};
            border: 1px solid {c['border_color']};
            border-radius: {radius}px;
        }}
    """


def primary_button_qss(c: dict, radius: int = 2) -> str:
    """Solid-filled primary action button (Save, Ask AI, New Notebook…)."""
    return f"""
        QPushButton {{
            background-color: {c['accent']};
            color: {c['accent_text']};
            border: 1px solid {c['accent']};
            border-radius: {radius}px;
            font-family: {MONO_FONT};
            font-size: 12px;
            font-weight: 600;
            padding: 6px 14px;
            letter-spacing: 0.5px;
        }}
        QPushButton:hover {{
            background-color: {c['accent_hover']};
            border-color: {c['accent_hover']};
        }}
        QPushButton:pressed {{
            background-color: {c['accent']};
            opacity: 0.85;
        }}
        QPushButton:disabled {{
            background-color: {c['border_color']};
            color: {c['text_secondary']};
        }}
    """


def ghost_button_qss(c: dict, radius: int = 2) -> str:
    """Ghost / secondary action button (bordered, transparent bg)."""
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {c['text_primary']};
            border: 1px solid {c['border_color']};
            border-radius: {radius}px;
            font-family: {MONO_FONT};
            font-size: 12px;
            font-weight: 500;
            padding: 6px 14px;
        }}
        QPushButton:hover {{
            background-color: {c['panel_card_bg']};
            border-color: {c['accent']};
        }}
        QPushButton:pressed {{
            background-color: {c['border_color']};
        }}
        QPushButton:disabled {{
            color: {c['text_secondary']};
            border-color: {c['border_color']};
        }}
    """


def scrollbar_qss(c: dict) -> str:
    return f"""
        QScrollBar:vertical {{
            background: {c['bg_app']};
            width: 6px;
            margin: 0;
            border: none;
        }}
        QScrollBar::handle:vertical {{
            background: {c['border_color']};
            border-radius: 3px;
            min-height: 24px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {c['text_secondary']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar:horizontal {{
            background: {c['bg_app']};
            height: 6px;
            margin: 0;
            border: none;
        }}
        QScrollBar::handle:horizontal {{
            background: {c['border_color']};
            border-radius: 3px;
            min-width: 24px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {c['text_secondary']};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0;
        }}
    """


# ---------------------------------------------------------------------------
# Global Application Stylesheet
# ---------------------------------------------------------------------------

def get_global_qss(c: dict) -> str:
    """
    Returns the complete application-level QSS stylesheet for the given
    color token dict from ThemeManager.get_colors().
    Apply via: QApplication.instance().setStyleSheet(get_global_qss(c))
    or per-widget via setStyleSheet.
    """
    return f"""
        /* ── Base ── */
        QMainWindow, QWidget {{
            background-color: {c['bg_app']};
            color: {c['text_primary']};
            font-family: {MONO_FONT};
            font-size: 13px;
        }}
        QDialog {{
            background-color: {c['bg_card']};
            color: {c['text_primary']};
            font-family: {MONO_FONT};
        }}

        /* ── Splitter ── */
        QSplitter::handle {{
            background-color: {c['border_color']};
        }}
        QSplitter::handle:horizontal {{
            width: 1px;
        }}
        QSplitter::handle:vertical {{
            height: 1px;
        }}

        /* ── Scroll Bars ── */
        {scrollbar_qss(c)}

        /* ── Tooltips ── */
        QToolTip {{
            background-color: {c['bg_card']};
            color: {c['text_primary']};
            border: 1px solid {c['border_color']};
            border-radius: 2px;
            padding: 4px 8px;
            font-family: {MONO_FONT};
            font-size: 11px;
        }}

        /* ── Tab Widget ── */
        QTabWidget::pane {{
            border: none;
            border-top: 1px solid {c['border_color']};
        }}
        QTabBar::tab {{
            background: transparent;
            color: {c['text_secondary']};
            font-family: {MONO_FONT};
            font-size: 12px;
            font-weight: 500;
            padding: 8px 16px;
            border: none;
            border-bottom: 2px solid transparent;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            color: {c['text_primary']};
            border-bottom: 2px solid {c['accent']};
        }}
        QTabBar::tab:hover:!selected {{
            color: {c['text_primary']};
            background-color: {c['panel_card_bg']};
        }}

        /* ── List Widget ── */
        QListWidget {{
            background-color: {c['bg_card']};
            border: 1px solid {c['border_color']};
            border-radius: 2px;
            font-family: {MONO_FONT};
            font-size: 13px;
            outline: none;
        }}
        QListWidget::item {{
            padding: 8px 8px;
            border-bottom: 1px solid {c['border_color']};
            color: {c['text_primary']};
        }}
        QListWidget::item:last-child {{
            border-bottom: none;
        }}
        QListWidget::item:hover {{
            background-color: {c['panel_card_bg']};
        }}
        QListWidget::item:selected {{
            background-color: {c['accent']};
            color: {c['accent_text']};
        }}

        /* ── Tree Widget ── */
        QTreeWidget {{
            background-color: {c['bg_card']};
            border: 1px solid {c['border_color']};
            border-radius: 2px;
            font-family: {MONO_FONT};
            font-size: 12px;
            color: {c['text_primary']};
            outline: none;
        }}
        QTreeWidget::item {{
            padding: 4px 4px;
        }}
        QTreeWidget::item:hover {{
            background-color: {c['panel_card_bg']};
        }}
        QTreeWidget::item:selected {{
            background-color: {c['accent']};
            color: {c['accent_text']};
        }}

        /* ── Line Edit ── */
        QLineEdit {{
            background-color: {c['input_bg']};
            color: {c['text_primary']};
            border: 1px solid {c['border_color']};
            border-radius: 2px;
            padding: 5px 8px;
            font-family: {MONO_FONT};
            font-size: 13px;
            selection-background-color: {c['accent']};
            selection-color: {c['accent_text']};
        }}
        QLineEdit:focus {{
            border-color: {c['accent']};
        }}
        QLineEdit:read-only {{
            color: {c['text_secondary']};
        }}

        /* ── Text Edit / Plain Text ── */
        QTextEdit, QPlainTextEdit {{
            background-color: {c['editor_bg']};
            color: {c['text_primary']};
            border: 1px solid {c['border_color']};
            border-radius: 2px;
            font-family: {MONO_FONT};
            font-size: 13px;
            selection-background-color: {c['accent']};
            selection-color: {c['accent_text']};
        }}
        QTextEdit:focus, QPlainTextEdit:focus {{
            border-color: {c['accent']};
        }}
        QTextBrowser {{
            background-color: {c['editor_bg']};
            color: {c['text_primary']};
            border: 1px solid {c['border_color']};
            border-radius: 2px;
            font-family: {MONO_FONT};
        }}

        /* ── ComboBox ── */
        QComboBox {{
            background-color: {c['input_bg']};
            color: {c['text_primary']};
            border: 1px solid {c['border_color']};
            border-radius: 2px;
            padding: 5px 8px;
            font-family: {MONO_FONT};
            font-size: 12px;
            min-height: 24px;
        }}
        QComboBox:hover {{
            border-color: {c['accent']};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 16px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {c['bg_card']};
            color: {c['text_primary']};
            border: 1px solid {c['border_color']};
            selection-background-color: {c['accent']};
            selection-color: {c['accent_text']};
            font-family: {MONO_FONT};
        }}

        /* ── Check Box ── */
        QCheckBox {{
            color: {c['text_primary']};
            font-family: {MONO_FONT};
            font-size: 13px;
            spacing: 6px;
        }}
        QCheckBox::indicator {{
            width: 14px;
            height: 14px;
            border: 1px solid {c['border_color']};
            border-radius: 2px;
            background-color: {c['input_bg']};
        }}
        QCheckBox::indicator:checked {{
            background-color: {c['accent']};
            border-color: {c['accent']};
        }}

        /* ── Radio Button ── */
        QRadioButton {{
            color: {c['text_primary']};
            font-family: {MONO_FONT};
            font-size: 13px;
            spacing: 6px;
        }}
        QRadioButton::indicator {{
            width: 14px;
            height: 14px;
            border: 1px solid {c['border_color']};
            border-radius: 7px;
            background-color: {c['input_bg']};
        }}
        QRadioButton::indicator:checked {{
            background-color: {c['accent']};
            border-color: {c['accent']};
        }}

        /* ── Slider ── */
        QSlider::groove:horizontal {{
            height: 4px;
            background-color: {c['border_color']};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background-color: {c['bg_card']};
            border: 2px solid {c['accent']};
            width: 14px;
            height: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }}
        QSlider::sub-page:horizontal {{
            background-color: {c['accent']};
            border-radius: 2px;
        }}

        /* ── Spin Box ── */
        QDoubleSpinBox, QSpinBox {{
            background-color: {c['input_bg']};
            color: {c['text_primary']};
            border: 1px solid {c['border_color']};
            border-radius: 2px;
            padding: 3px 6px;
            font-family: {MONO_FONT};
            font-size: 12px;
        }}
        QDoubleSpinBox:focus, QSpinBox:focus {{
            border-color: {c['accent']};
        }}

        /* ── Progress Bar ── */
        QProgressBar {{
            background-color: {c['border_color']};
            border: 1px solid {c['border_color']};
            border-radius: 2px;
            text-align: center;
            color: {c['text_primary']};
            font-family: {MONO_FONT};
            font-size: 11px;
            height: 16px;
        }}
        QProgressBar::chunk {{
            background-color: {c['accent']};
            border-radius: 2px;
        }}

        /* ── Group Box ── */
        QGroupBox {{
            color: {c['text_secondary']};
            font-family: {MONO_FONT};
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.8px;
            border: 1px solid {c['border_color']};
            border-radius: 2px;
            margin-top: 12px;
            padding-top: 8px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 6px;
            color: {c['text_secondary']};
        }}

        /* ── Dialog Button Box ── */
        QDialogButtonBox QPushButton {{
            background-color: {c['bg_card']};
            color: {c['text_primary']};
            border: 1px solid {c['border_color']};
            border-radius: 2px;
            font-family: {MONO_FONT};
            font-size: 12px;
            padding: 6px 14px;
            min-width: 72px;
        }}
        QDialogButtonBox QPushButton:hover {{
            background-color: {c['panel_card_bg']};
            border-color: {c['accent']};
        }}
        QDialogButtonBox QPushButton[text="OK"], QDialogButtonBox QPushButton[text="Apply"] {{
            background-color: {c['accent']};
            color: {c['accent_text']};
            border-color: {c['accent']};
        }}

        /* ── Menus ── */
        {menu_qss(c)}

        /* ── Scroll Area ── */
        QScrollArea {{
            border: none;
            background-color: transparent;
        }}
        QScrollArea > QWidget > QWidget {{
            background-color: transparent;
        }}

        /* ── Frame separators ── */
        QFrame[frameShape="4"], QFrame[frameShape="5"] {{
            color: {c['border_color']};
        }}
    """
