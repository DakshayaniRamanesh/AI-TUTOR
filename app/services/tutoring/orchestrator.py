import uuid
from typing import Optional, List, Dict, Any
from shared.contracts.common import StableId
from shared.contracts.reasoning import ValidationVerdict, CanvasAnchor
from shared.contracts.tutoring import (
    TutorFeedback, TutorResponse, TutorMode, FeedbackSeverity, CitationChip
)
from shared.contracts.context import ContextRequest, ContextBundle, RetrievedEvidence
from app.services.memory.repositories import MemoryRepository
from app.services.reasoning.math_parser import parse_math, ParsedMath
from app.services.reasoning.math_validator import validate_transition
from app.services.reasoning.context_builder import ContextBuilder
from backend.latex_video.narration_planner import _LatexToSpeech

class TutorOrchestrator:
    """
    Authoritative TutorOrchestrator for Kestrel.
    Unifies Canvas Events, Handwriting, Subject Brain RAG,
    SymPy Math Reasoning, Citations, and Voice Speech Translation.
    """

    def __init__(self, repository: MemoryRepository, context_builder: ContextBuilder):
        self.repo = repository
        self.context_builder = context_builder

    def process_request(self, request: ContextRequest) -> TutorResponse:
        """
        Processes a unified ContextRequest through ContextBuilder,
        mathematical reasoning, subject evidence retrieval, and pedagogical policy.
        """
        # 1. Build unified context
        bundle: ContextBundle = self.context_builder.build_context(request)
        mode = getattr(request, "tutor_mode", TutorMode.CHECK_STEP)
        if isinstance(mode, str):
            try:
                mode = TutorMode(mode)
            except ValueError:
                mode = TutorMode.CHECK_STEP

        current_text = bundle.current_work_text or request.user_query or ""
        anchors = [bundle.canvas_anchor] if bundle.canvas_anchor else []

        # Convert retrieved evidence to citation chips
        citation_chips = []
        for ev in bundle.retrieved_evidence:
            citation_chips.append(CitationChip(
                chunk_id=ev.chunk_id,
                material_id=ev.material_id,
                document_title=ev.document_title,
                chapter=ev.chapter,
                section=ev.section,
                page_number=ev.page_number,
                snippet=ev.snippet
            ))

        # 2. Dispatch according to TutorMode
        if mode in (TutorMode.CHECK_STEP, TutorMode.AUTO_CHECK):
            response = self._handle_check_step(request, bundle, current_text, anchors, citation_chips)
        elif mode in [TutorMode.EXPLAIN, TutorMode.ASK]:
            response = self._handle_explain_or_ask(request, bundle, current_text, anchors, citation_chips, mode)
        elif mode == TutorMode.HINT:
            response = self._handle_hint(request, bundle, current_text, anchors, citation_chips)
        else:
            response = self._handle_check_step(request, bundle, current_text, anchors, citation_chips)

        # 3. Generate speakable narration text (convert LaTeX math to natural spoken English)
        try:
            spoken = _LatexToSpeech.translate(response.feedback_text)
            response.spoken_text = spoken
        except Exception:
            response.spoken_text = response.feedback_text

        return response

    def _handle_check_step(
        self,
        request: ContextRequest,
        bundle: ContextBundle,
        current_text: str,
        anchors: List[CanvasAnchor],
        citations: List[CitationChip]
    ) -> TutorResponse:
        current_parsed = parse_math(current_text)

        if not current_parsed.is_valid:
            return TutorResponse(
                request_id=request.request_id,
                tutor_mode=TutorMode.CHECK_STEP,
                verdict=ValidationVerdict.UNKNOWN,
                feedback_text="I couldn't quite read that math. Could you rewrite it clearer?",
                socratic_hints=["Make sure the equal sign and variables are clearly written."],
                severity=FeedbackSeverity.INFO,
                anchors=anchors,
                citations=[],
                source_mode="OFFLINE_LOCAL"
            )

        verdict = ValidationVerdict.UNKNOWN
        explanation = "First step captured. Write the next step and I can verify the transition."
        socratic_hints = ["What should we do next?"]
        severity = FeedbackSeverity.INFO

        # Find previous step in attempt explicitly
        previous_step = None
        if request.attempt_id:
            # Compare against the latest non-invalid step. This lets a corrected step branch from
            # the last trustworthy/captured line instead of from the mistake it is correcting.
            recent_steps = self.repo.get_recent_steps(request.attempt_id, limit=20)
            previous_step = next(
                (s for s in reversed(recent_steps) if s.validation_verdict != ValidationVerdict.INVALID.value),
                None,
            )

        if previous_step and previous_step.recognized_text:
            prev_parsed = parse_math(previous_step.recognized_text)
            validation_res = validate_transition(prev_parsed, current_parsed, step_id=previous_step.id)
            verdict = validation_res.verdict
            explanation = validation_res.explanation or "Transition validated."

            if verdict == ValidationVerdict.INVALID:
                severity = FeedbackSeverity.WARNING
                socratic_hints = ["Check your algebra operations.", "Did you apply the same operation to both sides?"]
                # Check for distribution error hint
                if "distribute" in explanation.lower():
                    socratic_hints = ["Remember to multiply every term inside the parentheses."]

                # Record learner observation for verified repeated errors
                if request.subject_id and "distribute" in explanation.lower():
                    user_id = getattr(request, "user_id", None)
                    if not user_id and request.session_id:
                        user_id = self.repo.get_user_id_for_session(request.session_id)
                    if not user_id and request.attempt_id:
                        user_id = self.repo.get_user_id_for_attempt(request.attempt_id)

                    self.repo.record_learner_observation(
                        user_id=user_id,
                        observation_type="DISTRIBUTIVE_PROPERTY_ERROR",
                        description="Student missed distributing factor across bracket term.",
                        attempt_id=request.attempt_id,
                        step_id=None,
                        subject_id=request.subject_id
                    )
            elif verdict == ValidationVerdict.UNKNOWN:
                explanation = f"I see {current_text}, but I couldn't verify this transition automatically."
                socratic_hints = ["Can you break that down into a smaller step?"]
                severity = FeedbackSeverity.INFO
            else:
                if explanation == "Transition validated.":
                    explanation = f"Correct! {current_text} is a valid step."
                socratic_hints = ["What is the next step to isolate the variable?"]
                severity = FeedbackSeverity.INFO

        # Persist to database if attempt_id exists
        if request.attempt_id:
            step_id = self.repo.append_reasoning_step(
                attempt_id=request.attempt_id,
                recognized_text=current_text,
                recognized_latex=current_parsed.latex if hasattr(current_parsed, 'latex') else None,
                content_type="EQUATION" if current_parsed.is_equation else "EXPRESSION",
                group_id=request.semantic_block_id,
                group_revision=request.group_revision,
                previous_step_id=previous_step.id if previous_step else None
            )
            self.repo.update_step_validation(step_id, verdict.value, explanation)

        explanation = f"I read: {current_text}\n{explanation}"

        return TutorResponse(
            request_id=request.request_id,
            subject_id=request.subject_id,
            notebook_id=request.notebook_id,
            session_id=request.session_id,
            attempt_id=request.attempt_id,
            canvas_revision=request.canvas_revision,
            semantic_block_id=request.semantic_block_id,
            tutor_mode=TutorMode.AUTO_CHECK if str(request.tutor_mode) == TutorMode.AUTO_CHECK.value else TutorMode.CHECK_STEP,
            verdict=verdict,
            feedback_text=explanation,
            socratic_hints=socratic_hints,
            severity=severity,
            anchors=anchors,
            citations=citations,
            source_mode="OFFLINE_LOCAL"
        )

    def _handle_explain_or_ask(
        self,
        request: ContextRequest,
        bundle: ContextBundle,
        current_text: str,
        anchors: List[CanvasAnchor],
        citations: List[CitationChip],
        mode: TutorMode
    ) -> TutorResponse:
        # Check if subject evidence was retrieved
        feedback_lines = []
        source_mode = "OFFLINE_LOCAL"

        if bundle.retrieved_evidence:
            source_mode = "HYBRID_RAG"
            evidence_text = "\n\n".join(
                f"[{index}] {ev.document_title or 'Subject material'}"
                f"{f', page {ev.page_number}' if ev.page_number else ''}: {ev.snippet}"
                for index, ev in enumerate(bundle.retrieved_evidence, 1)
            )
            try:
                from shared.ai_client import ai_client
                answer = ai_client.generate_content(
                    f"Student question: {current_text}\n\nEvidence:\n{evidence_text}\n\n"
                    "Explain clearly and step-by-step using only the evidence. Reference sources as [1], [2]. "
                    "If the evidence is insufficient, say exactly what is missing.",
                    system_instruction="You are Kestrel, a concise Socratic tutor grounded in the learner's subject materials.",
                    temperature=0.0,
                ).strip()
                if answer:
                    feedback_lines.append(answer)
            except Exception:
                best_ev = bundle.retrieved_evidence[0]
                feedback_lines.append(
                    f"Based on {best_ev.document_title or 'Subject Notes'}: {best_ev.snippet[:500]}"
                )
        else:
            # Fallback to local mathematical analysis or general explanation
            parsed = parse_math(current_text)
            if parsed.is_valid:
                if parsed.is_equation:
                    feedback_lines.append(f"For the equation {current_text}:")
                    feedback_lines.append("To solve linear equations, isolate the variable term by performing inverse operations equally on both sides.")
                else:
                    feedback_lines.append(f"Expression: {current_text}")
            else:
                feedback_lines.append(f"Question: {current_text}")
                feedback_lines.append("Here is an explanation based on core principles. (No uploaded subject material matched this specific query.)")

        # Graph concept relations
        if bundle.graph_context and bundle.graph_context.neighbor_concepts:
            rel_names = [f"{n.display_name} ({n.relation})" for n in bundle.graph_context.neighbor_concepts[:3]]
            feedback_lines.append(f"\nRelated Subject Concepts: {', '.join(rel_names)}")

        return TutorResponse(
            request_id=request.request_id,
            subject_id=request.subject_id,
            notebook_id=request.notebook_id,
            session_id=request.session_id,
            attempt_id=request.attempt_id,
            canvas_revision=request.canvas_revision,
            semantic_block_id=request.semantic_block_id,
            tutor_mode=mode,
            verdict=ValidationVerdict.VALID if bundle.retrieved_evidence else None,
            feedback_text="\n".join(feedback_lines),
            socratic_hints=["Would you like a step-by-step example?", "Can you apply this rule to your equation?"],
            severity=FeedbackSeverity.INFO,
            anchors=anchors,
            citations=citations,
            source_mode=source_mode
        )

    def _handle_hint(
        self,
        request: ContextRequest,
        bundle: ContextBundle,
        current_text: str,
        anchors: List[CanvasAnchor],
        citations: List[CitationChip]
    ) -> TutorResponse:
        parsed = parse_math(current_text)
        hint_text = "Look closely at the operations between terms. What is the inverse operation?"
        if parsed.is_equation:
            hint_text = "To isolate the variable, perform the opposite operation on both sides of the equation."

        return TutorResponse(
            request_id=request.request_id,
            subject_id=request.subject_id,
            notebook_id=request.notebook_id,
            session_id=request.session_id,
            attempt_id=request.attempt_id,
            canvas_revision=request.canvas_revision,
            semantic_block_id=request.semantic_block_id,
            tutor_mode=TutorMode.HINT,
            verdict=None,
            feedback_text=hint_text,
            socratic_hints=["What happens if you subtract or divide both sides?", "Check the signs carefully."],
            severity=FeedbackSeverity.INFO,
            anchors=anchors,
            citations=citations,
            source_mode="OFFLINE_LOCAL"
        )

    def process_student_input(
        self, 
        attempt_id: str, 
        recognized_text: str, 
        group_id: Optional[str] = None, 
        group_revision: int = 0, 
        anchors: Optional[List[dict]] = None,
        subject_id: Optional[str] = None,
        notebook_id: Optional[str] = None,
        mode: str = "CHECK_STEP"
    ) -> TutorFeedback:
        """
        Backwards-compatibility bridge that wraps parameters into a ContextRequest
        and delegates to the unified process_request pipeline.
        """
        req = ContextRequest(
            request_id=str(uuid.uuid4()),
            subject_id=subject_id,
            notebook_id=notebook_id,
            attempt_id=attempt_id,
            user_query=recognized_text,
            tutor_mode=mode
        )
        response = self.process_request(req)

        return TutorFeedback(
            feedback_text=response.feedback_text,
            socratic_hints=response.socratic_hints,
            severity=response.severity,
            anchors=response.anchors,
            citations=response.citations,
            spoken_text=response.spoken_text,
            verdict=response.verdict
        )
