import sys, os
sys.path.insert(0, os.path.abspath("."))
from dotenv import load_dotenv
load_dotenv()
load_dotenv("backend/.env")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer
from app.ui.main_window import MainWindow

app = QApplication(sys.argv)
app.setApplicationName("Kestrel")
app.setStyle("Fusion")

os.makedirs("app_screenshots", exist_ok=True)

window = MainWindow()
window.resize(1440, 900)
window.show()

def capture():
    # Navigate to canvas view
    window.main_stack.setCurrentWidget(window._canvas_wrapper)
    
    def do_capture():
        pixmap = window.grab()
        pixmap.save("app_screenshots/02_canvas_with_circle_toolbar.png")
        print("Saved: app_screenshots/02_canvas_with_circle_toolbar.png")
        app.quit()
    
    QTimer.singleShot(600, do_capture)

QTimer.singleShot(400, capture)
sys.exit(app.exec())