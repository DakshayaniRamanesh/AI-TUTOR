"""
PyQt6 Application Entry Point & Bootstrap with Animated Splash Screen

Strategy:
 - Splash appears in ~100 ms on the main thread.
 - A background thread does only the slow *imports* (qdrant, sqlalchemy, etc.)
   — no widget or QObject creation happens there.
 - When imports are finished the thread signals the main thread, which then
   runs bootstrap_db() + MainWindow() safely on the main thread.
"""

import sys
import os
from dotenv import load_dotenv

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
from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal


class _ImportPreloader(QObject):
    """
    Lives on a background QThread.
    Only does module-level imports — never creates any QWidget or QObject child.
    Signals the main thread when done so it can safely build MainWindow.
    """
    status  = pyqtSignal(str)   # progress text for the splash
    ready   = pyqtSignal()      # imports done — main thread should now build window
    failed  = pyqtSignal(str)   # fatal error

    def run(self):
        try:
            self.status.emit("Setting up database…")
            try:
                from app.storage.database_ops import bootstrap_db
                bootstrap_db()
            except Exception as e:
                print(f"[DB] Migration failed: {e}")

            self.status.emit("Loading modules…")
            # Trigger the slow imports now (qdrant_client, sqlalchemy, etc.)
            import app.ui.main_window          # noqa: F401 — side-effect import only

            self.status.emit("Ready.")
            self.ready.emit()

        except Exception:
            import traceback
            self.failed.emit(traceback.format_exc())


def main():
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        q_app = QApplication(sys.argv)
        q_app.setApplicationName("Kestrel")
        q_app.setStyle("Fusion")

        # ── Splash appears immediately (main thread) ───────────────────────
        from app.ui.splash_screen import SplashScreen
        splash = SplashScreen(duration_ms=2400)
        splash.show()
        q_app.processEvents()

        # ── Background thread: heavy imports only ──────────────────────────
        preloader = _ImportPreloader()
        thread = QThread()
        preloader.moveToThread(thread)
        thread.started.connect(preloader.run)

        if hasattr(splash, "set_status"):
            preloader.status.connect(splash.set_status)

        window_ref: list = []

        def _on_imports_ready():
            """Called on the MAIN THREAD via Qt signal — safe to build widgets."""
            thread.quit()
            from app.ui.main_window import MainWindow   # already imported; instant
            w = MainWindow()
            window_ref.append(w)
            # If splash already finished, show immediately; otherwise wait for it.
            if not splash.isVisible():
                w.show()

        def _on_failed(msg: str):
            print(f"[Fatal Loader Error]\n{msg}", file=sys.stderr)
            with open("crash.log", "a", encoding="utf-8") as f:
                f.write(msg + "\n")
            thread.quit()
            q_app.quit()

        # ready signal → main thread (Qt auto-connects cross-thread signals via
        # QueuedConnection, so _on_imports_ready runs on the main thread's loop)
        preloader.ready.connect(_on_imports_ready, Qt.ConnectionType.QueuedConnection)
        preloader.failed.connect(_on_failed,       Qt.ConnectionType.QueuedConnection)

        def _on_splash_finished():
            """Splash fade-out done — show window if loader already finished."""
            if window_ref:
                window_ref[0].show()
            # else: window not ready yet — _on_imports_ready will call .show()

        splash.finished.connect(_on_splash_finished)

        q_app.setQuitOnLastWindowClosed(False)
        thread.start()

        ret = q_app.exec()
        thread.wait(3000)
        sys.exit(ret)

    except Exception:
        import traceback
        err_msg = traceback.format_exc()
        print(f"[Fatal App Error] {err_msg}", file=sys.stderr)
        with open("crash.log", "a", encoding="utf-8") as f:
            f.write(err_msg + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
