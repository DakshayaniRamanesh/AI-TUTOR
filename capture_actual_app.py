"""
Capture Actual PyQt6 App Screenshots directly from the Qt Engine.
Zero modifications to original app code.
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer
from app.ui.main_window import MainWindow

def run_capture():
    app = QApplication(sys.argv)
    app.setApplicationName("Kestrel")
    app.setStyle("Fusion")

    os.makedirs("app_screenshots", exist_ok=True)

    window = MainWindow()
    window.resize(1440, 900)
    window.show()

    def capture_screens():
        # 1. Main Home View
        pixmap_main = window.grab()
        pixmap_main.save("app_screenshots/01_actual_main_canvas.png")
        print(" Saved: app_screenshots/01_actual_main_canvas.png")

        # 2. Switch to Canvas View to show the AskBar & Feather button
        window.home_view.btn_blank.click()
        QTimer.singleShot(800, capture_canvas)

    def capture_canvas():
        pixmap_canvas = window.grab()
        pixmap_canvas.save("app_screenshots/02_canvas_with_feather_button.png")
        print(" Saved: app_screenshots/02_canvas_with_feather_button.png")

        # 3. Trigger feather button to show active "Feathering…" state
        window.feather_button.btn_feather.click()
        QTimer.singleShot(800, capture_feathering)

    def capture_feathering():
        pixmap_active = window.grab()
        pixmap_active.save("app_screenshots/03_feathering_active_state.png")
        print(" Saved: app_screenshots/03_feathering_active_state.png")

        # 4. Switch to Obsidian Knowledge Graph View
        window.main_stack.setCurrentWidget(window.obsidian_graph_panel)
        QTimer.singleShot(800, capture_knowledge_graph)

    def capture_knowledge_graph():
        pixmap_kg = window.grab()
        pixmap_kg.save("app_screenshots/04_main_knowledge_graph.png")
        print(" Saved: app_screenshots/04_main_knowledge_graph.png")
        app.quit()

    # Trigger capture after UI initializes
    QTimer.singleShot(1500, capture_screens)
    sys.exit(app.exec())

if __name__ == "__main__":
    run_capture()
