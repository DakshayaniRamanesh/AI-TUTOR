"""add reasoning ancestry

Revision ID: febdd314c89e
Revises: a1b2c3d4e5f6
Create Date: 2026-09-24 16:34:09.882330

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'febdd314c89e'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('reasoning_steps') as batch_op:
        batch_op.add_column(sa.Column('previous_step_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('replaces_step_id', sa.String(), nullable=True))

def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('reasoning_steps') as batch_op:
        batch_op.drop_column('replaces_step_id')
        batch_op.drop_column('previous_step_id')
