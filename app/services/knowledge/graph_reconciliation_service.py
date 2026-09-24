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

            # 3. Upsert Edges
            for edge_dto in new_edges:
                source_db_id = node_id_map.get(edge_dto.source_node_id, edge_dto.source_node_id)
                target_db_id = node_id_map.get(edge_dto.target_node_id, edge_dto.target_node_id)
                
                if source_db_id == target_db_id:
                    continue # Reject self-edges
                    
                # Reject unsupported enums (handled by Pydantic, but double check)
                
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
            
            # 4. Clean up orphans
            # Find nodes with 0 evidence
            session.flush()
            all_subject_nodes = session.query(ConceptNode).filter(ConceptNode.subject_id == subject_id).all()
            for n in all_subject_nodes:
                ev_count = session.query(GraphEvidence).filter(GraphEvidence.node_id == n.id).count()
                n.evidence_count = ev_count
                
                # We only delete orphans if they are not SUBJECT nodes
                if ev_count == 0 and n.node_type != "SUBJECT":
                    # Delete edges connected to this node
                    session.query(ConceptEdge).filter((ConceptEdge.source_node_id == n.id) | (ConceptEdge.target_node_id == n.id)).delete()
                    session.delete(n)

            # Update edge evidence counts and remove orphan edges
            all_subject_edges = session.query(ConceptEdge).filter(ConceptEdge.subject_id == subject_id).all()
            for e in all_subject_edges:
                ev_count = session.query(GraphEvidence).filter(GraphEvidence.edge_id == e.id).count()
                e.evidence_count = ev_count
                if ev_count == 0:
                    session.delete(e)

            session.commit()
