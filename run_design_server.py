"""
Lightweight Design Server for Figma Export
Runs a local web server hosting the UI/UX design suite for Figma import.
"""

import http.server
import socketserver
import webbrowser
import os
import sys

PORT = 8080
DIRECTORY = os.path.join(os.path.dirname(__file__), "ui_figma_exporter")

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

def main():
    os.chdir(DIRECTORY)
    print("=" * 60)
    print("  🎨 AI TUTOR UI/UX FIGMA SUITE IS READY")
    print("=" * 60)
    print(f"  Local URL: http://localhost:{PORT}")
    print("\n  👉 How to export to Figma in 2 minutes:")
    print("  1. Open Figma -> Create a new design file.")
    print("  2. Search & run plugin: 'html.to.design'")
    print(f"  3. Enter URL: http://localhost:{PORT}")
    print("  4. Click 'Import' -> 100% native Figma Auto-Layout layers created!")
    print("=" * 60)
    print("  Press Ctrl+C to stop server.\n")

    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            try:
                webbrowser.open(f"http://localhost:{PORT}")
            except Exception:
                pass
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")

if __name__ == "__main__":
    main()
