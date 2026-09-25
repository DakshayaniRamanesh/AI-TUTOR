import pytest
from pydantic import ValidationError
from shared.contracts.graph_contracts import (
    GraphNodeDTO, GraphEdgeDTO, GraphEvidenceDTO, GraphSnapshot,
    NodeType, RelationType
)

def test_graph_node_enum_validation():
    node = GraphNodeDTO(
        id="1", subject_id="s1", canonical_key="test", display_name="Test",
        node_type="CONCEPT"  # String literal should coerce to Enum
    )
    assert node.node_type == NodeType.CONCEPT
    
    with pytest.raises(ValidationError):
        GraphNodeDTO(
            id="1", subject_id="s1", canonical_key="test", display_name="Test",
            node_type="UNKNOWN_TYPE"
        )

def test_graph_edge_enum_validation():
    edge = GraphEdgeDTO(
        id="1", subject_id="s1", source_node_id="n1", target_node_id="n2",
        relation_type="PART_OF"
    )
    assert edge.relation_type == RelationType.PART_OF
    
    with pytest.raises(ValidationError):
        GraphEdgeDTO(
            id="1", subject_id="s1", source_node_id="n1", target_node_id="n2",
            relation_type="INVALID_REL"
        )

def test_graph_dto_json_roundtrip():
    node = GraphNodeDTO(
        id="n1", subject_id="s1", canonical_key="test", display_name="Test",
        node_type=NodeType.CONCEPT,
        evidence=[GraphEvidenceDTO(id="e1", material_id="m1", chunk_id="c1")]
    )
    edge = GraphEdgeDTO(
        id="e1", subject_id="s1", source_node_id="n1", target_node_id="n2",
        relation_type=RelationType.PART_OF
    )
    snapshot = GraphSnapshot(scope="SUBJECT", scope_id="s1", revision=1, nodes=[node], edges=[edge])
    
    # Serialize to JSON and parse back
    json_data = snapshot.model_dump_json()
    snapshot_restored = GraphSnapshot.model_validate_json(json_data)
    
    assert snapshot_restored.nodes[0].node_type == NodeType.CONCEPT
    assert snapshot_restored.edges[0].relation_type == RelationType.PART_OF
    assert snapshot_restored.nodes[0].evidence[0].material_id == "m1"

def test_semantic_node_and_edge_without_evidence_raises():
    with pytest.raises(ValidationError, match="Semantic nodes require valid chunk_id evidence."):
        GraphNodeDTO(
            id="n_semantic",
            subject_id="s1",
            canonical_key="test_semantic",
            display_name="Test Semantic",
            node_type=NodeType.CONCEPT,
            extraction_mode="ONLINE_STRUCTURED",
            evidence=[]
        )

    with pytest.raises(ValidationError, match="Semantic edges require valid chunk_id evidence."):
        GraphEdgeDTO(
            id="e_semantic",
            subject_id="s1",
            source_node_id="n1",
            target_node_id="n2",
            relation_type=RelationType.PREREQUISITE_OF,
            extraction_mode="ONLINE_STRUCTURED",
            evidence=[]
        )
