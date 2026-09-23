import uuid
from typing import List, Optional
from PyQt6.QtCore import QPointF
from shared.contracts.ink import InkStroke, InkPoint
from shared.contracts.common import CanvasBBox, CoordinateSpace

class InkAdapter:
    """Adapts Qt Canvas UI items to strict Pydantic Contracts."""
    
    @staticmethod
    def extract_ink_stroke(qt_item, board_id: str) -> Optional[InkStroke]:
        """Converts an app.ui.items.ink_stroke.InkStroke to a shared.contracts.ink.InkStroke.
        Properly resolves scene coordinates and preserves raw timestamps if available.
        """
        # Ensure it has the data we need
        if not hasattr(qt_item, "path") or not hasattr(qt_item, "to_dict"):
            return None
            
        item_id = getattr(qt_item, "item_id", None)
        if not item_id:
            # Fallback for unstored items
            item_id = str(uuid.uuid4())
            qt_item.item_id = item_id
            
        # Get scene bounding rect for the bbox
        scene_rect = qt_item.sceneBoundingRect()
        bbox = CanvasBBox(
            x=scene_rect.x(),
            y=scene_rect.y(),
            width=scene_rect.width(),
            height=scene_rect.height(),
            coordinate_space=CoordinateSpace.SCENE
        )
        
        points: List[InkPoint] = []
        
        # Priority 1: Raw points (has pressure and timestamp)
        if hasattr(qt_item, "raw_stroke") and qt_item.raw_stroke:
            for pt in qt_item.raw_stroke:
                if len(pt) >= 4:
                    x, y, p, t = pt[0], pt[1], pt[2], pt[3]
                elif len(pt) == 3:
                    x, y, p = pt[0], pt[1], pt[2]
                    t = None
                else:
                    x, y = pt[0], pt[1]
                    p, t = 1.0, None
                    
                # Map from local to scene coordinates since items can be moved
                scene_pt = qt_item.mapToScene(QPointF(x, y))
                
                # QTabletEvent timestamp is usually ms. time.time() is seconds.
                # In StrokeProcessor, time.time() is used by default. Let's convert to ms if it's small.
                # Actually, our new requirement is timestamp_ms.
                timestamp_ms = None
                if t is not None:
                    # If it's epoch seconds (e.g., 1700000000.123), convert to int ms
                    if t < 100000000000: 
                        timestamp_ms = int(t * 1000)
                    else:
                        timestamp_ms = int(t)

                points.append(InkPoint(
                    x=scene_pt.x(),
                    y=scene_pt.y(),
                    pressure=max(0.0, min(1.0, float(p))),
                    timestamp_ms=timestamp_ms
                ))
        
        # Priority 2: Fallback to Qt path elements
        else:
            path = qt_item.path()
            for i in range(path.elementCount()):
                el = path.elementAt(i)
                # Map local to scene
                scene_pt = qt_item.mapToScene(QPointF(el.x, el.y))
                points.append(InkPoint(
                    x=scene_pt.x(),
                    y=scene_pt.y(),
                    pressure=1.0,
                    timestamp_ms=None
                ))

        if not points:
            return None
            
        tool_mode = getattr(qt_item, "tool_mode", "pen")
        color = qt_item.stroke_color.name() if hasattr(qt_item, "stroke_color") else "#1c1c1e"
        width = getattr(qt_item, "stroke_width", 3.0)

        return InkStroke(
            id=item_id,
            board_id=board_id,
            points=points,
            tool_type=tool_mode,
            color=color,
            width=width,
            bbox=bbox
        )
