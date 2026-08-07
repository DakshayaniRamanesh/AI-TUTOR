"""
Unit tests for ThemeManager and LatexEditorWidget
"""

import pytest
from PyQt6.QtWidgets import QApplication

from app.ui.theme_manager import ThemeManager
from app.ui.widgets.latex_editor_widget import LatexEditorWidget

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_theme_manager_toggle():
    tm = ThemeManager.instance()
    initial_theme = tm.current_theme
    toggled = tm.toggle_theme()
    assert toggled != initial_theme
    assert tm.current_theme == toggled
    
    # Toggle back
    tm.toggle_theme()
    assert tm.current_theme == initial_theme

def test_theme_manager_colors():
    tm = ThemeManager.instance()
    colors = tm.get_colors()
    assert "bg_card" in colors
    assert "canvas_bg" in colors
    assert "accent" in colors

def test_latex_editor_widget(qapp):
    widget = LatexEditorWidget()
    sample_code = r"\documentclass{article}\begin{document}E = mc^2\end{document}"
    widget.set_latex_code(sample_code, title="Test Equation")
    
    assert widget.get_latex_code() == sample_code
    assert "Test Equation" in widget.lbl_title.text()
