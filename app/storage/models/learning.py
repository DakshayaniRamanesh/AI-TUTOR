import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum, Integer, Float, Text
from sqlalchemy.orm import relationship
from app.storage.database import Base

class SessionStatus(str, enum.Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"

class AttemptStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"

class LearningSession(Base):
    __tablename__ = "learning_sessions"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    notebook_id = Column(String, ForeignKey("notebooks.id"), nullable=True)
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=True)
    
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    status = Column(SQLEnum(SessionStatus), default=SessionStatus.CREATED)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    attempts = relationship("ProblemAttempt", back_populates="session", cascade="all, delete-orphan")

class ProblemAttempt(Base):
    __tablename__ = "problem_attempts"
    id = Column(String, primary_key=True)
    learning_session_id = Column(String, ForeignKey("learning_sessions.id"), nullable=False)
    
    problem_text = Column(Text, nullable=True)
    problem_latex = Column(Text, nullable=True)
    source_type = Column(String, nullable=True)
    source_reference = Column(String, nullable=True)
    
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(SQLEnum(AttemptStatus), default=AttemptStatus.IN_PROGRESS)

    session = relationship("LearningSession", back_populates="attempts")
    steps = relationship("ReasoningStep", back_populates="attempt", cascade="all, delete-orphan")

class ReasoningStep(Base):
    __tablename__ = "reasoning_steps"
    id = Column(String, primary_key=True)
    attempt_id = Column(String, ForeignKey("problem_attempts.id"), nullable=False)
    
    sequence_number = Column(Integer, nullable=False)
    recognized_text = Column(Text, nullable=False)
    recognized_latex = Column(Text, nullable=True)
    normalized_expression = Column(Text, nullable=True)
    content_type = Column(String, nullable=True)
    recognition_confidence = Column(Float, nullable=True)
    
    validation_verdict = Column(String, nullable=True)
    previous_step_id = Column(String, ForeignKey("reasoning_steps.id"), nullable=True)
    replaces_step_id = Column(String, ForeignKey("reasoning_steps.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    attempt = relationship("ProblemAttempt", back_populates="steps")
    anchors = relationship("CanvasAnchorRecord", back_populates="step", cascade="all, delete-orphan")
    validation_events = relationship("ValidationEvent", back_populates="step", cascade="all, delete-orphan")

class CanvasAnchorRecord(Base):
    __tablename__ = "canvas_anchor_records"
    id = Column(String, primary_key=True)
    reasoning_step_id = Column(String, ForeignKey("reasoning_steps.id"), nullable=False)
    
    board_id = Column(String, nullable=False)
    board_revision = Column(String, nullable=True)
    item_ids = Column(Text, nullable=False) # JSON array of item IDs
    bbox_snapshot = Column(Text, nullable=True) # JSON snapshot of bbox
    coordinate_space = Column(String, nullable=False)

    step = relationship("ReasoningStep", back_populates="anchors")

class ValidationEvent(Base):
    __tablename__ = "validation_events"
    id = Column(String, primary_key=True)
    reasoning_step_id = Column(String, ForeignKey("reasoning_steps.id"), nullable=False)
    
    validator_name = Column(String, nullable=False)
    verdict = Column(String, nullable=False)
    explanation = Column(Text, nullable=True)
    rule_used = Column(String, nullable=True)
    structured_details = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    step = relationship("ReasoningStep", back_populates="validation_events")

class ConceptMemory(Base):
    __tablename__ = "concept_memory"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    concept_key = Column(String, nullable=False)
    
    encounter_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    struggle_count = Column(Integer, default=0)
    mastery_estimate = Column(Float, default=0.0)
    
    last_encountered = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
