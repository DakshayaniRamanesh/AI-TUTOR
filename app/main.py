"""
PyQt6 Application Entry Point & Bootstrap with Animated Splash Screen
"""

import sys
import os
from dotenv import load_dotenv

# Ensure root directory is on Python path and load environment variables
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from app.ui.main_window import MainWindow
from app.ui.splash_screen import SplashScreen

def main():
    try:
        # Enable High DPI scaling
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        
        app = QApplication(sys.argv)
        app.setApplicationName("Kestrel")
        app.setStyle("Fusion")

        # Display animated intro splash screen with Kestrel logo animation
        splash = SplashScreen(duration_ms=2200)
        splash.show()
        app.processEvents()

        # Initialize main window in background while splash animates
        window = MainWindow()

        # When splash finishes fade-out, reveal the main window
        splash.finished.connect(window.show)
        
        sys.exit(app.exec())
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        print(f"[Fatal App Error] {err_msg}", file=sys.stderr)
        with open("crash.log", "a", encoding="utf-8") as f:
            f.write(err_msg + "\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
