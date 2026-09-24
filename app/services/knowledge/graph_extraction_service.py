from app.services.knowledge.graph_reconciliation_service import GraphReconciliationService
import uuid
import json
import os
from typing import List, Dict, Set, Optional, Tuple
from sqlalchemy.orm import Session
from app.storage.database import SubjectChunk, Subject, Material, Notebook, ConceptNode, ConceptEdge, GraphEvidence, get_session_factory
from shared.contracts.graph_contracts import GraphNodeDTO, GraphEdgeDTO, GraphEvidenceDTO, GraphSnapshot

class KnowledgeGraphExtractionService:
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or get_session_factory()

    def extract_structural_graph(self, subject_id: str, material_id: str = None) -> GraphSnapshot:
        """
        Offline, deterministic extraction of knowledge graph structure from SQL database.
        No LLM calls. Safe for synchronous background workers.
        """
        nodes_dict: Dict[str, GraphNodeDTO] = {}
        edges_dict: Dict[str, GraphEdgeDTO] = {}

        def add_node(node: GraphNodeDTO):
            if node.id not in nodes_dict:
                nodes_dict[node.id] = node

        def add_edge(edge: GraphEdgeDTO):
            key = f"{edge.source_node_id}->{edge.target_node_id}:{edge.relation_type}"
            if key not in edges_dict:
                edges_dict[key] = edge
            else:
                edges_dict[key].evidence.extend(edge.evidence)
                edges_dict[key].evidence_counts += edge.evidence_counts

        with self.session_factory() as session:
            subject = session.query(Subject).filter(Subject.id == subject_id).first()
            if not subject:
                return GraphSnapshot(scope="SUBJECT", scope_id=subject_id, revision=1)

            # 1. Subject Node
            subj_node_id = f"subj_{subject_id}"
            add_node(GraphNodeDTO(
                id=subj_node_id,
                subject_id=subject_id,
                canonical_key=subject.name.lower(),
                display_name=subject.name,
                node_type="SUBJECT",
                extraction_mode="OFFLINE_STRUCTURAL"
            ))

            # 2. Materials & Chunks
                        if material_id:
                materials = session.query(Material).filter(Material.id == material_id).all()
            else:
                materials = session.query(Material).filter(Material.subject_id == subject_id).all()
            for mat in materials:
                mat_node_id = f"mat_{mat.id}"
                add_node(GraphNodeDTO(
                    id=mat_node_id,
                    subject_id=subject_id,
                    canonical_key=mat.filename.lower(),
                    display_name=mat.filename,
                    node_type="RESOURCE",
                    extraction_mode="OFFLINE_STRUCTURAL"
                ))
                add_edge(GraphEdgeDTO(
                    id=str(uuid.uuid4()),
                    subject_id=subject_id,
                    source_node_id=mat_node_id,
                    target_node_id=subj_node_id,
                    relation_type="PART_OF",
                    extraction_mode="OFFLINE_STRUCTURAL"
                ))

                chunks = session.query(SubjectChunk).filter(SubjectChunk.material_id == mat.id).all()
                for chunk in chunks:
                    if chunk.chapter:
                        chap_key = f"{mat.id}_chap_{chunk.chapter.lower()}"
                        chap_node_id = f"chap_{hash(chap_key)}"
                        
                        evidence = GraphEvidenceDTO(
                            id=str(uuid.uuid4()),
                            material_id=mat.id,
                            chunk_id=chunk.id,
                            page_number=chunk.page_number,
                            snippet=chunk.text[:200] if chunk.text else ""
                        )
                        
                        if chap_node_id not in nodes_dict:
                            add_node(GraphNodeDTO(
                                id=chap_node_id,
                                subject_id=subject_id,
                                canonical_key=chunk.chapter.lower(),
                                display_name=chunk.chapter,
                                node_type="MODULE",
                                evidence_counts=1,
                                extraction_mode="OFFLINE_STRUCTURAL",
                                evidence=[evidence]
                            ))
                            add_edge(GraphEdgeDTO(
                                id=str(uuid.uuid4()),
                                subject_id=subject_id,
                                source_node_id=chap_node_id,
                                target_node_id=mat_node_id,
                                relation_type="PART_OF",
                                extraction_mode="OFFLINE_STRUCTURAL"
                            ))
                        else:
                            nodes_dict[chap_node_id].evidence.append(evidence)
                            nodes_dict[chap_node_id].evidence_counts += 1

                    if chunk.section:
                        sec_key = f"{mat.id}_sec_{chunk.section.lower()}"
                        sec_node_id = f"sec_{hash(sec_key)}"
                        
                        evidence = GraphEvidenceDTO(
                            id=str(uuid.uuid4()),
                            material_id=mat.id,
                            chunk_id=chunk.id,
                            page_number=chunk.page_number,
                            snippet=chunk.text[:200] if chunk.text else ""
                        )
                        
                        if sec_node_id not in nodes_dict:
                            add_node(GraphNodeDTO(
                                id=sec_node_id,
                                subject_id=subject_id,
                                canonical_key=chunk.section.lower(),
                                display_name=chunk.section,
                                node_type="CONCEPT",
                                evidence_counts=1,
                                extraction_mode="OFFLINE_STRUCTURAL",
                                evidence=[evidence]
                            ))
                            parent_target = f"chap_{hash(f'{mat.id}_chap_{chunk.chapter.lower()}')}" if chunk.chapter else mat_node_id
                            add_edge(GraphEdgeDTO(
                                id=str(uuid.uuid4()),
                                subject_id=subject_id,
                                source_node_id=sec_node_id,
                                target_node_id=parent_target,
                                relation_type="PART_OF",
                                extraction_mode="OFFLINE_STRUCTURAL"
                            ))
                        else:
                            nodes_dict[sec_node_id].evidence.append(evidence)
                            nodes_dict[sec_node_id].evidence_counts += 1

            # 3. Notebooks
            notebooks = session.query(Notebook).filter(Notebook.subject_id == subject_id).all()
            for nb in notebooks:
                nb_node_id = f"nb_{nb.id}"
                add_node(GraphNodeDTO(
                    id=nb_node_id,
                    subject_id=subject_id,
                    canonical_key=nb.name.lower(),
                    display_name=nb.name,
                    node_type="NOTEBOOK",
                    extraction_mode="OFFLINE_STRUCTURAL"
                ))
                add_edge(GraphEdgeDTO(
                    id=str(uuid.uuid4()),
                    subject_id=subject_id,
                    source_node_id=nb_node_id,
                    target_node_id=subj_node_id,
                    relation_type="PART_OF",
                    extraction_mode="OFFLINE_STRUCTURAL"
                ))

        return GraphSnapshot(
            scope="SUBJECT",
            scope_id=subject_id,
            revision=1,
            nodes=list(nodes_dict.values()),
            edges=list(edges_dict.values()),
            build_state="READY"
        )

