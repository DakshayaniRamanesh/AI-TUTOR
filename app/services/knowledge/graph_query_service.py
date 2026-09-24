from typing import List, Optional
from sqlalchemy.orm import Session
from app.storage.database import get_session_factory, Subject, ConceptNode, ConceptEdge, GraphEvidence, GraphLayout
from shared.contracts.graph_contracts import GraphSnapshot, GraphNodeDTO, GraphEdgeDTO, GraphEvidenceDTO, NodeType, RelationType, GraphLayoutStateDTO

GLOBAL_NODE_CAP = 100
SUBJECT_NODE_CAP = 12

class GraphQueryService:
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or get_session_factory()

    def get_subject_snapshot(self, subject_id: str) -> GraphSnapshot:
        with self.session_factory() as session:
            subject = session.query(Subject).filter(Subject.id == subject_id).first()
            if not subject:
                return GraphSnapshot(scope="SUBJECT", scope_id=subject_id, revision=1, nodes=[], edges=[])

            nodes = session.query(ConceptNode).filter(ConceptNode.subject_id == subject_id).all()
            edges = session.query(ConceptEdge).filter(ConceptEdge.subject_id == subject_id).all()
            
            node_dtos = []
            for n in nodes:
                try: node_type = NodeType(n.node_type)
                except ValueError: node_type = NodeType.CONCEPT
                
                aliases = []
                if n.aliases_json:
                    try: aliases = json.loads(n.aliases_json)
                    except: pass
                
                node_dtos.append(GraphNodeDTO(
                    id=n.id,
                    subject_id=n.subject_id,
                    canonical_key=n.canonical_key,
                    display_name=n.display_name,
                    node_type=node_type,
                    description=n.description,
                    aliases=aliases,
                    evidence_counts=n.evidence_count or 0,
                    extraction_mode=n.extraction_method,
                ))

            edge_dtos = []
            for e in edges:
                try: relation_type = RelationType(e.relation_type)
                except ValueError: relation_type = RelationType.RELATED_TO
                
                edge_dtos.append(GraphEdgeDTO(
                    id=e.id,
                    subject_id=e.subject_id,
                    source_node_id=e.source_node_id,
                    target_node_id=e.target_node_id,
                    relation_type=relation_type,
                    evidence_counts=e.evidence_count or 0,
                    extraction_mode=e.extraction_method,
                ))

            layouts = session.query(GraphLayout).filter(GraphLayout.scope_type == "SUBJECT", GraphLayout.scope_id == subject_id).all()
            layout_dict = {
                l.node_id: GraphLayoutStateDTO(node_id=l.node_id, x=l.x, y=l.y, pinned=l.pinned)
                for l in layouts
            }

            return GraphSnapshot(
                scope="SUBJECT",
                scope_id=subject_id,
                revision=1,
                nodes=node_dtos,
                edges=edge_dtos,
                layout=layout_dict
            )

    def get_global_snapshot(self) -> GraphSnapshot:
        with self.session_factory() as session:
            subjects = session.query(Subject).all()
            node_dtos = []
            edge_dtos = []

            # Helper to rank concepts deterministically
            def rank_node(n):
                base = 1000 if n.node_type in ["RESOURCE", "MODULE", "NOTEBOOK"] else 0
                return base + (n.evidence_count or 0)
                
            candidate_concept_nodes = []

            for subj in subjects:
                subj_node_id = f"subj_{subj.id}"
                node_dtos.append(GraphNodeDTO(
                    id=subj_node_id,
                    subject_id=subj.id,
                    canonical_key=subj.name.lower(),
                    display_name=subj.name,
                    node_type=NodeType.SUBJECT,
                    description=f"Subject: {subj.name}",
                    extraction_mode="OFFLINE_STRUCTURAL"
                ))

                # Fetch nodes and rank them
                nodes = session.query(ConceptNode).filter(ConceptNode.subject_id == subj.id).all()
                nodes.sort(key=rank_node, reverse=True)
                
                # Cap per subject
                for n in nodes[:SUBJECT_NODE_CAP]:
                    candidate_concept_nodes.append((subj, subj_node_id, n))

            # Pool all candidate concepts, rank globally, and apply global cap
            candidate_concept_nodes.sort(key=lambda item: rank_node(item[2]), reverse=True)
            allowed_global_slots = max(0, GLOBAL_NODE_CAP - len(node_dtos))
            selected_candidates = candidate_concept_nodes[:allowed_global_slots]

            for subj, subj_node_id, n in selected_candidates:
                try: node_type = NodeType(n.node_type)
                except ValueError: node_type = NodeType.CONCEPT
                
                aliases = []
                if n.aliases_json:
                    try: aliases = json.loads(n.aliases_json)
                    except: pass
                
                node_dtos.append(GraphNodeDTO(
                    id=n.id,
                    subject_id=n.subject_id,
                    canonical_key=n.canonical_key,
                    display_name=n.display_name,
                    node_type=node_type,
                    description=n.description,
                    aliases=aliases,
                    evidence_counts=n.evidence_count or 0,
                    extraction_mode=n.extraction_method,
                ))
                
                edge_dtos.append(GraphEdgeDTO(
                    id=f"g_edge_{subj.id}_{n.id}",
                    subject_id=subj.id,
                    source_node_id=subj_node_id,
                    target_node_id=n.id,
                    relation_type=RelationType.CONTAINS,
                    extraction_mode="OFFLINE_STRUCTURAL"
                ))

            layouts = session.query(GraphLayout).filter(GraphLayout.scope_type == "GLOBAL").all()
            layout_dict = {
                l.node_id: GraphLayoutStateDTO(node_id=l.node_id, x=l.x, y=l.y, pinned=l.pinned)
                for l in layouts
            }

            return GraphSnapshot(
                scope="GLOBAL",
                scope_id=None,
                revision=1,
                nodes=node_dtos,
                edges=edge_dtos,
                layout=layout_dict
            )

    def get_one_hop_context(self, subject_id: str, concept_terms: List[str]) -> dict:
        """
        Retrieves 1-hop evidence-backed neighbor relationships for focal concepts.
        Strictly scoped to the given subject_id.
        """
        if not subject_id or not concept_terms:
            return {"focal_concepts": [], "neighbor_concepts": []}

        import json
        normalized_terms = [t.lower().strip() for t in concept_terms if t.strip()]
        if not normalized_terms:
            return {"focal_concepts": [], "neighbor_concepts": []}

        with self.session_factory() as session:
            # Find matching focal nodes
            all_nodes = session.query(ConceptNode).filter(ConceptNode.subject_id == subject_id).all()
            focal_nodes = []
            focal_ids = set()
            focal_names = []

            for n in all_nodes:
                d_name = (n.display_name or "").lower()
                c_key = (n.canonical_key or "").lower()
                aliases = []
                if n.aliases_json:
                    try: aliases = [a.lower() for a in json.loads(n.aliases_json)]
                    except: pass

                matched = any(
                    term in d_name or term in c_key or any(term in a for a in aliases)
                    for term in normalized_terms
                )
                if matched:
                    focal_nodes.append(n)
                    focal_ids.add(n.id)
                    focal_names.append(n.display_name)

            if not focal_nodes:
                return {"focal_concepts": [], "neighbor_concepts": []}

            # Find 1-hop edges
            edges = session.query(ConceptEdge).filter(
                ConceptEdge.subject_id == subject_id,
                (ConceptEdge.source_node_id.in_(focal_ids)) | (ConceptEdge.target_node_id.in_(focal_ids))
            ).all()

            node_map = {n.id: n for n in all_nodes}
            neighbors = []
            seen_neighbors = set()

            for e in edges:
                if (e.evidence_count or 0) <= 0:
                    continue  # Only evidence-backed relations

                other_id = e.target_node_id if e.source_node_id in focal_ids else e.source_node_id
                if other_id not in focal_ids and other_id in node_map and other_id not in seen_neighbors:
                    other_node = node_map[other_id]
                    seen_neighbors.add(other_id)
                    neighbors.append({
                        "concept_key": other_node.canonical_key,
                        "display_name": other_node.display_name,
                        "relation": e.relation_type,
                        "evidence_count": e.evidence_count or 0
                    })

            return {
                "focal_concepts": focal_names[:5],
                "neighbor_concepts": neighbors[:8]
            }
