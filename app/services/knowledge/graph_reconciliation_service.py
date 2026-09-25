import json
import uuid
import re
from typing import List, Dict, Optional, Set
from sqlalchemy.orm import Session
from app.storage.database import get_session_factory, ConceptNode, ConceptEdge, GraphEvidence
from shared.contracts.graph_contracts import GraphNodeDTO, GraphEdgeDTO

import unicodedata

def normalize_label(label: str) -> str:
    """Conservatively normalize a label for identity."""
    # Unicode NFKC normalization
    label = unicodedata.normalize('NFKC', label)
    # casefold for better Unicode matching than lower()
    label = label.casefold()
    # Trim leading/trailing whitespace
    label = label.strip()
    # Collapse repeated whitespace
    label = re.sub(r'\s+', ' ', label)
    # Normalize harmless punctuation (remove them, but keep math symbols)
    label = re.sub(r'[\(\)\[\]\{\}\.\,\;\-\_]', '', label)
    return label

def generate_canonical_key(subject_id: str, node_type: str, display_name: str) -> str:
    norm = normalize_label(display_name)
    return f"{subject_id}::{node_type}::{norm}"

class GraphReconciliationService:
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or get_session_factory()

    def reconcile_material_graph(self, subject_id: str, material_id: str, new_nodes: List[GraphNodeDTO], new_edges: List[GraphEdgeDTO]):
        """
        Upsert nodes and edges derived from a specific material.
        Orphan nodes and edges are cleaned up if their last evidence is removed.
        """
        from app.storage.database import SubjectChunk
        with self.session_factory() as session:
            # Pre-fetch valid chunks for this material/subject
            valid_chunks = {
                c.id for c in session.query(SubjectChunk.id).filter(
                    SubjectChunk.subject_id == subject_id,
                    SubjectChunk.material_id == material_id
                ).all()
            }

            # 1. Remove old evidence from this material
            old_evidence = session.query(GraphEvidence).filter(
                GraphEvidence.subject_id == subject_id,
                GraphEvidence.material_id == material_id
            ).all()
            for ev in old_evidence:
                session.delete(ev)
            session.flush()

            # 2. Upsert Nodes
            node_id_map = {}  # Map from DTO id to DB id
            for node_dto in new_nodes:
                canonical_key = generate_canonical_key(subject_id, node_dto.node_type.value, node_dto.display_name)
                
                db_node = session.query(ConceptNode).filter(
                    ConceptNode.subject_id == subject_id,
                    ConceptNode.canonical_key == canonical_key
                ).first()

                if not db_node:
                    db_node = ConceptNode(
                        id=uuid.uuid4().hex,
                        subject_id=subject_id,
                        canonical_key=canonical_key,
                        display_name=node_dto.display_name,
                        node_type=node_dto.node_type.value,
                        description=node_dto.description,
                        extraction_method=node_dto.extraction_mode,
                        evidence_count=0,
                        aliases_json=json.dumps([node_dto.display_name])
                    )
                    session.add(db_node)
                    session.flush()
                else:
                    
                    aliases = []
                    if db_node.aliases_json:
                        try:
                            aliases = json.loads(db_node.aliases_json)
                        except json.JSONDecodeError:
                            pass
                            
                    if node_dto.display_name not in aliases:
                        aliases.append(node_dto.display_name)
                        db_node.aliases_json = json.dumps(aliases)
                
                node_id_map[node_dto.id] = db_node.id
                node_id_map[canonical_key] = db_node.id
                node_id_map[node_dto.display_name.lower().strip()] = db_node.id
                
                # Add node evidence
                for ev_dto in node_dto.evidence:
                    if ev_dto.chunk_id not in valid_chunks:
                        continue # Stale or invalid chunk
                    db_ev = GraphEvidence(
                        id=uuid.uuid4().hex,
                        subject_id=subject_id,
                        material_id=material_id,
                        chunk_id=ev_dto.chunk_id,
                        node_id=db_node.id,
                        page_number=ev_dto.page_number,
                        snippet=ev_dto.snippet,
                        extraction_method=node_dto.extraction_mode
                    )
                    session.add(db_ev)

            def _resolve_or_create_node_id(raw_ref: str) -> Optional[str]:
                if not raw_ref:
                    return None
                raw_clean = str(raw_ref).strip()
                if raw_clean in node_id_map:
                    return node_id_map[raw_clean]
                if raw_clean.lower() in node_id_map:
                    return node_id_map[raw_clean.lower()]

                # Check if matches existing DB node id
                existing = session.query(ConceptNode).filter(ConceptNode.id == raw_clean).first()
                if existing:
                    node_id_map[raw_clean] = existing.id
                    return existing.id

                # Check by canonical_key or display_name
                c_key = generate_canonical_key(subject_id, "CONCEPT", raw_clean)
                existing_name = session.query(ConceptNode).filter(
                    ConceptNode.subject_id == subject_id,
                    (ConceptNode.canonical_key == c_key) | (ConceptNode.display_name.ilike(raw_clean))
                ).first()
                if existing_name:
                    node_id_map[raw_clean] = existing_name.id
                    return existing_name.id

                return None

            # 3. Upsert Edges
            for edge_dto in new_edges:
                source_db_id = _resolve_or_create_node_id(edge_dto.source_node_id)
                target_db_id = _resolve_or_create_node_id(edge_dto.target_node_id)
                
                if not source_db_id or not target_db_id or source_db_id == target_db_id:
                    continue # Reject self-edges or unresolvable endpoints
                
                db_edge = session.query(ConceptEdge).filter(
                    ConceptEdge.subject_id == subject_id,
                    ConceptEdge.source_node_id == source_db_id,
                    ConceptEdge.target_node_id == target_db_id,
                    ConceptEdge.relation_type == edge_dto.relation_type.value
                ).first()

                if not db_edge:
                    db_edge = ConceptEdge(
                        id=uuid.uuid4().hex,
                        subject_id=subject_id,
                        source_node_id=source_db_id,
                        target_node_id=target_db_id,
                        relation_type=edge_dto.relation_type.value,
                        extraction_method=edge_dto.extraction_mode,
                        evidence_count=0
                    )
                    session.add(db_edge)
                    session.flush()
                
                # Add edge evidence
                for ev_dto in edge_dto.evidence:
                    if ev_dto.chunk_id not in valid_chunks:
                        continue # Stale or invalid chunk
                    db_ev = GraphEvidence(
                        id=uuid.uuid4().hex,
                        subject_id=subject_id,
                        material_id=material_id,
                        chunk_id=ev_dto.chunk_id,
                        edge_id=db_edge.id,
                        page_number=ev_dto.page_number,
                        snippet=ev_dto.snippet,
                        extraction_method=edge_dto.extraction_mode
                    )
                    session.add(db_ev)
            
            # 4. Clean up orphans safely
            session.flush()
            all_subject_nodes = session.query(ConceptNode).filter(ConceptNode.subject_id == subject_id).all()
            for n in all_subject_nodes:
                ev_count = session.query(GraphEvidence).filter(GraphEvidence.node_id == n.id).count()
                n.evidence_count = ev_count
                # Only prune stale temporary resource/module containers from old deleted materials
                if ev_count == 0 and n.node_type in ("RESOURCE", "MODULE"):
                    has_edges = session.query(ConceptEdge).filter(
                        (ConceptEdge.source_node_id == n.id) | (ConceptEdge.target_node_id == n.id)
                    ).first()
                    if not has_edges:
                        session.delete(n)

            # Update edge evidence counts and prune only dangling edges whose endpoints were deleted
            all_subject_edges = session.query(ConceptEdge).filter(ConceptEdge.subject_id == subject_id).all()
            existing_node_ids = {n.id for n in session.query(ConceptNode.id).filter(ConceptNode.subject_id == subject_id).all()}
            for e in all_subject_edges:
                ev_count = session.query(GraphEvidence).filter(GraphEvidence.edge_id == e.id).count()
                e.evidence_count = ev_count
                if e.source_node_id not in existing_node_ids or e.target_node_id not in existing_node_ids:
                    session.delete(e)

            session.commit()
