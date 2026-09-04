import json
import os
import re
from typing import Any, Dict, List

from backend.video_generation.models import TeachingPlan, TeachingStep, VideoJob
from backend.workspace.qdrant_store import QdrantRAGStore
from backend.video_generation.agents.math_validator import validate_math_transition


class TeachingPlannerAgent:
    """Decide what the learner needs before deciding how Manim should draw it."""

    def __init__(self, rag_store: QdrantRAGStore):
        self.rag_store = rag_store
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")

    def run(self, job: VideoJob) -> VideoJob:
        job.step = "teaching_planner"
        job.progress_percentage = 34
        board = job.board_ir
        if not board:
            return job

        query = " ".join(filter(None, [job.user_prompt, board.probable_topic, board.extracted_text[:1200]]))
        chunks = self.rag_store.search(query, job.material_id or job.job_id, top_k=4)
        rag_context = "\n---\n".join(c.get("text", "") for c in chunks if c.get("text"))[:6000]
        graph_context = self._knowledge_graph_context(job.subject_id, board.extracted_text)
        job.metadata["teaching_context"] = {
            "rag_context": rag_context,
            "knowledge_graph_context": graph_context,
            "rag_pages": [c.get("page") for c in chunks],
        }

        prompt = f"""You are the teaching planner for a smart whiteboard.
Do NOT design Manim code. Decide what the learner needs to understand.

EDUCATIONAL RULES:
1. STRICT RULE: "No Unexplained Transformations". For every state transition, you must provide the concept/rule.
2. Assume the learner does not already know why the answer is correct.
3. PREREQUISITE AWARENESS: Analyze the likely prerequisites. If a prerequisite is missing, insert a TeachingStep to explicitly introduce it before solving the main equation.
4. MISCONCEPTION MODELLING: Identify common mistakes and address them explicitly.
5. Explain mathematical identities before applying them.

USER INSTRUCTION:
{job.user_prompt}

BOARD TOPIC:
{board.probable_topic}

BOARD CONTENT:
{board.extracted_text[:5000]}

VISIBLE EQUATIONS:
{json.dumps(board.equations[:10])}

TEXTBOOK/RAG CONTEXT:
{rag_context or 'No grounded textbook context available.'}

Return ONLY JSON matching this format:
{{
  "learning_objective": "one precise objective",
  "existing_knowledge": ["what the board suggests"],
  "prerequisites": ["only truly necessary prerequisites"],
  "misconceptions": ["likely misconception, if any"],
  "steps": [
    {{
      "step_id": "step_1",
      "before_state": "equation or state before",
      "learner_question": "Why...?",
      "concept_or_rule": "The rule being applied",
      "explanation": "Clear explanation",
      "visual_strategy": "How to show this",
      "after_state": "equation or state after",
      "misconception_to_avoid": "optional",
      "estimated_duration": 8.0
    }}
  ],
  "key_concepts": ["important concepts"],
  "estimated_duration_seconds": 35
}}"""

        parsed = self._generate_json(prompt)
        if parsed:
            steps = []
            for s in parsed.get("steps", []):
                # SymPy validation
                before_s = s.get("before_state", "")
                after_s = s.get("after_state", "")
                if before_s and after_s and before_s != after_s:
                    is_valid, msg = validate_math_transition(before_s, after_s)
                    if not is_valid:
                        print(f"[TeachingPlannerAgent] Math validation failed for step {s.get('step_id')}: {msg}")
                        # In the future, we could reject and ask LLM to fix, but for now we log it.

                steps.append(TeachingStep(
                    step_id=str(s.get("step_id", "s1")),
                    before_state=str(s.get("before_state", "")),
                    learner_question=str(s.get("learner_question", "")),
                    concept_or_rule=str(s.get("concept_or_rule", "")),
                    explanation=str(s.get("explanation", "")),
                    visual_strategy=str(s.get("visual_strategy", "")),
                    after_state=str(s.get("after_state", "")),
                    misconception_to_avoid=s.get("misconception_to_avoid"),
                    estimated_duration=float(s.get("estimated_duration", 5.0))
                ))
                
            # Complexity-based duration: 10s base + 8s per step
            dyn_duration = max(20, 10 + len(steps) * 8)
                
            job.teaching_plan = TeachingPlan(
                learning_objective=str(parsed.get("learning_objective", board.learning_intent))[:500],
                existing_knowledge=self._str_list(parsed.get("existing_knowledge"), 6),
                prerequisites=self._str_list(parsed.get("prerequisites"), 6),
                misconceptions=self._str_list(parsed.get("misconceptions"), 6),
                steps=steps,
                key_concepts=self._str_list(parsed.get("key_concepts"), 10),
                estimated_duration_seconds=dyn_duration,
            )
            return job

        objective = board.learning_intent or f"Understand {board.probable_topic}."
        fallback_step = TeachingStep(
            step_id="fallback_1",
            before_state=board.extracted_text[:100],
            learner_question="What does this mean?",
            concept_or_rule="Observe the relationship",
            explanation="Start from the selected whiteboard content.",
            visual_strategy="Highlight terms",
            after_state=board.extracted_text[:100],
            estimated_duration=10.0
        )
        job.teaching_plan = TeachingPlan(
            learning_objective=objective,
            steps=[fallback_step],
            key_concepts=(board.concepts[:8] or [board.probable_topic]),
            estimated_duration_seconds=30,
        )
        return job

    def _generate_json(self, prompt: str) -> Dict[str, Any]:
        text = ""
        # Groq first — fast structured JSON (0.2s vs Gemini's 2-3s for this task)
        if self.groq_api_key:
            try:
                from groq import Groq
                response = Groq(api_key=self.groq_api_key).chat.completions.create(
                    model="qwen/qwen3.8-27b",
                    messages=[{"role": "user", "content": prompt}],
                    timeout=30.0,
                )
                text = response.choices[0].message.content or ""
                if text:
                    print("[TeachingPlannerAgent] Groq JSON generation succeeded")
            except Exception as exc:
                print(f"[TeachingPlannerAgent] Groq error: {exc}")

        # Gemini fallback
        if not text and self.google_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.google_api_key)
                response = genai.GenerativeModel("gemini-3.5-flash-lite").generate_content(prompt)
                text = response.text if response else ""
                if text:
                    print("[TeachingPlannerAgent] Gemini JSON generation succeeded")
            except Exception as exc:
                print(f"[TeachingPlannerAgent] Gemini error: {exc}")

        if not text:
            return {}
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _knowledge_graph_context(self, subject_id: str, text: str) -> str:
        if not subject_id:
            return ""
        try:
            from app.storage.database import SessionLocal, ConceptNode, ConceptEdge
            with SessionLocal() as db:
                nodes = db.query(ConceptNode).filter_by(subject_id=subject_id).all()
                edges = db.query(ConceptEdge).filter_by(subject_id=subject_id).all()
            haystack = text.lower()
            matched = [n for n in nodes if str(n.name).lower() in haystack]
            if not matched:
                matched = nodes[:10]
            names = {str(n.name) for n in matched}
            rels = [
                f"{e.source_name} --{e.relationship_desc or 'related to'}--> {e.target_name}"
                for e in edges
                if e.source_name in names or e.target_name in names
            ][:20]
            node_lines = [f"{n.name}: {getattr(n, 'description', '')}" for n in matched[:12]]
            return "\n".join(node_lines + rels)[:5000]
        except Exception as exc:
            print(f"[TeachingPlannerAgent] Knowledge graph read skipped: {exc}")
            return ""

    @staticmethod
    def _str_list(value: Any, limit: int) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(v).strip()[:300] for v in value if str(v).strip()][:limit]

    @staticmethod
    def _safe_duration(value: Any) -> int:
        try:
            return max(12, min(120, int(value)))
        except Exception:
            return 35
