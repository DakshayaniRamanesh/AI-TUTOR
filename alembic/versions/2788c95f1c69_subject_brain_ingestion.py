"""subject_brain_ingestion

Revision ID: 2788c95f1c69
Revises: 4996ac6ad613
Create Date: 2026-09-24 08:46:52.122734

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2788c95f1c69'
down_revision: Union[str, Sequence[str], None] = '4996ac6ad613'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    from sqlalchemy import inspect
    inspector = inspect(conn)
    existing_cols = []
    tables = inspector.get_table_names()
    if 'materials' in tables:
        existing_cols = [c['name'] for c in inspector.get_columns('materials')]

    # 1. Add columns to materials
    with op.batch_alter_table('materials') as batch_op:
        if 'resource_type' not in existing_cols:
            batch_op.add_column(sa.Column('resource_type', sa.String(), nullable=True, server_default='PDF'))
        if 'mime_type' not in existing_cols:
            batch_op.add_column(sa.Column('mime_type', sa.String(), nullable=True))
        if 'content_hash' not in existing_cols:
            batch_op.add_column(sa.Column('content_hash', sa.String(), nullable=True))
        if 'file_size' not in existing_cols:
            batch_op.add_column(sa.Column('file_size', sa.Integer(), nullable=True))
        if 'ingestion_status' not in existing_cols:
            batch_op.add_column(sa.Column('ingestion_status', sa.String(), nullable=True, server_default='REGISTERED'))
        if 'chunk_count' not in existing_cols:
            batch_op.add_column(sa.Column('chunk_count', sa.Integer(), nullable=True, server_default='0'))
        if 'ingestion_error' not in existing_cols:
            batch_op.add_column(sa.Column('ingestion_error', sa.String(), nullable=True))
        if 'last_indexed_at' not in existing_cols:
            batch_op.add_column(sa.Column('last_indexed_at', sa.DateTime(), nullable=True))
        if 'metadata_json' not in existing_cols:
            batch_op.add_column(sa.Column('metadata_json', sa.String(), nullable=True))

    # 2. Create subject_chunks table
    if 'subject_chunks' not in tables:
        op.create_table(
            'subject_chunks',
            sa.Column('id', sa.String(), primary_key=True),
            sa.Column('subject_id', sa.String(), sa.ForeignKey('subjects.id'), nullable=False),
            sa.Column('material_id', sa.String(), sa.ForeignKey('materials.id'), nullable=False),
            sa.Column('chunk_index', sa.Integer(), nullable=False),
            sa.Column('document_title', sa.String(), nullable=True),
            sa.Column('chapter', sa.String(), nullable=True),
            sa.Column('section', sa.String(), nullable=True),
            sa.Column('page_number', sa.Integer(), nullable=True),
            sa.Column('content_type', sa.String(), nullable=True),
            sa.Column('text', sa.String(), nullable=True),
            sa.Column('token_count', sa.Integer(), nullable=True),
            sa.Column('content_hash', sa.String(), nullable=True),
            sa.Column('parent_path', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )
        
        op.create_index('ix_subject_chunks_subject_id', 'subject_chunks', ['subject_id'])
        op.create_index('ix_subject_chunks_material_id', 'subject_chunks', ['material_id'])
        op.create_index('ix_subject_chunks_subject_content_type', 'subject_chunks', ['subject_id', 'content_type'])
        op.create_index('ix_subject_chunks_content_hash', 'subject_chunks', ['content_hash'])

    # 3. Create FTS5 virtual table
    op.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS subject_chunks_fts 
        USING fts5(
            text, 
            document_title, 
            chapter, 
            section, 
            chunk_id UNINDEXED, 
            subject_id UNINDEXED
        )
    """)

    # 4. Create FTS triggers for insert, delete, update
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS subject_chunks_ai AFTER INSERT ON subject_chunks BEGIN
            INSERT INTO subject_chunks_fts(rowid, text, document_title, chapter, section, chunk_id, subject_id)
            VALUES (new.rowid, new.text, new.document_title, new.chapter, new.section, new.id, new.subject_id);
        END;
    """)
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS subject_chunks_ad AFTER DELETE ON subject_chunks BEGIN
            INSERT INTO subject_chunks_fts(subject_chunks_fts, rowid, text, document_title, chapter, section, chunk_id, subject_id)
            VALUES ('delete', old.rowid, old.text, old.document_title, old.chapter, old.section, old.id, old.subject_id);
        END;
    """)
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS subject_chunks_au AFTER UPDATE ON subject_chunks BEGIN
            INSERT INTO subject_chunks_fts(subject_chunks_fts, rowid, text, document_title, chapter, section, chunk_id, subject_id)
            VALUES ('delete', old.rowid, old.text, old.document_title, old.chapter, old.section, old.id, old.subject_id);
            INSERT INTO subject_chunks_fts(rowid, text, document_title, chapter, section, chunk_id, subject_id)
            VALUES (new.rowid, new.text, new.document_title, new.chapter, new.section, new.id, new.subject_id);
        END;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS subject_chunks_au")
    op.execute("DROP TRIGGER IF EXISTS subject_chunks_ad")
    op.execute("DROP TRIGGER IF EXISTS subject_chunks_ai")
    op.execute("DROP TABLE IF EXISTS subject_chunks_fts")
    
    op.drop_index('ix_subject_chunks_content_hash', table_name='subject_chunks')
    op.drop_index('ix_subject_chunks_subject_content_type', table_name='subject_chunks')
    op.drop_index('ix_subject_chunks_material_id', table_name='subject_chunks')
    op.drop_index('ix_subject_chunks_subject_id', table_name='subject_chunks')
    op.drop_table('subject_chunks')
    
    with op.batch_alter_table('materials') as batch_op:
        batch_op.drop_column('metadata_json')
        batch_op.drop_column('last_indexed_at')
        batch_op.drop_column('ingestion_error')
        batch_op.drop_column('chunk_count')
        batch_op.drop_column('ingestion_status')
        batch_op.drop_column('file_size')
        batch_op.drop_column('content_hash')
        batch_op.drop_column('mime_type')
        batch_op.drop_column('resource_type')
