"""
PyQt6 Application Entry Point & Bootstrap with Animated Splash Screen
"""

import sys
import os
from dotenv import load_dotenv

# Ensure root directory is on Python path and prevent namespace collision with app/
current_dir = os.path.abspath(os.path.dirname(__file__))
if current_dir in sys.path:
    sys.path.remove(current_dir)
if "" in sys.path:
    sys.path.remove("")
sys.path.insert(0, os.path.abspath(os.path.join(current_dir, "..")))
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

def main():
    try:
        # Enable High DPI scaling
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        
        q_app = QApplication(sys.argv)
        q_app.setApplicationName("Kestrel")
        q_app.setStyle("Fusion")

        # ── Database Setup (Safe to run now that QApplication exists) ──
        try:
            from app.storage.database_ops import bootstrap_db
            bootstrap_db()
        except Exception as e:
            print(f"[DB] Migration failed: {e}")

        # ── Now safe to import UI ──
        from app.ui.splash_screen import SplashScreen
        
        from app.ui.main_window import MainWindow

        print("[MAIN] Displaying splash screen", flush=True)
        # Display animated intro splash screen with Kestrel logo animation
        splash = SplashScreen(duration_ms=2200)
        splash.show()
        q_app.processEvents()

        print("[MAIN] Instantiating MainWindow", flush=True)
        # Initialize main window in background while splash animates
        window = MainWindow()

        print("[MAIN] Connecting signals", flush=True)
        # When splash finishes fade-out, reveal the main window
        splash.finished.connect(window.show)
        
        q_app.setQuitOnLastWindowClosed(False)

        print("[MAIN] Calling q_app.exec()", flush=True)
        ret = q_app.exec()
        print(f"[MAIN] q_app.exec() returned {ret}", flush=True)
        sys.exit(ret)
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        print(f"[Fatal App Error] {err_msg}", file=sys.stderr)
        with open("crash.log", "a", encoding="utf-8") as f:
            f.write(err_msg + "\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
