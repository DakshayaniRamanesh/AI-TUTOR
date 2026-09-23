import json
import uuid
from typing import Optional, List, Dict, Any
from app.storage.database import SessionLocal
from app.storage.models.learning import (
    LearningSession, ProblemAttempt, ReasoningStep, CanvasAnchorRecord, ValidationEvent,
    SessionStatus, AttemptStatus
)
from pydantic import BaseModel
from datetime import datetime

class ReasoningStepDTO(BaseModel):
    id: str
    attempt_id: str
    sequence_number: int
    recognized_text: str
    recognized_latex: Optional[str]
    validation_verdict: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class MemoryRepository:
    def get_or_create_active_session(self, notebook_id: Optional[str] = None, user_id: Optional[str] = None) -> str:
        with SessionLocal() as db:
            session = db.query(LearningSession).filter(
                LearningSession.notebook_id == notebook_id,
                LearningSession.status == SessionStatus.ACTIVE
            ).first()
            if session:
                return session.id
            
            # Create new if none exists
            new_session = LearningSession(
                id=str(uuid.uuid4()),
                notebook_id=notebook_id,
                user_id=user_id,
                status=SessionStatus.ACTIVE
            )
            db.add(new_session)
            db.commit()
            return new_session.id

    def start_learning_session(self, notebook_id: Optional[str] = None, user_id: Optional[str] = None) -> str:
        with SessionLocal() as db:
            session = LearningSession(
                id=str(uuid.uuid4()),
                notebook_id=notebook_id,
                user_id=user_id,
                status=SessionStatus.ACTIVE
            )
            db.add(session)
            db.commit()
            return session.id

    def get_or_create_active_attempt(self, session_id: str, problem_text: Optional[str] = None) -> str:
        with SessionLocal() as db:
            attempt = db.query(ProblemAttempt).filter(
                ProblemAttempt.learning_session_id == session_id,
                ProblemAttempt.status == AttemptStatus.IN_PROGRESS
            ).first()
            if attempt:
                return attempt.id
                
            new_attempt = ProblemAttempt(
                id=str(uuid.uuid4()),
                learning_session_id=session_id,
                problem_text=problem_text,
                status=AttemptStatus.IN_PROGRESS
            )
            db.add(new_attempt)
            db.commit()
            return new_attempt.id

    def start_problem_attempt(self, session_id: str, problem_text: Optional[str] = None) -> str:
        with SessionLocal() as db:
            attempt = ProblemAttempt(
                id=str(uuid.uuid4()),
                learning_session_id=session_id,
                problem_text=problem_text,
                status=AttemptStatus.IN_PROGRESS
            )
            db.add(attempt)
            db.commit()
            return attempt.id

    def append_reasoning_step(
        self, 
        attempt_id: str, 
        recognized_text: str, 
        recognized_latex: Optional[str] = None,
        content_type: Optional[str] = None,
        anchors: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        with SessionLocal() as db:
            # Lock the attempt row to safely calculate the next sequence number (if this was Postgres we'd FOR UPDATE)
            # In SQLite with WAL, transactions are serialized appropriately.
            
            # Find max sequence number
            max_seq = db.query(ReasoningStep).filter(ReasoningStep.attempt_id == attempt_id).count()
            
            step = ReasoningStep(
                id=str(uuid.uuid4()),
                attempt_id=attempt_id,
                sequence_number=max_seq + 1,
                recognized_text=recognized_text,
                recognized_latex=recognized_latex,
                content_type=content_type
            )
            db.add(step)
            
            if anchors:
                for anchor_data in anchors:
                    anchor = CanvasAnchorRecord(
                        id=str(uuid.uuid4()),
                        reasoning_step_id=step.id,
                        board_id=anchor_data.get("board_id", "default"),
                        item_ids=json.dumps(anchor_data.get("item_ids", [])),
                        coordinate_space=anchor_data.get("coordinate_space", "SCENE")
                    )
                    db.add(anchor)
                    
            db.commit()
            return step.id

    def update_step_validation(self, step_id: str, verdict: str, explanation: Optional[str] = None):
        with SessionLocal() as db:
            step = db.query(ReasoningStep).filter(ReasoningStep.id == step_id).first()
            if step:
                step.validation_verdict = verdict
                event = ValidationEvent(
                    id=str(uuid.uuid4()),
                    reasoning_step_id=step_id,
                    validator_name="TriStateValidator",
                    verdict=verdict,
                    explanation=explanation
                )
                db.add(event)
                db.commit()

    def get_recent_steps(self, attempt_id: str, limit: int = 5) -> List[ReasoningStepDTO]:
        with SessionLocal() as db:
            steps = db.query(ReasoningStep).filter(
                ReasoningStep.attempt_id == attempt_id
            ).order_by(ReasoningStep.sequence_number.desc()).limit(limit).all()
            
            # Reverse to chronological
            steps = list(reversed(steps))
            return [ReasoningStepDTO.model_validate(s) for s in steps]
