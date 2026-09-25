import uuid
import pytest
from app.storage.database import User, Subject, Material, ConceptNode, ConceptEdge, GraphEvidence, SubjectChunk
from app.services.knowledge.graph_query_service import GraphQueryService
from app.services.knowledge.graph_reconciliation_service import GraphReconciliationService
from shared.contracts.graph_contracts import GraphNodeDTO, GraphEdgeDTO, GraphEvidenceDTO, NodeType, RelationType

def test_subject_snapshot_skips_invalid_legacy_nodes_and_their_edges(db_session_factory):
    subject_id = f"subj_{uuid.uuid4().hex[:8]}"
    user_id = f"user_{uuid.uuid4().hex[:8]}"
    material_id = f"mat_{uuid.uuid4().hex[:8]}"
    
    with db_session_factory() as session:
        user = User(id=user_id, username=f"test_{uuid.uuid4().hex[:8]}")
        subj = Subject(id=subject_id, user_id=user_id, name="Resilience Subject")
        mat = Material(id=material_id, subject_id=subject_id, filename="Doc.pdf", file_path="/fake", content_hash="hash1")
        session.add_all([user, subj, mat])
        session.commit()

        # Valid node with evidence
        valid_node_id = f"node_valid_{uuid.uuid4().hex[:8]}"
        valid_node = ConceptNode(
            id=valid_node_id,
            subject_id=subject_id,
            canonical_key="valid_concept",
            display_name="Valid Concept",
            node_type="CONCEPT",
            extraction_method="ONLINE_STRUCTURED",
            evidence_count=1
        )
        chunk = SubjectChunk(
            id=f"chk_{uuid.uuid4().hex[:8]}",
            subject_id=subject_id,
            material_id=material_id,
            chunk_index=0,
            text="Valid content"
        )
        valid_ev = GraphEvidence(
            id=f"ev_{uuid.uuid4().hex[:8]}",
            subject_id=subject_id,
            material_id=material_id,
            chunk_id=chunk.id,
            node_id=valid_node_id
        )

        # Invalid legacy node: ONLINE_STRUCTURED with 0 evidence
        invalid_node_id = f"node_invalid_{uuid.uuid4().hex[:8]}"
        invalid_node = ConceptNode(
            id=invalid_node_id,
            subject_id=subject_id,
            canonical_key="invalid_legacy_concept",
            display_name="Invalid Legacy Concept",
            node_type="CONCEPT",
            extraction_method="ONLINE_STRUCTURED",
            evidence_count=0
        )

        # Edge connecting valid node and invalid node
        edge_id = f"edge_{uuid.uuid4().hex[:8]}"
        edge = ConceptEdge(
            id=edge_id,
            subject_id=subject_id,
            source_node_id=valid_node_id,
            target_node_id=invalid_node_id,
            relation_type="RELATED_TO",
            extraction_method="OFFLINE_STRUCTURAL",
            evidence_count=1
        )

        session.add_all([chunk, valid_node, invalid_node])
        session.commit()

        session.add_all([valid_ev, edge])
        session.commit()

    service = GraphQueryService(session_factory=db_session_factory)
    snapshot = service.get_subject_snapshot(subject_id)

    # 1. get_subject_snapshot does not crash
    assert snapshot is not None

    returned_node_ids = {n.id for n in snapshot.nodes}
    # 2. Invalid node is absent from the returned snapshot
    assert invalid_node_id not in returned_node_ids

    # 3. Valid nodes remain
    assert valid_node_id in returned_node_ids

    # 4. Edges connected to skipped nodes are absent
    returned_edge_ids = {e.id for e in snapshot.edges}
    assert edge_id not in returned_edge_ids
    for e in snapshot.edges:
        assert e.source_node_id in returned_node_ids
        assert e.target_node_id in returned_node_ids

def test_reconciliation_does_not_create_unknown_endpoint_node(db_session_factory):
    subject_id = f"subj_{uuid.uuid4().hex[:8]}"
    user_id = f"user_{uuid.uuid4().hex[:8]}"
    material_id = f"mat_{uuid.uuid4().hex[:8]}"

    with db_session_factory() as session:
        user = User(id=user_id, username=f"test_{uuid.uuid4().hex[:8]}")
        subj = Subject(id=subject_id, user_id=user_id, name="Recon Subject")
        mat = Material(id=material_id, subject_id=subject_id, filename="Doc.pdf", file_path="/fake", content_hash="hash2")
        session.add_all([user, subj, mat])
        session.commit()

    service = GraphReconciliationService(session_factory=db_session_factory)

    # Edge refers to completely unknown source and target endpoints
    edge = GraphEdgeDTO(
        id="e_unknown",
        subject_id=subject_id,
        source_node_id="unknown_endpoint_a",
        target_node_id="unknown_endpoint_b",
        relation_type=RelationType.RELATED_TO,
        extraction_mode="OFFLINE_STRUCTURAL",
        evidence=[]
    )

    initial_node_count = 0
    with db_session_factory() as session:
        initial_node_count = session.query(ConceptNode).filter(ConceptNode.subject_id == subject_id).count()

    service.reconcile_material_graph(subject_id, material_id, [], [edge])

    with db_session_factory() as session:
        final_node_count = session.query(ConceptNode).filter(ConceptNode.subject_id == subject_id).count()
        # 5. Reconciliation must not create an unknown endpoint node
        assert final_node_count == initial_node_count
        assert session.query(ConceptEdge).filter(ConceptEdge.id == "e_unknown").first() is None
