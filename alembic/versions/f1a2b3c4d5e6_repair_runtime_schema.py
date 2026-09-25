"""Repair runtime graph schema and subject-chunk indexes.

Revision ID: f1a2b3c4d5e6
Revises: ecb5ad7a15e6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "ecb5ad7a15e6"
branch_labels = None
depends_on = None


def _columns(inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "concept_edges" in tables:
        existing = _columns(inspector, "concept_edges")
        additions = [
            ("source_node_id", sa.Column("source_node_id", sa.String(), nullable=True)),
            ("target_node_id", sa.Column("target_node_id", sa.String(), nullable=True)),
            ("relation_type", sa.Column("relation_type", sa.String(), nullable=True)),
            ("evidence_count", sa.Column("evidence_count", sa.Integer(), server_default="0")),
            ("extraction_method", sa.Column("extraction_method", sa.String(), nullable=True)),
            ("confidence", sa.Column("confidence", sa.Float(), nullable=True)),
            ("created_at", sa.Column("created_at", sa.DateTime(), nullable=True)),
            ("updated_at", sa.Column("updated_at", sa.DateTime(), nullable=True)),
        ]
        missing = [column for name, column in additions if name not in existing]
        if missing:
            with op.batch_alter_table("concept_edges") as batch:
                for column in missing:
                    batch.add_column(column)

        # Preserve legacy graph data where names still match modern node labels.
        op.execute(sa.text("""
            UPDATE concept_edges
               SET source_node_id = COALESCE(
                       source_node_id,
                       (SELECT id FROM concept_nodes
                         WHERE concept_nodes.subject_id = concept_edges.subject_id
                           AND lower(concept_nodes.display_name) = lower(concept_edges.source_name)
                         LIMIT 1)),
                   target_node_id = COALESCE(
                       target_node_id,
                       (SELECT id FROM concept_nodes
                         WHERE concept_nodes.subject_id = concept_edges.subject_id
                           AND lower(concept_nodes.display_name) = lower(concept_edges.target_name)
                         LIMIT 1)),
                   relation_type = COALESCE(relation_type, 'RELATED_TO'),
                   evidence_count = COALESCE(evidence_count, 0)
        """))

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "graph_evidence" not in tables:
        op.create_table(
            "graph_evidence",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("subject_id", sa.String(), sa.ForeignKey("subjects.id"), nullable=False),
            sa.Column("material_id", sa.String(), sa.ForeignKey("materials.id"), nullable=True),
            sa.Column("chunk_id", sa.String(), sa.ForeignKey("subject_chunks.id"), nullable=True),
            sa.Column("node_id", sa.String(), sa.ForeignKey("concept_nodes.id"), nullable=True),
            sa.Column("edge_id", sa.String(), sa.ForeignKey("concept_edges.id"), nullable=True),
            sa.Column("page_number", sa.Integer(), nullable=True),
            sa.Column("snippet", sa.Text(), nullable=True),
            sa.Column("extraction_method", sa.String(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )

    if "graph_layout_state" not in tables:
        op.create_table(
            "graph_layout_state",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("scope_type", sa.String(), nullable=False),
            sa.Column("scope_id", sa.String(), nullable=True),
            sa.Column("node_id", sa.String(), nullable=False),
            sa.Column("x", sa.Float(), nullable=False),
            sa.Column("y", sa.Float(), nullable=False),
            sa.Column("pinned", sa.Boolean(), server_default=sa.false()),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("graph_revision", sa.Integer(), server_default="0"),
            sa.UniqueConstraint("scope_type", "scope_id", "node_id", name="uq_graph_layout_state_scope_node"),
        )

    inspector = sa.inspect(bind)
    if "subject_chunks" in inspector.get_table_names():
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("subject_chunks")}
        if "ix_subject_chunks_subject_id" not in existing_indexes:
            op.create_index("ix_subject_chunks_subject_id", "subject_chunks", ["subject_id"])
        if "ix_subject_chunks_material_id" not in existing_indexes:
            op.create_index("ix_subject_chunks_material_id", "subject_chunks", ["material_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "subject_chunks" in tables:
        indexes = {idx["name"] for idx in inspector.get_indexes("subject_chunks")}
        for name in ("ix_subject_chunks_material_id", "ix_subject_chunks_subject_id"):
            if name in indexes:
                op.drop_index(name, table_name="subject_chunks")
    if "graph_layout_state" in tables:
        op.drop_table("graph_layout_state")
    if "graph_evidence" in tables:
        op.drop_table("graph_evidence")
