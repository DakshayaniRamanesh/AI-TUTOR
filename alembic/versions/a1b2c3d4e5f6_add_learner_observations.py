"""add learner_observations

Revision ID: a1b2c3d4e5f6
Revises: 3ed8cb85d605
Create Date: 2026-09-24 14:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '3ed8cb85d605'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if 'learner_observations' not in tables:
        op.create_table(
            'learner_observations',
            sa.Column('id', sa.String(), primary_key=True),
            sa.Column('user_id', sa.String(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('subject_id', sa.String(), sa.ForeignKey('subjects.id'), nullable=True),
            sa.Column('observation_type', sa.String(), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('supporting_attempt_ids_json', sa.Text(), default='[]'),
            sa.Column('supporting_step_ids_json', sa.Text(), default='[]'),
            sa.Column('occurrence_count', sa.Integer(), default=1),
            sa.Column('status', sa.String(), default='ACTIVE'),
            sa.Column('confidence', sa.Float(), default=1.0),
            sa.Column('first_seen', sa.DateTime(), nullable=True),
            sa.Column('last_seen', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )
        op.create_index(
            'ix_learner_observations_user_subject',
            'learner_observations',
            ['user_id', 'subject_id']
        )

def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if 'learner_observations' in tables:
        op.drop_index('ix_learner_observations_user_subject', table_name='learner_observations')
        op.drop_table('learner_observations')
