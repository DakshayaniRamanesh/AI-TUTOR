import time
import uuid
from typing import List, Optional, Tuple, Any
from shared.contracts.common import CanvasBBox, CoordinateSpace, StableId
from shared.contracts.context import SemanticBlock, SemanticBlockType, CanvasContext, ContextScope
from app.services.recognition.stroke_grouper import StrokeGrouper, StrokeData

class SemanticCanvasBuilder:
    """
    Constructs coherent semantic blocks from canvas strokes and items.
    Preserves individual stroke IDs while grouping by spatial and temporal proximity.
    """

    def __init__(self, stroke_grouper: Optional[StrokeGrouper] = None):
        self.grouper = stroke_grouper or StrokeGrouper()

    @staticmethod
    def classify_block_type(text: Optional[str]) -> SemanticBlockType:
        """Heuristically classifies block type from recognized text."""
        if not text or not text.strip():
            return SemanticBlockType.UNKNOWN

        t = text.strip()
        has_math_symbols = any(c in t for c in ['=', '+', '-', '*', '/', '^', '\\', '(', ')', '{', '}', '<', '>'])
        has_letters = any(c.isalpha() for c in t)
        word_count = len(t.split())

        # If it has an equal sign and variable/digits -> MATH
        if '=' in t:
            return SemanticBlockType.MATH

        if has_math_symbols and (not has_letters or word_count <= 4):
            return SemanticBlockType.MATH

        if word_count > 4 and not has_math_symbols:
            return SemanticBlockType.TEXT

        if has_math_symbols and has_letters and word_count > 3:
            return SemanticBlockType.MIXED

        return SemanticBlockType.TEXT if has_letters else SemanticBlockType.MATH

    def build_canvas_context(
        self,
        board_id: str,
        canvas_revision: Optional[int],
        strokes: List[Any],
        selected_items: List[Any],
        viewport_rect: Optional[Tuple[float, float, float, float]] = None
    ) -> CanvasContext:
        """
        Builds a full CanvasContext from physical scene items and strokes.
        """
        now_ms = time.time() * 1000.0

        # Convert strokes to StrokeData
        stroke_datas = []
        stroke_item_map = {}
        for s in strokes:
            s_id = getattr(s, "item_id", None) or str(uuid.uuid4())
            if hasattr(s, "item_id") and not s.item_id:
                s.item_id = s_id
            stroke_item_map[s_id] = s

            rect = s.sceneBoundingRect() if hasattr(s, "sceneBoundingRect") else None
            rx = rect.x() if rect else 0.0
            ry = rect.y() if rect else 0.0
            rw = rect.width() if rect else 10.0
            rh = rect.height() if rect else 10.0

            sd = StrokeData(
                stroke_id=s_id,
                x=rx,
                y=ry,
                w=rw,
                h=rh,
                start_ts=now_ms,
                end_ts=now_ms
            )
            stroke_datas.append(sd)

        # Selected stroke IDs & item IDs
        selected_stroke_ids = []
        selected_item_ids = []
        for it in selected_items:
            iid = getattr(it, "item_id", None) or getattr(it, "id", None) or str(uuid.uuid4())
            selected_item_ids.append(iid)
            if iid in stroke_item_map:
                selected_stroke_ids.append(iid)

        # Group strokes
        semantic_blocks: List[SemanticBlock] = []
        active_block_id = None

        if selected_stroke_ids:
            # Explicit selection forms a priority block
            sel_datas = [sd for sd in stroke_datas if sd.stroke_id in selected_stroke_ids]
            if sel_datas:
                group = self.grouper.create_explicit_group(sel_datas, board_id=board_id)
                btype = SemanticBlockType.MATH  # default candidate
                block = SemanticBlock(
                    block_id=group.id,
                    block_type=btype,
                    stroke_ids=group.stroke_ids,
                    item_ids=selected_item_ids,
                    bbox=group.bbox
                )
                semantic_blocks.append(block)
                active_block_id = block.block_id
        else:
            # Automatic spatial & temporal grouping
            for sd in stroke_datas:
                self.grouper.add_stroke(sd)

            for g_id, g in self.grouper.groups.items():
                block = SemanticBlock(
                    block_id=g.id,
                    block_type=SemanticBlockType.MATH,
                    stroke_ids=g.stroke_ids,
                    item_ids=g.stroke_ids,
                    bbox=g.bbox
                )
                semantic_blocks.append(block)

            active_block_id = self.grouper.active_group_id

        # Viewport BBox
        viewport_bbox = None
        if viewport_rect:
            vx, vy, vw, vh = viewport_rect
            viewport_bbox = CanvasBBox(x=vx, y=vy, width=vw, height=vh)

        return CanvasContext(
            board_id=board_id,
            canvas_revision=canvas_revision,
            viewport_bbox=viewport_bbox,
            selected_item_ids=selected_item_ids,
            selected_stroke_ids=selected_stroke_ids,
            semantic_blocks=semantic_blocks,
            active_block_id=active_block_id
        )
