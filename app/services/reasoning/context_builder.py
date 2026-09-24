import re
from typing import Optional, List, Dict, Any
from shared.contracts.context import (
    ContextRequest, ContextBundle, RetrievedEvidence, GraphContext, 
    GraphConceptDTO, LearnerObservationDTO, CanvasContext, SemanticBlock
)
from shared.contracts.reasoning import CanvasAnchor
from shared.contracts.common import CanvasBBox
from app.services.memory.repositories import MemoryRepository
from backend.workspace.subject_search_service import SubjectSearchService
from app.services.knowledge.graph_query_service import GraphQueryService

MAX_SNIPPET_BUDGET_CHARS = 1600

class ContextBuilder:
    """
    Authoritative Unified ContextBuilder for Kestrel.
    Synthesizes Canvas Workspace, Episodic Memory, Learner Observations,
    Subject Knowledge Retrieval, and Evidence-backed Knowledge Graph.
    """

    def __init__(
        self, 
        repository: MemoryRepository,
        search_service: Optional[SubjectSearchService] = None,
        graph_service: Optional[GraphQueryService] = None
    ):
        self.repo = repository
        self.search_service = search_service or SubjectSearchService()
        self.graph_service = graph_service or GraphQueryService()

    def build_context(self, request: ContextRequest) -> ContextBundle:
        """
        Builds a unified ContextBundle from a typed ContextRequest.
        """
        diagnostic_reasons = []

        # 1. Resolve Current Work & Canvas Anchor
        current_work_text = request.user_query
        canvas_anchor = None

        if request.canvas_context:
            cc: CanvasContext = request.canvas_context
            # If an active block or selected block has recognized text, prioritize it for math/student work
            target_block: Optional[SemanticBlock] = None
            if cc.active_block_id:
                for b in cc.semantic_blocks:
                    if b.block_id == cc.active_block_id:
                        target_block = b
                        break

            if not target_block and cc.selected_item_ids:
                for b in cc.semantic_blocks:
                    if any(iid in cc.selected_item_ids for iid in b.item_ids):
                        target_block = b
                        break

            if not target_block and cc.semantic_blocks:
                target_block = cc.semantic_blocks[-1]

            if target_block:
                if not current_work_text and target_block.recognized_text:
                    current_work_text = target_block.recognized_text
                    diagnostic_reasons.append(f"Derived current work from semantic block '{target_block.block_id}'")

                item_ids = target_block.item_ids or target_block.stroke_ids or [target_block.block_id]
                canvas_anchor = CanvasAnchor(
                    item_ids=item_ids,
                    board_id=cc.board_id,
                    board_revision=str(cc.canvas_revision) if cc.canvas_revision else None,
                    bbox_snapshot=target_block.bbox
                )

        # 2. Episodic Memory (Recent Reasoning Steps)
        recent_reasoning_lines = []
        if request.attempt_id:
            steps = self.repo.get_recent_steps(request.attempt_id, limit=5)
            if steps:
                recent_reasoning_lines.append(f"--- Recent Reasoning History (Attempt {request.attempt_id}) ---")
                for i, s in enumerate(steps, 1):
                    v = s.validation_verdict or "UNVALIDATED"
                    recent_reasoning_lines.append(f"Step {i}: {s.recognized_text} [{v}]")
                diagnostic_reasons.append(f"Included {len(steps)} recent reasoning steps from attempt '{request.attempt_id}'")
            else:
                diagnostic_reasons.append(f"No previous steps in attempt '{request.attempt_id}'")
        else:
            diagnostic_reasons.append("No attempt_id provided; episodic memory skipped")

        recent_reasoning_text = "\n".join(recent_reasoning_lines)

        # 3. Learner Observations (Layer 4 Memory)
        learner_obs_dtos: List[LearnerObservationDTO] = []
        # If user_id can be resolved or default user
        user_id = getattr(request, "user_id", None) or "default_user"
        try:
            obs_list = self.repo.get_learner_observations(
                user_id=user_id, 
                subject_id=request.subject_id, 
                status="ACTIVE"
            )
            for o in obs_list:
                learner_obs_dtos.append(LearnerObservationDTO(
                    observation_type=o.observation_type,
                    description=o.description,
                    occurrence_count=o.occurrence_count,
                    status=o.status,
                    confidence=o.confidence
                ))
            if learner_obs_dtos:
                diagnostic_reasons.append(f"Found {len(learner_obs_dtos)} active learner observations")
        except Exception as e:
            diagnostic_reasons.append(f"Learner observation query warning: {e}")

        # 4. Canonical Subject Retrieval (Materials + Chunks + Hybrid Search)
        retrieved_evidence: List[RetrievedEvidence] = []
        search_query = request.user_query or current_work_text or ""
        
        if request.subject_id and search_query.strip():
            raw_hits = self.search_service.search(
                subject_id=request.subject_id,
                query_text=search_query,
                top_k=4
            )
            total_chars = 0
            for h in raw_hits:
                text_snippet = h.get("text", "").strip()
                if not text_snippet:
                    continue
                # Character budget control
                if total_chars + len(text_snippet) > MAX_SNIPPET_BUDGET_CHARS:
                    truncated_len = max(0, MAX_SNIPPET_BUDGET_CHARS - total_chars)
                    if truncated_len < 100:
                        break
                    text_snippet = text_snippet[:truncated_len] + "..."

                total_chars += len(text_snippet)
                retrieved_evidence.append(RetrievedEvidence(
                    chunk_id=str(h.get("id") or h.get("chunk_id")),
                    material_id=h.get("material_id"),
                    document_title=h.get("document_title"),
                    chapter=h.get("chapter"),
                    section=h.get("section"),
                    page_number=h.get("page_number"),
                    snippet=text_snippet,
                    score=float(h.get("score", 1.0)),
                    source=str(h.get("source", "lexical"))
                ))
            if retrieved_evidence:
                diagnostic_reasons.append(f"Retrieved {len(retrieved_evidence)} chunks from subject '{request.subject_id}'")
            else:
                diagnostic_reasons.append(f"Subject '{request.subject_id}' searched; no relevant chunks matched")
        elif not request.subject_id:
            diagnostic_reasons.append("No subject_id provided; subject material search skipped")

        # 5. Evidence-Backed 1-Hop Knowledge Graph Expansion
        graph_context: Optional[GraphContext] = None
        if request.subject_id and (current_work_text or search_query):
            # Extract candidate concept terms from math/prose tokens
            combined_text = f"{current_work_text or ''} {search_query}".lower()
            tokens = re.findall(r'[a-zA-Z]{3,}', combined_text)
            candidate_terms = list(set(tokens))[:6]

            if candidate_terms:
                raw_graph = self.graph_service.get_one_hop_context(
                    subject_id=request.subject_id,
                    concept_terms=candidate_terms
                )
                focal = raw_graph.get("focal_concepts", [])
                neighbors = []
                for n in raw_graph.get("neighbor_concepts", []):
                    neighbors.append(GraphConceptDTO(
                        concept_key=n["concept_key"],
                        display_name=n["display_name"],
                        relation=n["relation"],
                        evidence_count=n.get("evidence_count", 0)
                    ))
                if focal or neighbors:
                    graph_context = GraphContext(
                        focal_concepts=focal,
                        neighbor_concepts=neighbors
                    )
                    diagnostic_reasons.append(f"Expanded graph: {len(focal)} focal concepts, {len(neighbors)} 1-hop neighbors")

        return ContextBundle(
            request_id=request.request_id,
            subject_id=request.subject_id,
            notebook_id=request.notebook_id,
            session_id=request.session_id,
            attempt_id=request.attempt_id,
            current_work_text=current_work_text,
            canvas_anchor=canvas_anchor,
            recent_reasoning_text=recent_reasoning_text,
            retrieved_evidence=retrieved_evidence,
            graph_context=graph_context,
            learner_observations=learner_obs_dtos,
            diagnostic_reasons=diagnostic_reasons
        )
