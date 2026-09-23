"""Desktop-side helpers for serializing a lasso selection for video generation."""

from __future__ import annotations

import base64
import uuid
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from PyQt6.QtCore import QBuffer, QIODevice, QRectF
from PyQt6.QtGui import QPainter, QPixmap


_MAX_SELECTED_ITEMS = 80
_MAX_NEARBY_ITEMS = 30
_MAX_PATH_ELEMENTS = 1200


def build_board_selection_payload(
    scene,
    selected_items: Sequence,
    lasso_points: Sequence[Tuple[float, float]] | None = None,
    user_instruction: str = "Explain the selected whiteboard region.",
    board_id: str = "",
    nearby_margin: float = 180.0,
) -> Dict[str, Any]:
    """Serialize native canvas objects and a supplementary PNG crop."""
    selected = [item for item in selected_items if item is not None and item.scene() == scene][:_MAX_SELECTED_ITEMS]
    if not selected:
        return {
            "board_id": board_id,
            "bbox": {},
            "lasso_polygon": list(lasso_points or []),
            "selected_items": [],
            "nearby_items": [],
            "image_b64": "",
            "user_instruction": user_instruction,
        }

    rect = selected[0].sceneBoundingRect()
    for item in selected[1:]:
        rect = rect.united(item.sceneBoundingRect())
    rect = rect.adjusted(-24, -24, 24, 24)

    selected_payload = [_serialize_item(item) for item in selected]
    selected_set = set(selected)

    halo = rect.adjusted(-nearby_margin, -nearby_margin, nearby_margin, nearby_margin)
    nearby_payload: List[Dict[str, Any]] = []
    for item in scene.items(halo):
        if item in selected_set or len(nearby_payload) >= _MAX_NEARBY_ITEMS:
            continue
        if not hasattr(item, "to_dict"):
            continue
        try:
            nearby_payload.append(_serialize_item(item))
        except Exception:
            continue

    return {
        "board_id": board_id,
        "board_revision": None,
        "bbox": {
            "x": float(rect.x()),
            "y": float(rect.y()),
            "width": float(rect.width()),
            "height": float(rect.height()),
        },
        "lasso_polygon": [[float(x), float(y)] for x, y in (lasso_points or [])],
        "selected_items": selected_payload,
        "nearby_items": nearby_payload,
        "image_b64": _render_region_base64(scene, rect),
        "user_instruction": user_instruction,
    }


def infer_prompt_from_selection(payload: Dict[str, Any]) -> str:
    """Use native text fields when available; otherwise keep a generic selection prompt."""
    text_parts: List[str] = []
    for item in payload.get("selected_items", []):
        _collect_text(item, text_parts)
        if sum(len(t) for t in text_parts) > 500:
            break
    if text_parts:
        snippet = " | ".join(dict.fromkeys(text_parts))[:500]
        return f"Explain this selected whiteboard content clearly: {snippet}"
    return payload.get("user_instruction") or "Explain the selected whiteboard region."


def _serialize_item(item) -> Dict[str, Any]:
    data = item.to_dict() if hasattr(item, "to_dict") else {"type": type(item).__name__}
    if not isinstance(data, dict):
        data = {"type": type(item).__name__, "value": str(data)}

    item_id = getattr(item, "item_id", None)
    if not item_id:
        item_id = uuid.uuid4().hex
        try:
            item.item_id = item_id
        except Exception:
            pass
    data = dict(data)
    data["item_id"] = str(item_id)

    br = item.sceneBoundingRect()
    data["scene_bbox"] = {
        "x": float(br.x()),
        "y": float(br.y()),
        "width": float(br.width()),
        "height": float(br.height()),
    }

    elements = data.get("elements")
    if isinstance(elements, list) and len(elements) > _MAX_PATH_ELEMENTS:
        # Evenly sample long paths instead of sending tens of thousands of points.
        step = max(1, len(elements) // _MAX_PATH_ELEMENTS)
        data["elements"] = elements[::step][:_MAX_PATH_ELEMENTS]
        data["elements_truncated"] = True
    return data


def _render_region_base64(scene, rect: QRectF) -> str:
    width = max(64, min(1800, int(rect.width())))
    height = max(64, min(1800, int(rect.height())))
    scale = min(1.0, 1800.0 / max(rect.width(), rect.height(), 1.0))
    width = max(64, int(rect.width() * scale))
    height = max(64, int(rect.height() * scale))

    pixmap = QPixmap(width, height)
    pixmap.fill()
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    scene.render(painter, target=QRectF(pixmap.rect()), source=rect)
    painter.end()

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    return base64.b64encode(bytes(buffer.data())).decode("ascii")


def _collect_text(value: Any, out: List[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"text", "title", "question", "raw_text", "caption", "label", "description"} and isinstance(child, str) and child.strip():
                out.append(child.strip())
            elif isinstance(child, (dict, list, tuple)):
                _collect_text(child, out)
    elif isinstance(value, (list, tuple)):
        for child in value[:20]:
            _collect_text(child, out)
