"""
End-to-End Canvas Collaboration Integration Test
Verifies that real CanvasScene instances synchronize strokes, sticky notes,
remote cursors, text changes, moves, and deletions across host and guest.
"""

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPointF, QTimer
from PyQt6.QtGui import QPainterPath

from app.ui.canvas_scene import CanvasScene
from app.ui.items.sticky_note import StickyNote
from app.ui.items.ink_stroke import InkStroke
from app.ui.items.remote_cursor import RemoteCollaboratorCursor
from app.collaboration.collab_session_manager import CollabSessionManager, CollabRole
from app.collaboration.collab_client import CollabClient
from app.collaboration.collab_server import CollabServer


def test_canvas_e2e_collaboration():
    app = QApplication.instance()
    if not app:
        app = QApplication([])

    test_port = 8993

    # 1. Setup Host Environment
    host_scene = CanvasScene()
    host_server = CollabServer(host="127.0.0.1", port=test_port, host_display_ip="127.0.0.1")
    host_server.canvas_sync_provider = lambda: {
        "items": host_scene.to_dict_list(),
        "background_mode": host_scene.background_mode
    }
    host_server.start()
    time.sleep(0.2)

    # Host client
    host_client = CollabClient(user_name="Teacher")
    host_client.item_added.connect(host_scene.apply_remote_item_add)
    host_client.item_updated.connect(host_scene.apply_remote_item_update)
    host_client.item_deleted.connect(host_scene.apply_remote_item_delete)
    host_client.cursor_moved.connect(host_scene.apply_remote_cursor)
    host_client.connect_to_host("127.0.0.1", test_port)

    # Wire host scene outbound to host client
    host_scene.item_collaborated_add.connect(host_client.send_item_add)
    host_scene.item_collaborated_update.connect(host_client.send_item_update)
    host_scene.item_collaborated_delete.connect(host_client.send_item_delete)
    host_scene.cursor_collaborated_move.connect(host_client.send_cursor_move)

    # 2. Setup Guest Environment
    guest_scene = CanvasScene()
    guest_client = CollabClient(user_name="Student")
    sync_done = []
    guest_client.sync_received.connect(lambda b: (guest_scene.apply_remote_sync(b), sync_done.append(True)))
    guest_client.item_added.connect(guest_scene.apply_remote_item_add)
    guest_client.item_updated.connect(guest_scene.apply_remote_item_update)
    guest_client.item_deleted.connect(guest_scene.apply_remote_item_delete)
    guest_client.cursor_moved.connect(guest_scene.apply_remote_cursor)
    guest_client.connect_to_host("127.0.0.1", test_port)

    # Wire guest scene outbound to guest client
    guest_scene.item_collaborated_add.connect(guest_client.send_item_add)
    guest_scene.item_collaborated_update.connect(guest_client.send_item_update)
    guest_scene.item_collaborated_delete.connect(guest_client.send_item_delete)
    guest_scene.cursor_collaborated_move.connect(guest_client.send_cursor_move)

    # Wait for handshake and initial sync
    for _ in range(40):
        app.processEvents()
        time.sleep(0.05)
        if host_client.is_connected and guest_client.is_connected and sync_done:
            break

    assert host_client.is_connected
    assert guest_client.is_connected
    assert len(sync_done) > 0

    # 3. Host adds an InkStroke
    path = QPainterPath()
    path.moveTo(0, 0)
    path.lineTo(100, 100)
    stroke = InkStroke(path=path, tool_mode="pen", color="#ff0000", width=4.0)
    stroke_id = stroke.item_id
    host_scene.addItem(stroke)
    host_scene.item_collaborated_add.emit(stroke.to_dict())

    for _ in range(25):
        app.processEvents()
        time.sleep(0.05)
        if guest_scene.find_item_by_id(stroke_id):
            break

    # Assert Guest received stroke
    guest_stroke = guest_scene.find_item_by_id(stroke_id)
    assert guest_stroke is not None
    assert guest_stroke.stroke_width == 4.0

    # 4. Guest creates a StickyNote
    guest_note = StickyNote(text="Notes from Student", color_key="yellow")
    guest_note.setPos(150, 200)
    note_id = guest_note.item_id
    guest_scene.addItem(guest_note)
    guest_scene.item_collaborated_add.emit(guest_note.to_dict())

    for _ in range(25):
        app.processEvents()
        time.sleep(0.05)
        if host_scene.find_item_by_id(note_id):
            break

    # Assert Host received StickyNote
    host_note = host_scene.find_item_by_id(note_id)
    assert host_note is not None
    assert host_note.widget.text_edit.toPlainText() == "Notes from Student"
    assert host_note.x() == 150
    assert host_note.y() == 200

    # 5. Host moves StickyNote to (300, 400)
    host_note.setPos(300, 400)
    host_scene.item_collaborated_update.emit(host_note.to_dict())

    for _ in range(25):
        app.processEvents()
        time.sleep(0.05)
        item_on_guest = guest_scene.find_item_by_id(note_id)
        if item_on_guest and item_on_guest.x() == 300:
            break

    item_on_guest = guest_scene.find_item_by_id(note_id)
    assert item_on_guest is not None
    assert item_on_guest.x() == 300
    assert item_on_guest.y() == 400

    # 6. Guest updates StickyNote text
    item_on_guest.widget.text_edit.setPlainText("Updated text collaboratively!")
    # Note: textChanged emits item_collaborated_update automatically via our earlier hook!

    for _ in range(20):
        app.processEvents()
        time.sleep(0.05)
        if host_note.widget.text_edit.toPlainText() == "Updated text collaboratively!":
            break

    assert host_note.widget.text_edit.toPlainText() == "Updated text collaboratively!"

    # 7. Host moves cursor -> Guest receives remote collaborator pointer
    host_scene.cursor_collaborated_move.emit(250.0, 350.0)

    for _ in range(20):
        app.processEvents()
        time.sleep(0.05)
        if host_client.client_id in guest_scene._remote_cursors:
            break

    assert host_client.client_id in guest_scene._remote_cursors
    cursor = guest_scene._remote_cursors[host_client.client_id]
    assert cursor.x() == 250.0
    assert cursor.y() == 350.0
    assert cursor.name == "Teacher"

    # 8. Host erases the initial stroke
    host_scene.item_collaborated_delete.emit([stroke_id])
    host_scene.removeItem(stroke)

    for _ in range(20):
        app.processEvents()
        time.sleep(0.05)
        if guest_scene.find_item_by_id(stroke_id) is None:
            break

    assert guest_scene.find_item_by_id(stroke_id) is None

    # Clean Teardown
    guest_client.disconnect()
    host_client.disconnect()
    host_server.stop()
    for _ in range(5):
        app.processEvents()
        time.sleep(0.05)

    print("End-to-End Canvas Collaboration test PASSED successfully!")


if __name__ == "__main__":
    test_canvas_e2e_collaboration()
