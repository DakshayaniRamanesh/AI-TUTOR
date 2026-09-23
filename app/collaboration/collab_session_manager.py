"""
Kestrel Collaboration Session Manager
Central coordinator managing local hosting, joining remote sessions,
dispatching canvas events, and tracking session state.
"""

from typing import Optional, Dict, Any, List, Tuple
from PyQt6.QtCore import QObject, pyqtSignal

from .collab_protocol import (
    decode_room_code, encode_room_code, generate_share_link,
    DEFAULT_COLLAB_PORT, get_local_ip_addresses
)
from .collab_server import CollabServer
from .collab_client import CollabClient


class CollabRole:
    IDLE = "idle"
    HOST = "host"
    GUEST = "guest"


class CollabSessionManager(QObject):
    """
    Singleton-style manager bridging the Qt Canvas and Networking layers.
    """
    # High-level session signals for MainWindow and Dialogs
    session_state_changed = pyqtSignal(str, str, str) # (role, room_code, share_link)
    peer_count_changed = pyqtSignal(int)
    peer_notification = pyqtSignal(str, str)          # (type: "joined"|"left", message)
    connection_error = pyqtSignal(str)

    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = CollabSessionManager()
        return cls._instance

    def __init__(self, parent=None):
        super().__init__(parent)
        self.role = CollabRole.IDLE
        self.room_code = ""
        self.share_link = ""
        self.user_name = "User"
        self.user_color = "#3b82f6"
        self.active_host = ""
        self.active_port = DEFAULT_COLLAB_PORT

        self._server: Optional[CollabServer] = None
        self._client: Optional[CollabClient] = None
        self._scene = None
        self._peers: Dict[str, Dict[str, Any]] = {}

    @property
    def is_in_session(self) -> bool:
        return self.role != CollabRole.IDLE

    def bind_canvas_scene(self, scene):
        """Attaches the active CanvasScene to the collaboration manager."""
        self._scene = scene

        # Connect scene signals to outbound network dispatcher
        if hasattr(scene, "item_collaborated_add"):
            scene.item_collaborated_add.connect(self._on_scene_item_add)
        if hasattr(scene, "item_collaborated_update"):
            scene.item_collaborated_update.connect(self._on_scene_item_update)
        if hasattr(scene, "item_collaborated_delete"):
            scene.item_collaborated_delete.connect(self._on_scene_item_delete)
        if hasattr(scene, "cursor_collaborated_move"):
            scene.cursor_collaborated_move.connect(self._on_scene_cursor_move)
        if hasattr(scene, "canvas_collaborated_clear"):
            scene.canvas_collaborated_clear.connect(self._on_scene_clear)
        if hasattr(scene, "bg_collaborated_changed"):
            scene.bg_collaborated_changed.connect(self._on_scene_bg_change)

    # ── Host Flow ─────────────────────────────────────────────────────────────

    def start_hosting(self, display_ip: str = None, port: int = DEFAULT_COLLAB_PORT, user_name: str = "Host") -> tuple[bool, str]:
        """Starts hosting a local collaboration session."""
        if self.is_in_session:
            self.leave_session()

        self.user_name = user_name or "Host"

        # Discover display IP if not provided
        if not display_ip:
            ips = get_local_ip_addresses()
            display_ip = ips[0][0] if ips else "127.0.0.1"

        self.active_host = display_ip
        self.active_port = port

        try:
            self._server = CollabServer(
                host="0.0.0.0",
                port=port,
                host_display_ip=display_ip,
                parent=self
            )
            # Provide current canvas state when peers connect
            self._server.canvas_sync_provider = self._get_current_canvas_dict

            self._server.server_started.connect(self._on_server_started)
            self._server.peer_connected.connect(self._on_server_peer_connected)
            self._server.peer_disconnected.connect(self._on_server_peer_disconnected)
            self._server.error_occurred.connect(self._on_network_error)
            self._server.start()

            return True, ""
        except Exception as err:
            return False, str(err)

    def _on_server_started(self, host: str, port: int, room_code: str):
        self.active_port = port
        self.room_code = room_code
        self.share_link = generate_share_link(host, port, room_code)
        self.role = CollabRole.HOST

        # Connect internal client as the Host participant
        self._client = CollabClient(user_name=self.user_name, parent=self)
        self._wire_client_signals(self._client)
        # Connect to localhost
        self._client.connect_to_host("127.0.0.1", port)

        self.session_state_changed.emit(self.role, self.room_code, self.share_link)
        self.peer_count_changed.emit(1)

    # ── Join Flow ─────────────────────────────────────────────────────────────

    def join_session(self, code_or_url: str, user_name: str = "Guest") -> tuple[bool, str]:
        """Joins an existing collaboration session using a code or link."""
        if self.is_in_session:
            self.leave_session()

        self.user_name = user_name or "Guest"

        target = decode_room_code(code_or_url)
        if not target:
            return False, "Invalid room code or address. Please check and try again."

        host, port = target
        self.active_host = host
        self.active_port = port
        self.room_code = encode_room_code(host, port)
        self.share_link = generate_share_link(host, port, self.room_code)
        self.role = CollabRole.GUEST

        try:
            self._client = CollabClient(user_name=self.user_name, parent=self)
            self._wire_client_signals(self._client)
            self._client.connect_to_host(host, port)
            return True, ""
        except Exception as err:
            self.role = CollabRole.IDLE
            return False, str(err)

    # ── Leave / Teardown Flow ──────────────────────────────────────────────────

    def leave_session(self):
        """Ends or disconnects from the current session."""
        if self._client:
            try:
                self._client.disconnect()
            except Exception:
                pass
            self._client = None

        if self._server:
            try:
                self._server.stop()
            except Exception:
                pass
            self._server = None

        self.role = CollabRole.IDLE
        self.room_code = ""
        self.share_link = ""
        self._peers.clear()

        # Clean up remote cursors on scene
        if self._scene and hasattr(self._scene, "clear_remote_cursors"):
            self._scene.clear_remote_cursors()

        self.session_state_changed.emit(CollabRole.IDLE, "", "")
        self.peer_count_changed.emit(0)

    # ── Internal Event Wiring ─────────────────────────────────────────────────

    def _wire_client_signals(self, client: CollabClient):
        client.connected.connect(self._on_client_connected)
        client.disconnected.connect(self._on_client_disconnected)
        client.connection_failed.connect(self._on_client_failed)

        client.sync_received.connect(self._on_remote_sync_received)
        client.item_added.connect(self._on_remote_item_added)
        client.item_updated.connect(self._on_remote_item_updated)
        client.item_deleted.connect(self._on_remote_item_deleted)
        client.cursor_moved.connect(self._on_remote_cursor_moved)
        client.canvas_cleared.connect(self._on_remote_canvas_cleared)
        client.bg_changed.connect(self._on_remote_bg_changed)

        client.peer_joined.connect(self._on_client_peer_joined)
        client.peer_left.connect(self._on_client_peer_left)

    def _on_client_connected(self, room_code: str, client_id: str, color: str):
        if room_code:
            self.room_code = room_code
            self.share_link = generate_share_link(self.active_host, self.active_port, self.room_code)
        self.user_color = color
        self.session_state_changed.emit(self.role, self.room_code, self.share_link)

    def _on_client_disconnected(self, reason: str):
        if self.role == CollabRole.GUEST:
            self.leave_session()

    def _on_client_failed(self, error_msg: str):
        self.connection_error.emit(error_msg)
        if self.role == CollabRole.GUEST:
            self.leave_session()

    def _on_server_peer_connected(self, client_id: str, name: str, color: str):
        self._peers[client_id] = {"name": name, "color": color}
        count = len(self._peers) + (1 if self.role == CollabRole.HOST else 0)
        self.peer_count_changed.emit(count)
        self.peer_notification.emit("joined", f"{name} joined the canvas")

    def _on_server_peer_disconnected(self, client_id: str, name: str):
        self._peers.pop(client_id, None)
        count = len(self._peers) + (1 if self.role == CollabRole.HOST else 0)
        self.peer_count_changed.emit(count)
        self.peer_notification.emit("left", f"{name} left the canvas")
        if self._scene and hasattr(self._scene, "remove_remote_cursor"):
            self._scene.remove_remote_cursor(client_id)

    def _on_client_peer_joined(self, name: str, color: str):
        self.peer_notification.emit("joined", f"{name} joined the canvas")

    def _on_client_peer_left(self, name: str):
        self.peer_notification.emit("left", f"{name} left the canvas")

    def _on_network_error(self, err: str):
        self.connection_error.emit(err)

    # ── Scene <-> Network Dispatch ────────────────────────────────────────────

    def _get_current_canvas_dict(self) -> Dict[str, Any]:
        """Serializes current canvas state for full sync."""
        if not self._scene:
            return {"items": [], "background_mode": "blank"}
        return {
            "items": self._scene.to_dict_list(),
            "background_mode": getattr(self._scene, "background_mode", "blank")
        }

    # Outbound from local CanvasScene -> Network
    def _on_scene_item_add(self, item_dict: dict):
        if self._client and self._client.is_connected:
            self._client.send_item_add(item_dict)

    def _on_scene_item_update(self, item_dict: dict):
        if self._client and self._client.is_connected:
            self._client.send_item_update(item_dict)

    def _on_scene_item_delete(self, item_ids: list):
        if self._client and self._client.is_connected:
            self._client.send_item_delete(item_ids)

    def _on_scene_cursor_move(self, x: float, y: float):
        if self._client and self._client.is_connected:
            self._client.send_cursor_move(x, y)

    def _on_scene_clear(self):
        if self._client and self._client.is_connected:
            self._client.send_canvas_clear()

    def _on_scene_bg_change(self, mode: str):
        if self._client and self._client.is_connected:
            self._client.send_bg_change(mode)

    # Inbound from Network -> CanvasScene
    def _on_remote_sync_received(self, board_data: dict):
        if self._scene and hasattr(self._scene, "apply_remote_sync"):
            self._scene.apply_remote_sync(board_data)

    def _on_remote_item_added(self, item_dict: dict):
        if self._scene and hasattr(self._scene, "apply_remote_item_add"):
            self._scene.apply_remote_item_add(item_dict)

    def _on_remote_item_updated(self, item_dict: dict):
        if self._scene and hasattr(self._scene, "apply_remote_item_update"):
            self._scene.apply_remote_item_update(item_dict)

    def _on_remote_item_deleted(self, item_ids: list):
        if self._scene and hasattr(self._scene, "apply_remote_item_delete"):
            self._scene.apply_remote_item_delete(item_ids)

    def _on_remote_cursor_moved(self, client_id: str, name: str, color: str, x: float, y: float):
        if self._scene and hasattr(self._scene, "apply_remote_cursor"):
            self._scene.apply_remote_cursor(client_id, name, color, x, y)

    def _on_remote_canvas_cleared(self):
        if self._scene and hasattr(self._scene, "apply_remote_clear"):
            self._scene.apply_remote_clear()

    def _on_remote_bg_changed(self, mode: str):
        if self._scene and hasattr(self._scene, "apply_remote_bg"):
            self._scene.apply_remote_bg(mode)
