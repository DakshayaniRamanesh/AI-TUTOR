"""
Kestrel Collaboration WebSocket Server
Runs an embedded, non-blocking WebSocket server on a background thread.
Relays real-time whiteboard mutations, cursor events, and full-sync state between peers.
"""

import asyncio
import json
import threading
import uuid
import socket
from typing import Dict, Set, Optional, Any, Callable
import websockets
from PyQt6.QtCore import QObject, pyqtSignal

from .collab_protocol import (
    CollabMsgType, make_collab_message, DEFAULT_COLLAB_PORT, encode_room_code
)

# Palette of participant colors
PEER_COLORS = [
    "#8b5cf6", # Purple/Violet
    "#10b981", # Emerald Green
    "#3b82f6", # Vibrant Blue
    "#f59e0b", # Amber
    "#ec4899", # Pink
    "#06b6d4", # Cyan
    "#f97316", # Orange
]


class CollabServer(QObject):
    """
    WebSocket Collaboration Server running in a background asyncio event loop.
    Emits Qt signals when peers connect, disconnect, or errors occur.
    """
    # Signals for Qt thread UI updates
    server_started = pyqtSignal(str, int, str) # (host, port, room_code)
    server_stopped = pyqtSignal()
    peer_connected = pyqtSignal(str, str, str) # (client_id, name, color)
    peer_disconnected = pyqtSignal(str, str)   # (client_id, name)
    error_occurred = pyqtSignal(str)

    def __init__(self, host: str = "0.0.0.0", port: int = DEFAULT_COLLAB_PORT, host_display_ip: str = "127.0.0.1", parent=None):
        super().__init__(parent)
        self.bind_host = host
        self.port = port
        self.host_display_ip = host_display_ip
        self.room_code = encode_room_code(self.host_display_ip, self.port)

        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server = None
        self._is_running = False

        # Active websocket connections: websocket -> client_info dict
        self._clients: Dict[Any, Dict[str, Any]] = {}
        # Lock for thread-safe access to clients
        self._lock = threading.Lock()

        # Canvas sync provider callback (called in host thread to get latest scene dict)
        self.canvas_sync_provider: Optional[Callable[[], Dict[str, Any]]] = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    def get_connected_peers(self) -> list:
        with self._lock:
            return list(self._clients.values())

    def start(self):
        """Starts the server in a separate daemon thread."""
        if self._is_running:
            return
        self._is_running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="CollabServerThread")
        self._thread.start()

    def stop(self):
        """Stops the server and closes all active connections."""
        if not self._is_running:
            return
        self._is_running = False
        if self._loop and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._shutdown_coroutine(), self._loop)
            try:
                future.result(timeout=2.0)
            except Exception:
                pass
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self.server_stopped.emit()

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._start_server_async())
            self._loop.run_forever()
        except Exception as err:
            self.error_occurred.emit(f"Server error: {err}")
        finally:
            self._loop.close()
            self._is_running = False

    async def _start_server_async(self):
        # Try binding to port; if occupied, try next 5 ports
        port_to_try = self.port
        bound_server = None
        max_attempts = 10

        for attempt in range(max_attempts):
            try:
                bound_server = await websockets.serve(
                    self._handler,
                    self.bind_host,
                    port_to_try,
                    max_size=20 * 1024 * 1024, # 20MB limit for full boards with images
                    ping_interval=20,
                    ping_timeout=20,
                )
                self.port = port_to_try
                self.room_code = encode_room_code(self.host_display_ip, self.port)
                break
            except OSError as err:
                if attempt < max_attempts - 1:
                    port_to_try += 1
                else:
                    raise err

        self._server = bound_server
        self.server_started.emit(self.host_display_ip, self.port, self.room_code)

    async def _shutdown_coroutine(self):
        # Close all active client connections
        with self._lock:
            active_ws = list(self._clients.keys())
        for ws in active_ws:
            try:
                await ws.close(code=1000, reason="Server shutting down")
            except Exception:
                pass
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _handler(self, websocket):
        client_id = uuid.uuid4().hex[:8]
        assigned_color = PEER_COLORS[len(self._clients) % len(PEER_COLORS)]
        client_info = {
            "client_id": client_id,
            "name": f"User-{client_id[:4]}",
            "color": assigned_color,
            "connected_at": asyncio.get_event_loop().time(),
        }

        with self._lock:
            self._clients[websocket] = client_info

        try:
            async for raw_message in websocket:
                try:
                    msg = json.loads(raw_message)
                    await self._process_client_message(websocket, client_info, msg)
                except json.JSONDecodeError:
                    continue
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            with self._lock:
                removed_info = self._clients.pop(websocket, None)

            if removed_info:
                # Notify remaining peers
                leave_msg = json.dumps(make_collab_message(
                    CollabMsgType.PEER_LEFT,
                    removed_info["client_id"],
                    {"name": removed_info["name"]}
                ))
                await self._broadcast_raw(leave_msg, exclude_ws=websocket)
                self.peer_disconnected.emit(removed_info["client_id"], removed_info["name"])

    async def _process_client_message(self, sender_ws, client_info: Dict[str, Any], msg: Dict[str, Any]):
        msg_type = msg.get("type")

        if msg_type == CollabMsgType.JOIN:
            user_name = msg.get("name", client_info["name"])
            client_info["name"] = user_name
            if "color" in msg:
                client_info["color"] = msg["color"]

            # Send WELCOME message to the joining client
            with self._lock:
                peers_list = [
                    {"client_id": c["client_id"], "name": c["name"], "color": c["color"]}
                    for ws, c in self._clients.items()
                ]

            welcome = make_collab_message(
                CollabMsgType.WELCOME,
                client_info["client_id"],
                {
                    "assigned_id": client_info["client_id"],
                    "color": client_info["color"],
                    "peers": peers_list,
                    "room_code": self.room_code,
                }
            )
            await sender_ws.send(json.dumps(welcome))

            # Broadcast PEER_JOINED to other clients
            joined_broadcast = json.dumps(make_collab_message(
                CollabMsgType.PEER_JOINED,
                client_info["client_id"],
                {"name": client_info["name"], "color": client_info["color"]}
            ))
            await self._broadcast_raw(joined_broadcast, exclude_ws=sender_ws)
            self.peer_connected.emit(client_info["client_id"], client_info["name"], client_info["color"])

        elif msg_type == CollabMsgType.SYNC_REQUEST:
            # Client wants current canvas state
            canvas_data = None
            if self.canvas_sync_provider:
                try:
                    canvas_data = self.canvas_sync_provider()
                except Exception as err:
                    print(f"[CollabServer] Error getting canvas sync: {err}")

            if canvas_data:
                sync_resp = make_collab_message(
                    CollabMsgType.SYNC_RESPONSE,
                    "server",
                    {"board": canvas_data}
                )
                await sender_ws.send(json.dumps(sync_resp))

        elif msg_type == CollabMsgType.PING:
            pong = make_collab_message(CollabMsgType.PONG, client_info["client_id"])
            await sender_ws.send(json.dumps(pong))

        else:
            # Relay standard mutation and cursor messages to all other peers
            raw_msg = json.dumps(msg)
            await self._broadcast_raw(raw_msg, exclude_ws=sender_ws)

    async def _broadcast_raw(self, payload: str, exclude_ws=None):
        with self._lock:
            targets = [ws for ws in self._clients.keys() if ws != exclude_ws]

        if not targets:
            return

        # Broadcast concurrently
        tasks = []
        for ws in targets:
            tasks.append(asyncio.create_task(self._safe_send(ws, payload)))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_send(self, ws, payload: str):
        try:
            await ws.send(payload)
        except Exception:
            pass
