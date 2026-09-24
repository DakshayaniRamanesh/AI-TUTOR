"""Add group_id and group_revision to reasoning_steps

Revision ID: 4996ac6ad613
Revises: 3660ad06ce3c
Create Date: 2026-09-24 07:59:34.210446

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4996ac6ad613'
down_revision: Union[str, Sequence[str], None] = '3660ad06ce3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    from sqlalchemy import inspect
    inspector = inspect(conn)
    existing_cols = []
    if 'reasoning_steps' in inspector.get_table_names():
        existing_cols = [c['name'] for c in inspector.get_columns('reasoning_steps')]

    with op.batch_alter_table('reasoning_steps') as batch_op:
        if 'group_id' not in existing_cols:
            batch_op.add_column(sa.Column('group_id', sa.String(), nullable=True))
        if 'group_revision' not in existing_cols:
            batch_op.add_column(sa.Column('group_revision', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    from sqlalchemy import inspect
    inspector = inspect(conn)
    existing_cols = []
    if 'reasoning_steps' in inspector.get_table_names():
        existing_cols = [c['name'] for c in inspector.get_columns('reasoning_steps')]

    with op.batch_alter_table('reasoning_steps') as batch_op:
        if 'group_revision' in existing_cols:
            batch_op.drop_column('group_revision')
        if 'group_id' in existing_cols:
            batch_op.drop_column('group_id')
