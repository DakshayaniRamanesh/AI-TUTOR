from typing import List, Optional
from pydantic import BaseModel
import uuid
from shared.contracts.ink import InkStroke, InkGroup
from shared.contracts.common import CanvasBBox, CoordinateSpace

class StrokeGroupingConfig(BaseModel):
    max_temporal_gap_ms: int = 1500  # E.g., pause between writing "2x" and "=" 
    max_horizontal_gap_px: float = 80.0  # E.g., distance between "2x" and "+".
    vertical_baseline_tolerance_px: float = 40.0 # Straying slightly up/down the baseline.

class StrokeGrouper:
    def __init__(self, config: Optional[StrokeGroupingConfig] = None):
        self.config = config or StrokeGroupingConfig()

    def group_strokes(self, strokes: List[InkStroke], board_id: str) -> List[InkGroup]:
        """Groups ink strokes temporally and spatially according to config."""
        if not strokes:
            return []

        # Check if we can do temporal grouping (all strokes have at least one timestamp)
        # Note: points[0].timestamp_ms might be None for legacy strokes
        can_group_temporally = all(
            (len(s.points) > 0 and s.points[0].timestamp_ms is not None)
            for s in strokes
        )

        groups: List[InkGroup] = []

        if can_group_temporally:
            # Sort by start time
            sorted_strokes = sorted(strokes, key=lambda s: s.points[0].timestamp_ms)
            
            current_group_strokes = [sorted_strokes[0]]
            
            for i in range(1, len(sorted_strokes)):
                curr_stroke = sorted_strokes[i]
                prev_stroke = current_group_strokes[-1]
                
                # Gap between end of prev and start of curr
                prev_end = prev_stroke.points[-1].timestamp_ms
                curr_start = curr_stroke.points[0].timestamp_ms
                
                gap = curr_start - prev_end
                
                if gap <= self.config.max_temporal_gap_ms:
                    # Also check for huge vertical jumps (new line) even if fast
                    v_gap = abs(curr_stroke.bbox.y - prev_stroke.bbox.y)
                    if v_gap > self.config.vertical_baseline_tolerance_px * 2:
                        # Force new group due to line break
                        groups.append(self._create_group(current_group_strokes, board_id))
                        current_group_strokes = [curr_stroke]
                    else:
                        current_group_strokes.append(curr_stroke)
                else:
                    groups.append(self._create_group(current_group_strokes, board_id))
                    current_group_strokes = [curr_stroke]
                    
            if current_group_strokes:
                groups.append(self._create_group(current_group_strokes, board_id))
                
        else:
            # Spatial fallback for legacy strokes
            # Sort by X coordinate
            sorted_strokes = sorted(strokes, key=lambda s: s.bbox.x)
            
            current_group_strokes = [sorted_strokes[0]]
            
            for i in range(1, len(sorted_strokes)):
                curr_stroke = sorted_strokes[i]
                prev_stroke = current_group_strokes[-1]
                
                h_gap = curr_stroke.bbox.x - (prev_stroke.bbox.x + prev_stroke.bbox.width)
                v_gap = abs(curr_stroke.bbox.y - prev_stroke.bbox.y)
                
                # Overlapping or within horizontal gap, AND on same baseline
                if h_gap <= self.config.max_horizontal_gap_px and v_gap <= self.config.vertical_baseline_tolerance_px:
                    current_group_strokes.append(curr_stroke)
                else:
                    groups.append(self._create_group(current_group_strokes, board_id))
                    current_group_strokes = [curr_stroke]
                    
            if current_group_strokes:
                groups.append(self._create_group(current_group_strokes, board_id))
                
        return groups

    def _create_group(self, strokes: List[InkStroke], board_id: str) -> InkGroup:
        # Calculate bounding box encompassing all strokes
        min_x = min(s.bbox.x for s in strokes)
        min_y = min(s.bbox.y for s in strokes)
        max_x = max(s.bbox.x + s.bbox.width for s in strokes)
        max_y = max(s.bbox.y + s.bbox.height for s in strokes)
        
        return InkGroup(
            id=str(uuid.uuid4()),
            board_id=board_id,
            stroke_ids=[s.id for s in strokes],
            bbox=CanvasBBox(
                x=min_x,
                y=min_y,
                width=max_x - min_x,
                height=max_y - min_y,
                coordinate_space=CoordinateSpace.SCENE
            )
        )
