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
        # 1. Main Default View
        pixmap_main = window.grab()
        pixmap_main.save("app_screenshots/01_actual_main_canvas.png")
        print(" Saved: app_screenshots/01_actual_main_canvas.png")

        # Exit
        app.quit()

    # Trigger capture after UI initializes
    QTimer.singleShot(1500, capture_screens)
    sys.exit(app.exec())

if __name__ == "__main__":
    run_capture()
