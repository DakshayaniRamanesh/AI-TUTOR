"""
Kestrel Collaboration WebSocket Client
Connects to a host session over WebSocket, synchronizes initial canvas state,
and streams real-time mutations and remote cursor events.
"""

import asyncio
import json
import threading
import uuid
import time
from typing import Optional, Dict, Any, List
import websockets
from PyQt6.QtCore import QObject, pyqtSignal

from .collab_protocol import (
    CollabMsgType, make_collab_message
)


class CollabClient(QObject):
    """
    WebSocket Collaboration Client running in a background asyncio event loop.
    Communicates with PyQt main thread via thread-safe signals.
    """
    # Connection state signals
    connected = pyqtSignal(str, str, str)   # (room_code, client_id, color)
    disconnected = pyqtSignal(str)          # (reason)
    connection_failed = pyqtSignal(str)     # (error_message)

    # Canvas sync signals
    sync_received = pyqtSignal(dict)        # (board_data)
    item_added = pyqtSignal(dict)           # (item_dict)
    item_updated = pyqtSignal(dict)         # (item_dict)
    item_deleted = pyqtSignal(list)         # (item_ids)
    cursor_moved = pyqtSignal(str, str, str, float, float) # (client_id, name, color, x, y)
    canvas_cleared = pyqtSignal()
    bg_changed = pyqtSignal(str)            # (background_mode)

    # Peer signals
    peer_joined = pyqtSignal(str, str)      # (name, color)
    peer_left = pyqtSignal(str)             # (name)

    def __init__(self, user_name: str = "User", parent=None):
        super().__init__(parent)
        self.user_name = user_name
        self.client_id = uuid.uuid4().hex[:8]
        self.user_color = "#3b82f6"
        self.room_code = ""

        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws = None
        self._send_queue: Optional[asyncio.Queue] = None
        self._is_connected = False
        self._should_run = False
        self._server_url = ""

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    def connect_to_host(self, host: str, port: int):
        """Initiates connection to the host."""
        if self._is_connected:
            self.disconnect()

        # Format ws URL
        if not host.startswith("ws://") and not host.startswith("wss://"):
            self._server_url = f"ws://{host}:{port}"
        else:
            self._server_url = host

        self._should_run = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="CollabClientThread")
        self._thread.start()

    def disconnect(self):
        """Disconnects cleanly from the host."""
        self._should_run = False
        self._is_connected = False
        if self._loop and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._shutdown_coroutine(), self._loop)
            try:
                future.result(timeout=2.0)
            except Exception:
                pass
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    # ── Thread-Safe Outgoing Event Queuing ─────────────────────────────────────

    def send_item_add(self, item_data: dict):
        self._queue_message(CollabMsgType.ITEM_ADD, {"item": item_data})

    def send_item_update(self, item_data: dict):
        self._queue_message(CollabMsgType.ITEM_UPDATE, {"item": item_data})

    def send_item_delete(self, item_ids: list):
        self._queue_message(CollabMsgType.ITEM_DELETE, {"item_ids": item_ids})

    def send_cursor_move(self, x: float, y: float):
        self._queue_message(CollabMsgType.CURSOR_MOVE, {
            "name": self.user_name,
            "color": self.user_color,
            "x": x,
            "y": y
        })

    def send_canvas_clear(self):
        self._queue_message(CollabMsgType.CANVAS_CLEAR)

    def send_bg_change(self, mode: str):
        self._queue_message(CollabMsgType.BG_CHANGE, {"mode": mode})

    def _queue_message(self, msg_type: str, extra: dict = None):
        if not self._is_connected or not self._loop or not self._send_queue:
            return
        payload = make_collab_message(msg_type, self.client_id, extra)
        asyncio.run_coroutine_threadsafe(self._send_queue.put(payload), self._loop)

    # ── Asyncio Event Loop Worker ─────────────────────────────────────────────

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._client_session())
        except Exception as err:
            if self._should_run:
                try:
                    self.connection_failed.emit(f"Could not connect to {self._server_url}: {err}")
                except Exception:
                    pass
        finally:
            try:
                pending = [t for t in asyncio.all_tasks(self._loop) if not t.done()]
                for t in pending:
                    t.cancel()
                if pending and not self._loop.is_closed():
                    self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            try:
                self._loop.close()
            except Exception:
                pass
            self._is_connected = False

    async def _shutdown_coroutine(self):
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass

    async def _client_session(self):
        try:
            async with websockets.connect(
                self._server_url,
                max_size=20 * 1024 * 1024,
                open_timeout=8.0,
                ping_interval=20,
                ping_timeout=20,
            ) as ws:
                self._ws = ws
                self._send_queue = asyncio.Queue()
                self._is_connected = True

                # 1. Send JOIN
                join_msg = make_collab_message(
                    CollabMsgType.JOIN,
                    self.client_id,
                    {"name": self.user_name}
                )
                await ws.send(json.dumps(join_msg))

                # 2. Run read and write tasks concurrently
                reader_task = asyncio.create_task(self._reader_loop(ws))
                writer_task = asyncio.create_task(self._writer_loop(ws))

                # 3. Send initial canvas SYNC_REQUEST
                await asyncio.sleep(0.1)
                sync_req = make_collab_message(CollabMsgType.SYNC_REQUEST, self.client_id)
                await self._send_queue.put(sync_req)

                done, pending = await asyncio.wait(
                    [reader_task, writer_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                for task in pending:
                    task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)

        except Exception as err:
            self._is_connected = False
            if self._should_run:
                try:
                    self.connection_failed.emit(f"Could not connect to {self._server_url}: {err}")
                except Exception:
                    pass
        finally:
            self._is_connected = False
            try:
                self.disconnected.emit("Connection closed")
            except Exception:
                pass

    async def _writer_loop(self, ws):
        try:
            while self._should_run:
                msg = await self._send_queue.get()
                try:
                    await ws.send(json.dumps(msg))
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    async def _reader_loop(self, ws):
        try:
            async for raw_message in ws:
                try:
                    msg = json.loads(raw_message)
                    self._handle_incoming_message(msg)
                except json.JSONDecodeError:
                    continue
        except (asyncio.CancelledError, Exception):
            pass

    def _handle_incoming_message(self, msg: Dict[str, Any]):
        sender_id = msg.get("client_id", "")
        # Ignore self reflections
        if sender_id == self.client_id:
            return

        msg_type = msg.get("type")

        if msg_type == CollabMsgType.WELCOME:
            self.client_id = msg.get("assigned_id", self.client_id)
            self.user_color = msg.get("color", self.user_color)
            self.room_code = msg.get("room_code", "")
            self.connected.emit(self.room_code, self.client_id, self.user_color)

        elif msg_type == CollabMsgType.SYNC_RESPONSE:
            board = msg.get("board", {})
            self.sync_received.emit(board)

        elif msg_type == CollabMsgType.ITEM_ADD:
            item = msg.get("item")
            if item:
                self.item_added.emit(item)

        elif msg_type == CollabMsgType.ITEM_UPDATE:
            item = msg.get("item")
            if item:
                self.item_updated.emit(item)

        elif msg_type == CollabMsgType.ITEM_DELETE:
            item_ids = msg.get("item_ids", [])
            if item_ids:
                self.item_deleted.emit(item_ids)

        elif msg_type == CollabMsgType.CURSOR_MOVE:
            name = msg.get("name", "Peer")
            color = msg.get("color", "#8b5cf6")
            x = float(msg.get("x", 0.0))
            y = float(msg.get("y", 0.0))
            self.cursor_moved.emit(sender_id, name, color, x, y)

        elif msg_type == CollabMsgType.CANVAS_CLEAR:
            self.canvas_cleared.emit()

        elif msg_type == CollabMsgType.BG_CHANGE:
            mode = msg.get("mode", "blank")
            self.bg_changed.emit(mode)

        elif msg_type == CollabMsgType.PEER_JOINED:
            name = msg.get("name", "New Peer")
            color = msg.get("color", "#10b981")
            self.peer_joined.emit(name, color)

        elif msg_type == CollabMsgType.PEER_LEFT:
            name = msg.get("name", "Peer")
            self.peer_left.emit(name)
