import os

filepath = 'alembic/versions/3660ad06ce3c_add_schema_invariants.py'
content = open(filepath).read()

content = content.replace("op.create_unique_constraint('uq_reasoning_step_attempt_seq', 'reasoning_steps', ['attempt_id', 'sequence_number'])", "with op.batch_alter_table('reasoning_steps') as batch_op:\n        batch_op.create_unique_constraint('uq_reasoning_step_attempt_seq', ['attempt_id', 'sequence_number'])")
content = content.replace("op.drop_constraint('uq_reasoning_step_attempt_seq', 'reasoning_steps', type_='unique')", "with op.batch_alter_table('reasoning_steps') as batch_op:\n        batch_op.drop_constraint('uq_reasoning_step_attempt_seq', type_='unique')")

open(filepath, 'w').write(content)
