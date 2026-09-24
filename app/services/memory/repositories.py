import json
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.storage.database import SessionLocal, User
from app.storage.models.learning import (
    LearningSession, ProblemAttempt, ReasoningStep, CanvasAnchorRecord, ValidationEvent,
    LearnerObservation, SessionStatus, AttemptStatus
)

class ReasoningStepDTO(BaseModel):
    id: str
    attempt_id: str
    sequence_number: int
    recognized_text: str
    recognized_latex: Optional[str] = None
    validation_verdict: Optional[str] = None
    content_type: Optional[str] = None
    group_id: Optional[str] = None
    group_revision: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class LearnerObservationDTO(BaseModel):
    id: str
    user_id: str
    subject_id: Optional[str] = None
    observation_type: str
    description: str
    supporting_attempt_ids: List[str] = []
    supporting_step_ids: List[str] = []
    occurrence_count: int = 1
    status: str = "ACTIVE"
    confidence: float = 1.0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

class MemoryRepository:
    def __init__(self, session_factory=None):
        self.Session = session_factory or SessionLocal

    def get_or_create_active_session(
        self, 
        notebook_id: Optional[str] = None, 
        user_id: Optional[str] = None,
        subject_id: Optional[str] = None
    ) -> str:
        with self.Session() as db:
            query = db.query(LearningSession).filter(
                LearningSession.notebook_id == notebook_id,
                LearningSession.status == SessionStatus.ACTIVE
            )
            if subject_id:
                query = query.filter(LearningSession.subject_id == subject_id)
            session = query.first()
            if session:
                return session.id
            
            # Create new if none exists
            new_session = LearningSession(
                id=str(uuid.uuid4()),
                notebook_id=notebook_id,
                subject_id=subject_id,
                user_id=user_id,
                status=SessionStatus.ACTIVE
            )
            db.add(new_session)
            db.commit()
            return new_session.id

    def start_learning_session(
        self, 
        notebook_id: Optional[str] = None, 
        user_id: Optional[str] = None,
        subject_id: Optional[str] = None
    ) -> str:
        with self.Session() as db:
            session = LearningSession(
                id=str(uuid.uuid4()),
                notebook_id=notebook_id,
                subject_id=subject_id,
                user_id=user_id,
                status=SessionStatus.ACTIVE
            )
            db.add(session)
            db.commit()
            return session.id

    def get_or_create_active_attempt(self, session_id: str, problem_text: Optional[str] = None) -> str:
        with self.Session() as db:
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
        with self.Session() as db:
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
        anchors: Optional[List[Dict[str, Any]]] = None,
        group_id: Optional[str] = None,
        group_revision: Optional[int] = None,
        previous_step_id: Optional[str] = None,
        replaces_step_id: Optional[str] = None
    ) -> str:
        with self.Session() as db:
            if group_id is not None:
                existing = db.query(ReasoningStep).filter(
                    ReasoningStep.attempt_id == attempt_id,
                    ReasoningStep.group_id == group_id
                ).first()
                if existing:
                    if group_revision is not None and (existing.group_revision is None or group_revision > existing.group_revision):
                        existing.recognized_text = recognized_text
                        existing.recognized_latex = recognized_latex
                        existing.content_type = content_type
                        existing.group_revision = group_revision
                        existing.validation_verdict = None
                        if previous_step_id: existing.previous_step_id = previous_step_id
                        if replaces_step_id: existing.replaces_step_id = replaces_step_id
                        db.commit()
                        return existing.id
                    else:
                        return existing.id

            max_seq = db.query(ReasoningStep).filter(ReasoningStep.attempt_id == attempt_id).count()
            
            step = ReasoningStep(
                id=str(uuid.uuid4()),
                attempt_id=attempt_id,
                sequence_number=max_seq + 1,
                recognized_text=recognized_text,
                recognized_latex=recognized_latex,
                content_type=content_type,
                group_id=group_id,
                group_revision=group_revision,
                previous_step_id=previous_step_id,
                replaces_step_id=replaces_step_id
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
        with self.Session() as db:
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
        with self.Session() as db:
            steps = db.query(ReasoningStep).filter(
                ReasoningStep.attempt_id == attempt_id
            ).order_by(ReasoningStep.sequence_number.desc()).limit(limit).all()
            
            # Reverse to chronological
            steps = list(reversed(steps))
            return [ReasoningStepDTO.model_validate(s) for s in steps]

    def get_last_step(self, attempt_id: str) -> Optional[ReasoningStepDTO]:
        with self.Session() as db:
            step = db.query(ReasoningStep).filter(
                ReasoningStep.attempt_id == attempt_id
            ).order_by(ReasoningStep.sequence_number.desc()).first()
            if step:
                return ReasoningStepDTO.model_validate(step)
            return None

    def get_last_valid_step(self, attempt_id: str) -> Optional[ReasoningStepDTO]:
        with self.Session() as db:
            step = db.query(ReasoningStep).filter(
                ReasoningStep.attempt_id == attempt_id,
                ReasoningStep.validation_verdict == "VALID"
            ).order_by(ReasoningStep.sequence_number.desc()).first()
            if step:
                return ReasoningStepDTO.model_validate(step)
            return None

    def get_user_id_for_session(self, session_id: str) -> Optional[str]:
        with self.Session() as db:
            session = db.query(LearningSession).filter(LearningSession.id == session_id).first()
            if session:
                return session.user_id
            return None

    def get_user_id_for_attempt(self, attempt_id: str) -> Optional[str]:
        with self.Session() as db:
            att = db.query(ProblemAttempt).filter(ProblemAttempt.id == attempt_id).first()
            if att and att.session:
                return att.session.user_id
            return None

    def record_learner_observation(
        self,
        user_id: Optional[str],
        observation_type: str,
        description: str,
        attempt_id: Optional[str] = None,
        step_id: Optional[str] = None,
        subject_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Record an evidence-backed observation. If an active observation of the same
        type already exists for this user/subject, increment occurrence_count and attach evidence.
        """
        with self.Session() as db:
            if attempt_id and not user_id:
                att = db.query(ProblemAttempt).filter(ProblemAttempt.id == attempt_id).first()
                if att and att.session and att.session.user_id:
                    user_id = att.session.user_id

            if not user_id:
                # Resolve identities via active session/attempt rather than auto-creating default users
                print("[MemoryRepository] Warning: No user_id resolved. Cannot record learner observation.")
                return None

            # Ensure user exists for foreign key constraint
            user_row = db.query(User).filter(User.id == user_id).first()
            if not user_row:
                user_row = User(id=user_id, username=user_id)
                db.add(user_row)
                db.flush()

            query = db.query(LearnerObservation).filter(
                LearnerObservation.user_id == user_id,
                LearnerObservation.observation_type == observation_type,
                LearnerObservation.status == "ACTIVE"
            )
            if subject_id:
                query = query.filter(LearnerObservation.subject_id == subject_id)
            existing = query.first()

            if existing:
                try: attempts = json.loads(existing.supporting_attempt_ids_json or "[]")
                except: attempts = []
                try: steps = json.loads(existing.supporting_step_ids_json or "[]")
                except: steps = []

                if attempt_id and attempt_id not in attempts:
                    attempts.append(attempt_id)
                if step_id and step_id not in steps:
                    steps.append(step_id)

                existing.supporting_attempt_ids_json = json.dumps(attempts)
                existing.supporting_step_ids_json = json.dumps(steps)
                existing.occurrence_count += 1
                existing.last_seen = datetime.utcnow()
                db.commit()
                return existing.id
            else:
                attempts = [attempt_id] if attempt_id else []
                steps = [step_id] if step_id else []
                obs = LearnerObservation(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    subject_id=subject_id,
                    observation_type=observation_type,
                    description=description,
                    supporting_attempt_ids_json=json.dumps(attempts),
                    supporting_step_ids_json=json.dumps(steps),
                    occurrence_count=1,
                    status="ACTIVE",
                    confidence=1.0,
                    first_seen=datetime.utcnow(),
                    last_seen=datetime.utcnow()
                )
                db.add(obs)
                db.commit()
                return obs.id

    def get_learner_observations(
        self,
        user_id: str,
        subject_id: Optional[str] = None,
        status: str = "ACTIVE"
    ) -> List[LearnerObservationDTO]:
        with self.Session() as db:
            query = db.query(LearnerObservation).filter(
                LearnerObservation.user_id == user_id,
                LearnerObservation.status == status
            )
            if subject_id:
                query = query.filter(LearnerObservation.subject_id == subject_id)
            results = query.all()

            dtos = []
            for r in results:
                try: attempts = json.loads(r.supporting_attempt_ids_json or "[]")
                except: attempts = []
                try: steps = json.loads(r.supporting_step_ids_json or "[]")
                except: steps = []

                dtos.append(LearnerObservationDTO(
                    id=r.id,
                    user_id=r.user_id,
                    subject_id=r.subject_id,
                    observation_type=r.observation_type,
                    description=r.description,
                    supporting_attempt_ids=attempts,
                    supporting_step_ids=steps,
                    occurrence_count=r.occurrence_count,
                    status=r.status,
                    confidence=r.confidence,
                    first_seen=r.first_seen,
                    last_seen=r.last_seen
                ))
            return dtos
