"""
Collaboration Protocol for Kestrel
Defines message schemas, Room Code encoding/decoding, and local network address discovery.
"""

import socket
import base64
import json
import uuid
import time
from typing import Dict, Any, List, Optional, Tuple


# Protocol version
COLLAB_PROTOCOL_VERSION = "1.0"

# Standard default port
DEFAULT_COLLAB_PORT = 8765

# Message Types
class CollabMsgType:
    JOIN = "join"
    WELCOME = "welcome"
    SYNC_REQUEST = "sync_request"
    SYNC_RESPONSE = "sync_response"
    ITEM_ADD = "item_add"
    ITEM_UPDATE = "item_update"
    ITEM_DELETE = "item_delete"
    CURSOR_MOVE = "cursor_move"
    CANVAS_CLEAR = "canvas_clear"
    BG_CHANGE = "bg_change"
    PEER_JOINED = "peer_joined"
    PEER_LEFT = "peer_left"
    PING = "ping"
    PONG = "pong"


def get_local_ip_addresses() -> List[Tuple[str, str]]:
    """
    Discovers available IPv4 addresses on this machine (LAN, Wi-Fi, Tailscale/VPN, Loopback).
    Returns list of (ip_address, description) tuples.
    """
    addresses = []
    seen = set()

    # 1. Primary outbound LAN route
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        # Doesn't actually make a connection, just queries routing table
        s.connect(("8.8.8.8", 80))
        primary_ip = s.getsockname()[0]
        s.close()
        if primary_ip and primary_ip not in seen:
            desc = "Local Network (Wi-Fi / LAN)"
            if primary_ip.startswith("100."):
                desc = "Tailscale / VPN"
            addresses.append((primary_ip, desc))
            seen.add(primary_ip)
    except Exception:
        pass

    # 2. Hostname resolution
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if ip not in seen and not ip.startswith("127."):
                desc = "Secondary Interface"
                if ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
                    desc = "Local Network"
                elif ip.startswith("100."):
                    desc = "Tailscale / VPN"
                addresses.append((ip, desc))
                seen.add(ip)
    except Exception:
        pass

    # 3. Always provide loopback as fallback
    if "127.0.0.1" not in seen:
        addresses.append(("127.0.0.1", "This Computer (Localhost)"))

    return addresses


def encode_room_code(host: str, port: int, room_id: str = "") -> str:
    """
    Generates a compact, human-friendly Room Code from host and port.
    Format:
    If host is an IPv4 address (e.g. 192.168.1.15) and port is 8765:
    We encode the IP into hex + port: KEST-C0A8010F-223D
    This is extremely easy to copy and share!
    """
    try:
        parts = [int(p) for p in host.split(".")]
        if len(parts) == 4 and all(0 <= p <= 255 for p in parts):
            hex_ip = "".join(f"{p:02X}" for p in parts)
            hex_port = f"{port:04X}"
            return f"KEST-{hex_ip}-{hex_port}"
    except Exception:
        pass

    # Fallback to base64 encoding for hostnames, domains, or arbitrary hosts
    raw = f"{host}:{port}"
    b64 = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")
    return f"KEST-{b64}"


def decode_room_code(code_or_url: str) -> Optional[Tuple[str, int]]:
    """
    Parses any of the following formats into (host, port):
    1. Compact Room Code: "KEST-C0A8010F-223D" or "KEST-<base64>"
    2. Direct address: "192.168.1.15:8765" or "100.127.255.152:8765"
    3. Host without port: "192.168.1.15" (defaults to DEFAULT_COLLAB_PORT)
    4. Link format: "kestrel://collab/192.168.1.15:8765" or "ws://192.168.1.15:8765"
    5. Tunnel URL: "0.tcp.ngrok.io:12345" or "collab.example.com:8765"
    """
    if not code_or_url:
        return None
    
    clean = code_or_url.strip()

    # Strip custom protocols if present
    for proto in ["kestrel://collab/", "kestrel://", "ws://", "wss://", "http://", "https://"]:
        if clean.lower().startswith(proto):
            clean = clean[len(proto):].strip("/")
            break

    # Strip URL query parameters if present (e.g. ?code=...)
    if "?" in clean:
        clean = clean.split("?")[0]

    # Check for KEST- prefix
    if clean.upper().startswith("KEST-"):
        payload = clean[5:]
        # Format 1: KEST-HEXIP-HEXPORT
        if "-" in payload:
            parts = payload.split("-")
            if len(parts) == 2 and len(parts[0]) == 8:
                try:
                    hex_ip, hex_port = parts[0], parts[1]
                    ip = ".".join(str(int(hex_ip[i:i+2], 16)) for i in (0, 2, 4, 6))
                    port = int(hex_port, 16)
                    return ip, port
                except Exception:
                    pass
        # Format 2: Base64 payload
        try:
            padded = payload + "=" * (-len(payload) % 4)
            decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
            if ":" in decoded:
                h, p = decoded.rsplit(":", 1)
                return h, int(p)
        except Exception:
            pass

    # Direct host:port
    if ":" in clean:
        parts = clean.rsplit(":", 1)
        try:
            return parts[0], int(parts[1])
        except ValueError:
            return None

    # Host only without port
    if clean:
        return clean, DEFAULT_COLLAB_PORT

    return None


def generate_share_link(host: str, port: int, room_code: str = "") -> str:
    """Generates a shareable URL string."""
    code = room_code or encode_room_code(host, port)
    return f"kestrel://collab/{host}:{port}?code={code}"


def make_collab_message(msg_type: str, client_id: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Helper to structure outgoing collaboration protocol packets."""
    payload = {
        "version": COLLAB_PROTOCOL_VERSION,
        "type": msg_type,
        "client_id": client_id,
        "timestamp": time.time(),
    }
    if data:
        payload.update(data)
    return payload
