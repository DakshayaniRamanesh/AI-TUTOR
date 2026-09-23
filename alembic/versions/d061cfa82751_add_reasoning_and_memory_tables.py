"""Add reasoning and memory tables

Revision ID: d061cfa82751
Revises: 
Create Date: 2026-09-22 23:20:01.824696

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd061cfa82751'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    from sqlalchemy import inspect
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    if 'concept_memory' not in tables:
        op.create_table('concept_memory',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('concept_key', sa.String(), nullable=False),
    sa.Column('encounter_count', sa.Integer(), nullable=True),
    sa.Column('success_count', sa.Integer(), nullable=True),
    sa.Column('struggle_count', sa.Integer(), nullable=True),
    sa.Column('mastery_estimate', sa.Float(), nullable=True),
    sa.Column('last_encountered', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    if 'learning_sessions' not in tables:
        op.create_table('learning_sessions',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=True),
    sa.Column('notebook_id', sa.String(), nullable=True),
    sa.Column('subject_id', sa.String(), nullable=True),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('ended_at', sa.DateTime(), nullable=True),
    sa.Column('status', sa.Enum('CREATED', 'ACTIVE', 'PAUSED', 'COMPLETED', 'ABANDONED', name='sessionstatus'), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['notebook_id'], ['notebooks.id'], ),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    if 'problem_attempts' not in tables:
        op.create_table('problem_attempts',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('learning_session_id', sa.String(), nullable=False),
    sa.Column('problem_text', sa.Text(), nullable=True),
    sa.Column('problem_latex', sa.Text(), nullable=True),
    sa.Column('source_type', sa.String(), nullable=True),
    sa.Column('source_reference', sa.String(), nullable=True),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('status', sa.Enum('IN_PROGRESS', 'COMPLETED', name='attemptstatus'), nullable=True),
    sa.ForeignKeyConstraint(['learning_session_id'], ['learning_sessions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    if 'reasoning_steps' not in tables:
        op.create_table('reasoning_steps',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('attempt_id', sa.String(), nullable=False),
    sa.Column('sequence_number', sa.Integer(), nullable=False),
    sa.Column('recognized_text', sa.Text(), nullable=False),
    sa.Column('recognized_latex', sa.Text(), nullable=True),
    sa.Column('normalized_expression', sa.Text(), nullable=True),
    sa.Column('content_type', sa.String(), nullable=True),
    sa.Column('recognition_confidence', sa.Float(), nullable=True),
    sa.Column('validation_verdict', sa.String(), nullable=True),
    sa.Column('previous_step_id', sa.String(), nullable=True),
    sa.Column('replaces_step_id', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['attempt_id'], ['problem_attempts.id'], ),
    sa.ForeignKeyConstraint(['previous_step_id'], ['reasoning_steps.id'], ),
    sa.ForeignKeyConstraint(['replaces_step_id'], ['reasoning_steps.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    if 'canvas_anchor_records' not in tables:
        op.create_table('canvas_anchor_records',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('reasoning_step_id', sa.String(), nullable=False),
    sa.Column('board_id', sa.String(), nullable=False),
    sa.Column('board_revision', sa.String(), nullable=True),
    sa.Column('item_ids', sa.Text(), nullable=False),
    sa.Column('bbox_snapshot', sa.Text(), nullable=True),
    sa.Column('coordinate_space', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['reasoning_step_id'], ['reasoning_steps.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    if 'validation_events' not in tables:
        op.create_table('validation_events',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('reasoning_step_id', sa.String(), nullable=False),
    sa.Column('validator_name', sa.String(), nullable=False),
    sa.Column('verdict', sa.String(), nullable=False),
    sa.Column('explanation', sa.Text(), nullable=True),
    sa.Column('rule_used', sa.String(), nullable=True),
    sa.Column('structured_details', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['reasoning_step_id'], ['reasoning_steps.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('validation_events')
    op.drop_table('canvas_anchor_records')
    op.drop_table('reasoning_steps')
    op.drop_table('problem_attempts')
    op.drop_table('learning_sessions')
    op.drop_table('concept_memory')
    # ### end Alembic commands ###
