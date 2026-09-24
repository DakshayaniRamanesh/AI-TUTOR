"""Add aliases_json to ConceptNode

Revision ID: 3ed8cb85d605
Revises: d694b2dbb8cf
Create Date: 2026-09-24 13:42:35.795550

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ed8cb85d605'
down_revision: Union[str, Sequence[str], None] = 'd694b2dbb8cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


import json
from sqlalchemy import inspect

def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('concept_nodes')]

    # Add new column if missing
    if 'aliases_json' not in columns:
        with op.batch_alter_table('concept_nodes') as batch_op:
            batch_op.add_column(sa.Column('aliases_json', sa.String(), nullable=True, server_default='[]'))
        
    # Migrate data if old column exists
    if 'aliases' in columns:
        nodes = conn.execute(sa.text("SELECT id, aliases FROM concept_nodes")).fetchall()
        for node_id, aliases in nodes:
            if aliases:
                aliases_list = [a.strip() for a in aliases.split(',') if a.strip()]
                aliases_json = json.dumps(aliases_list)
            else:
                aliases_json = "[]"
            conn.execute(
                sa.text("UPDATE concept_nodes SET aliases_json = :json WHERE id = :id"),
                {"json": aliases_json, "id": node_id}
            )
        
        # Drop old column
        with op.batch_alter_table('concept_nodes') as batch_op:
            batch_op.drop_column('aliases')


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('concept_nodes')]

    # Add old column back if missing
    if 'aliases' not in columns:
        with op.batch_alter_table('concept_nodes') as batch_op:
            batch_op.add_column(sa.Column('aliases', sa.String(), nullable=True, server_default=''))
        
    # Migrate data back if new column exists
    if 'aliases_json' in columns:
        nodes = conn.execute(sa.text("SELECT id, aliases_json FROM concept_nodes")).fetchall()
        for node_id, aliases_json in nodes:
            aliases_str = ""
            if aliases_json:
                try:
                    aliases_list = json.loads(aliases_json)
                    aliases_str = ",".join(aliases_list)
                except:
                    pass
            conn.execute(
                sa.text("UPDATE concept_nodes SET aliases = :astr WHERE id = :id"),
                {"astr": aliases_str, "id": node_id}
            )
        
        # Drop new column
        with op.batch_alter_table('concept_nodes') as batch_op:
            batch_op.drop_column('aliases_json')
