import os
import re

content = open('app/storage/models/learning.py').read()

content = content.replace('from sqlalchemy import Column', 'from sqlalchemy import Column, Index, UniqueConstraint')

content = content.replace(
    'attempts = relationship("ProblemAttempt", back_populates="session", cascade="all, delete-orphan")',
    'attempts = relationship("ProblemAttempt", back_populates="session", cascade="all, delete-orphan")\n\n    __table_args__ = (\n        Index("ix_learning_sessions_notebook_status", "notebook_id", "status"),\n    )'
)

content = content.replace(
    'steps = relationship("ReasoningStep", back_populates="attempt", cascade="all, delete-orphan")',
    'steps = relationship("ReasoningStep", back_populates="attempt", cascade="all, delete-orphan")\n\n    __table_args__ = (\n        Index("ix_problem_attempts_session_status", "learning_session_id", "status"),\n    )'
)

content = content.replace(
    'validation_events = relationship("ValidationEvent", back_populates="step", cascade="all, delete-orphan")',
    'validation_events = relationship("ValidationEvent", back_populates="step", cascade="all, delete-orphan")\n\n    __table_args__ = (\n        UniqueConstraint("attempt_id", "sequence_number", name="uq_reasoning_step_attempt_seq"),\n        Index("ix_reasoning_steps_attempt_seq", "attempt_id", "sequence_number"),\n    )'
)

open('app/storage/models/learning.py', 'w').write(content)
