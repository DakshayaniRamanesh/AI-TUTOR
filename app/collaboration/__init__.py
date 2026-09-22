"""
Collaboration module for Kestrel.
"""

from .collab_protocol import (
    CollabMsgType, get_local_ip_addresses, encode_room_code,
    decode_room_code, generate_share_link, DEFAULT_COLLAB_PORT
)
from .collab_server import CollabServer
from .collab_client import CollabClient
from .collab_session_manager import CollabSessionManager, CollabRole

__all__ = [
    "CollabMsgType",
    "get_local_ip_addresses",
    "encode_room_code",
    "decode_room_code",
    "generate_share_link",
    "DEFAULT_COLLAB_PORT",
    "CollabServer",
    "CollabClient",
    "CollabSessionManager",
    "CollabRole",
]
