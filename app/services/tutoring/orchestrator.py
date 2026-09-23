from typing import Optional, Union, List
from shared.contracts.reasoning import ValidationVerdict
from shared.contracts.tutoring import TutorFeedback, FeedbackSeverity
from app.services.memory.repositories import MemoryRepository
from app.services.reasoning.math_parser import parse_math, ParsedMath
from app.services.reasoning.math_validator import validate_transition
from app.services.reasoning.context_builder import ContextBuilder
import uuid

class TutorOrchestrator:
    def __init__(self, repository: MemoryRepository, context_builder: ContextBuilder):
        self.repo = repository
        self.context_builder = context_builder

    def process_student_input(self, attempt_id: str, recognized_text: str, anchors: Optional[List[dict]] = None) -> TutorFeedback:
        """
        Coordinates parsing, validation, memory storage, and feedback generation.
        """
        # 1. Parse student input safely
        current_parsed = parse_math(recognized_text)
        
        # 2. Get previous step from history for validation
        recent_steps = self.repo.get_recent_steps(attempt_id, limit=1)
        
        verdict = ValidationVerdict.VALID
        explanation = "First step looks good."
        
        if recent_steps:
            last_step = recent_steps[-1]
            last_parsed = parse_math(last_step.recognized_text)
            
            # 3. Rigorous validation
            validation_result = validate_transition(last_parsed, current_parsed, step_id=last_step.id)
            verdict = validation_result.verdict
            explanation = validation_result.explanation or "Transition validated."

        # 4. Store current step in database
        step_id = self.repo.append_reasoning_step(
            attempt_id=attempt_id,
            recognized_text=recognized_text,
            content_type="EQUATION" if current_parsed.is_equation else "EXPRESSION",
            anchors=anchors
        )
        
        # 5. Store validation result in database
        self.repo.update_step_validation(step_id, verdict.value, explanation)

        # 6. Generate Feedback
        # In a full integration, we'd call an LLM here with self.context_builder.build_context(attempt_id)
        # For this milestone, we return deterministic pedagogical feedback based on the tri-state validator.
        
        if not current_parsed.is_valid:
             return TutorFeedback(
                feedback_text="I couldn't quite read that math. Could you rewrite it clearer?",
                socratic_hints=[],
                severity=FeedbackSeverity.WARNING,
                anchors=[]
             )

        if verdict == ValidationVerdict.VALID:
            return TutorFeedback(
                feedback_text=f"Correct! {recognized_text} is a valid step.",
                socratic_hints=["What should we do next?"],
                severity=FeedbackSeverity.INFO,
                anchors=[]
            )
        elif verdict == ValidationVerdict.INVALID:
            return TutorFeedback(
                feedback_text=f"Wait, {recognized_text} doesn't mathematically follow from the previous step.",
                socratic_hints=["Check your algebra operations.", "Did you apply the same operation to both sides?"],
                severity=FeedbackSeverity.WARNING,
                anchors=[]
            )
        else:
            return TutorFeedback(
                feedback_text=f"I see {recognized_text}, but I'm not entirely sure how we got there.",
                socratic_hints=["Can you break that down into a smaller step?"],
                severity=FeedbackSeverity.INFO,
                anchors=[]
            )
