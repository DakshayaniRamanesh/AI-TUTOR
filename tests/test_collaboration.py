import time
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from PyQt6.QtCore import QCoreApplication

from app.collaboration.collab_protocol import (
    get_local_ip_addresses, encode_room_code, decode_room_code,
    generate_share_link, make_collab_message, CollabMsgType
)
from app.collaboration.collab_server import CollabServer
from app.collaboration.collab_client import CollabClient


def test_ip_discovery():
    ips = get_local_ip_addresses()
    assert len(ips) > 0
    # At least loopback or local ip exists
    ip_strings = [ip for ip, desc in ips]
    assert any("127.0.0.1" in ip or "192.168." in ip or "10." in ip or "100." in ip for ip in ip_strings)


def test_room_code_encode_decode():
    host = "192.168.1.50"
    port = 8765

    # 1. Hex encoding for standard IPv4
    code = encode_room_code(host, port)
    assert code.startswith("KEST-")
    
    decoded = decode_room_code(code)
    assert decoded is not None
    assert decoded[0] == host
    assert decoded[1] == port

    # 2. Raw IP:port input
    raw = f"{host}:{port}"
    decoded_raw = decode_room_code(raw)
    assert decoded_raw == (host, port)

    # 3. Share link format
    link = generate_share_link(host, port, code)
    assert "kestrel://collab/" in link
    decoded_link = decode_room_code(link)
    assert decoded_link == (host, port)

    # 4. Tailscale / arbitrary IP
    ts_ip = "100.127.255.152"
    ts_code = encode_room_code(ts_ip, 9000)
    assert decode_room_code(ts_code) == (ts_ip, 9000)


def test_collab_server_client_roundtrip():
    # Ensure QCoreApplication exists for signals
    app = QCoreApplication.instance()
    if not app:
        app = QCoreApplication([])

    test_port = 8991
    server = CollabServer(host="127.0.0.1", port=test_port, host_display_ip="127.0.0.1")
    
    # Mock canvas sync provider
    mock_board = {
        "items": [{"item_id": "note-1", "type": "StickyNote", "text": "Hello Collab"}],
        "background_mode": "ruled"
    }
    server.canvas_sync_provider = lambda: mock_board
    server.start()
    time.sleep(0.3)

    # Connect Client A (Host user)
    client_a = CollabClient(user_name="Alice")
    received_by_a = []
    client_a.item_added.connect(lambda item: received_by_a.append(("add", item)))
    client_a.item_updated.connect(lambda item: received_by_a.append(("update", item)))
    client_a.connect_to_host("127.0.0.1", server.port)

    # Connect Client B (Guest user)
    client_b = CollabClient(user_name="Bob")
    received_by_b = []
    sync_received_by_b = []
    client_b.sync_received.connect(lambda board: sync_received_by_b.append(board))
    client_b.item_added.connect(lambda item: received_by_b.append(("add", item)))
    client_b.cursor_moved.connect(lambda cid, name, col, x, y: received_by_b.append(("cursor", x, y)))
    client_b.connect_to_host("127.0.0.1", server.port)

    # Process events to allow async handshakes
    for _ in range(30):
        app.processEvents()
        time.sleep(0.05)
        if client_a.is_connected and client_b.is_connected and sync_received_by_b:
            break

    assert client_a.is_connected
    assert client_b.is_connected
    # Client B must have received initial board sync
    assert len(sync_received_by_b) >= 1
    assert sync_received_by_b[0]["items"][0]["item_id"] == "note-1"

    # Client A creates a stroke
    test_stroke = {
        "item_id": "stroke-99",
        "type": "InkStroke",
        "color": "#1c1c1e",
        "width": 3.0,
        "elements": [{"type": 0, "x": 10, "y": 10}, {"type": 1, "x": 50, "y": 50}]
    }
    client_a.send_item_add(test_stroke)

    for _ in range(20):
        app.processEvents()
        time.sleep(0.05)
        if any(msg[0] == "add" and msg[1]["item_id"] == "stroke-99" for msg in received_by_b):
            break

    # Client B must have received Client A's stroke
    assert any(msg[0] == "add" and msg[1]["item_id"] == "stroke-99" for msg in received_by_b)

    # Client A moves cursor
    client_a.send_cursor_move(120.5, 340.0)

    for _ in range(20):
        app.processEvents()
        time.sleep(0.05)
        if any(msg[0] == "cursor" for msg in received_by_b):
            break

    assert any(msg[0] == "cursor" and msg[1] == 120.5 for msg in received_by_b)

    # Client B updates a sticky note
    updated_note = {
        "item_id": "note-1",
        "type": "StickyNote",
        "text": "Simultaneous collaboration works!",
        "x": 200,
        "y": 300
    }
    client_b.send_item_update(updated_note)

    for _ in range(20):
        app.processEvents()
        time.sleep(0.05)
        if any(msg[0] == "update" and msg[1]["text"] == "Simultaneous collaboration works!" for msg in received_by_a):
            break

    assert any(msg[0] == "update" and msg[1]["item_id"] == "note-1" for msg in received_by_a)

    # Clean teardown
    client_a.disconnect()
    client_b.disconnect()
    server.stop()
    for _ in range(5):
        app.processEvents()
        time.sleep(0.05)


if __name__ == "__main__":
    test_ip_discovery()
    test_room_code_encode_decode()
    test_collab_server_client_roundtrip()
    print("All collaboration tests PASSED successfully!")
