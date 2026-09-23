import os

filepath = 'alembic/versions/3660ad06ce3c_add_schema_invariants.py'
content = open(filepath).read()

# Make it idempotent
injection = '''
    conn = op.get_bind()
    from sqlalchemy import inspect
    inspector = inspect(conn)
    
    def has_index(table_name, index_name):
        return any(idx['name'] == index_name for idx in inspector.get_indexes(table_name))
        
    def has_constraint(table_name, constraint_name):
        return any(uc['name'] == constraint_name for uc in inspector.get_unique_constraints(table_name))
        
'''

content = content.replace('def upgrade() -> None:\n    """Upgrade schema."""', 'def upgrade() -> None:\n    """Upgrade schema."""' + injection)

content = content.replace("op.create_index('ix_learning_sessions_notebook_status'", "if not has_index('learning_sessions', 'ix_learning_sessions_notebook_status'):\n        op.create_index('ix_learning_sessions_notebook_status'")
content = content.replace("op.create_index('ix_problem_attempts_session_status'", "if not has_index('problem_attempts', 'ix_problem_attempts_session_status'):\n        op.create_index('ix_problem_attempts_session_status'")
content = content.replace("op.create_index('ix_reasoning_steps_attempt_seq'", "if not has_index('reasoning_steps', 'ix_reasoning_steps_attempt_seq'):\n        op.create_index('ix_reasoning_steps_attempt_seq'")

content = content.replace("with op.batch_alter_table('reasoning_steps') as batch_op:", "if not has_constraint('reasoning_steps', 'uq_reasoning_step_attempt_seq'):\n        with op.batch_alter_table('reasoning_steps') as batch_op:")

open(filepath, 'w').write(content)
