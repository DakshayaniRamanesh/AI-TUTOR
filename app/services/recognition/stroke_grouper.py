import uuid
from typing import List, Optional, Dict
from pydantic import BaseModel
from shared.contracts.ink import InkGroup
from shared.contracts.common import CanvasBBox, CoordinateSpace

class StrokeGroupingConfig(BaseModel):
    max_temporal_gap_ms: int = 1200
    max_horizontal_gap_px: float = 80.0
    vertical_baseline_tolerance_px: float = 40.0

class StrokeData:
    def __init__(self, stroke_id: str, x: float, y: float, w: float, h: float, start_ts: float, end_ts: float):
        self.stroke_id = stroke_id
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.start_ts = start_ts
        self.end_ts = end_ts

class StrokeGrouper:
    """Stateful service that tracks the currently active ink group and manages revisions."""
    def __init__(self, config: Optional[StrokeGroupingConfig] = None):
        self.config = config or StrokeGroupingConfig()
        self.active_group_id: Optional[str] = None
        self.groups: Dict[str, InkGroup] = {}
        self._group_strokes: Dict[str, List[StrokeData]] = {}
        self._last_stroke_end_ts_ms: float = 0.0

    def add_stroke(self, stroke: StrokeData, board_id: str) -> InkGroup:
        """Adds a single completed stroke to the appropriate group."""
        curr_start = stroke.start_ts
        curr_end = stroke.end_ts
        
        should_start_new = True

        if self.active_group_id and self.active_group_id in self.groups:
            active_group = self.groups[self.active_group_id]
            
            gap = curr_start - self._last_stroke_end_ts_ms
            if gap <= self.config.max_temporal_gap_ms:
                # Check spatial overlap/proximity
                v_gap = abs(stroke.y - active_group.bbox.y)
                if v_gap <= self.config.vertical_baseline_tolerance_px * 2:
                    should_start_new = False
                    
        if should_start_new:
            self.active_group_id = str(uuid.uuid4())
            self.groups[self.active_group_id] = InkGroup(
                id=self.active_group_id,
                board_id=board_id,
                revision=0,
                stroke_ids=[stroke.stroke_id],
                bbox=CanvasBBox(x=stroke.x, y=stroke.y, width=stroke.w, height=stroke.h)
            )
            self._group_strokes[self.active_group_id] = [stroke]
            group = self.groups[self.active_group_id]
        else:
            # Add stroke to active group
            group = self.groups[self.active_group_id]
            strokes = self._group_strokes[self.active_group_id]
            strokes.append(stroke)
            
            group.stroke_ids.append(stroke.stroke_id)
            group.revision += 1
            
            # Update bounding box
            min_x = min(s.x for s in strokes)
            min_y = min(s.y for s in strokes)
            max_r = max(s.x + s.w for s in strokes)
            max_b = max(s.y + s.h for s in strokes)
            
            group.bbox.x = min_x
            group.bbox.y = min_y
            group.bbox.width = max_r - min_x
            group.bbox.height = max_b - min_y
        
        self._last_stroke_end_ts_ms = curr_end
        
        return group

    def create_explicit_group(self, strokes: List[StrokeData], board_id: str) -> InkGroup:
        """Create a group explicitly when a user selects a region."""
        if not strokes:
            raise ValueError("Cannot create an explicit group with zero strokes.")
            
        group_id = str(uuid.uuid4())
        
        min_x = min(s.x for s in strokes)
        min_y = min(s.y for s in strokes)
        max_r = max(s.x + s.w for s in strokes)
        max_b = max(s.y + s.h for s in strokes)
        
        group = InkGroup(
            id=group_id,
            board_id=board_id,
            revision=1,
            stroke_ids=[s.stroke_id for s in strokes],
            bbox=CanvasBBox(
                x=min_x,
                y=min_y,
                width=max_r - min_x,
                height=max_b - min_y,
                coordinate_space=CoordinateSpace.SCENE
            )
        )
        
        self.groups[group_id] = group
        self._group_strokes[group_id] = strokes
        self.active_group_id = group_id
        
        self._last_stroke_end_ts_ms = strokes[-1].end_ts
            
        return group
