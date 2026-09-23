from app.services.memory.repositories import MemoryRepository

class ContextBuilder:
    def __init__(self, repository: MemoryRepository):
        self.repo = repository

    def build_context(self, attempt_id: str, max_steps: int = 5) -> str:
        """
        Builds a strict chronological LLM prompt context from the recent reasoning steps.
        """
        steps = self.repo.get_recent_steps(attempt_id, limit=max_steps)
        
        if not steps:
            return "No previous steps recorded."

        context_lines = []
        context_lines.append(f"--- Recent Reasoning History (Last {len(steps)} steps) ---")
        
        for i, step in enumerate(steps, 1):
            verdict = step.validation_verdict or "UNVALIDATED"
            context_lines.append(f"Step {i}:")
            context_lines.append(f"  Input: {step.recognized_text}")
            context_lines.append(f"  Validity: {verdict}")
            
        return "\n".join(context_lines)
