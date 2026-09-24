import datetime
from sqlalchemy.orm import Session
from app.storage.database import get_session_factory, GraphLayout

def save_node_layout(node_id: str, scope_type: str, scope_id: str, x: float, y: float, pinned: bool = False):
    factory = get_session_factory()
    with factory() as session:
        layout = session.query(GraphLayout).filter_by(node_id=node_id, scope_type=scope_type).first()
        if not layout:
            layout = GraphLayout(
                id=f"{scope_type}_{node_id}",
                node_id=node_id,
                scope_type=scope_type,
                scope_id=scope_id
            )
            session.add(layout)
        layout.x = x
        layout.y = y
        layout.pinned = pinned
        layout.updated_at = datetime.datetime.utcnow()
        session.commit()

import threading

def save_node_layout_async(node_id: str, scope_type: str, scope_id: str, x: float, y: float):
    """Async wrapper for saving layout to avoid blocking UI"""
    def _save():
        try:
            save_node_layout(node_id, scope_type, scope_id, x, y, pinned=True)
        except Exception as e:
            print(f"Error saving node layout: {e}")
    threading.Thread(target=_save, daemon=True).start()
