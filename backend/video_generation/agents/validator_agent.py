import re
from backend.video_generation.models import ValidationResult, VideoJob


class ValidatorAgent:
    """
    Lightweight semantic/story-structure validator for the legacy StoryAgent path.

    This intentionally remains deterministic and cheap. Whiteboard SceneSpecs are
    validated structurally by StoryboardPlannerAgent and then by the Manim CI
    harness after deterministic compilation.
    """

    def run(self, job: VideoJob) -> VideoJob:
        job.step = "validator_agent"
        job.progress_percentage = 45

        script = (job.story_script or "").strip()
        failures = []

        if len(script) < 180:
            failures.append("Lesson script is too short to support a useful visual explanation.")

        scene_count = len(re.findall(r"(?im)^\s*##?\s*scene\s+\d+", script))
        if scene_count < 2:
            failures.append("Lesson should contain at least two purposeful scenes.")

        lower = script.lower()
        visual_terms = ("visual", "diagram", "graph", "matrix", "vector", "arrow", "shape", "animate", "transform")
        if not any(term in lower for term in visual_terms):
            failures.append("Lesson does not specify a meaningful visual representation.")

        prompt_terms = [
            t for t in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", (job.user_prompt or "").lower())
            if t not in {"this", "that", "explain", "about", "please", "selected", "document"}
        ]
        if prompt_terms and not any(term in lower for term in prompt_terms[:8]):
            failures.append("Lesson appears disconnected from the requested topic.")

        # Catch the known generic CNN fallback accidentally being used for unrelated topics.
        cnn_markers = {"feature map", "3x3 sliding filter", "max pooling"}
        if any(marker in lower for marker in cnn_markers):
            prompt_lower = (job.user_prompt or "").lower()
            cnn_prompt = any(k in prompt_lower for k in ("cnn", "convolution", "neural", "feature map", "pooling"))
            if not cnn_prompt:
                failures.append("Generic CNN fallback content does not match the requested topic.")

        # If SceneSpecs exist, perform Pedagogical Validation
        if job.scene_specs:
            unexplained_transformations = 0
            for scene in job.scene_specs:
                for action in scene.actions:
                    if action.get("type") == "transform" and not action.get("reason"):
                        unexplained_transformations += 1
                        
            if unexplained_transformations > 0:
                failures.append(f"Pedagogical Error: Found {unexplained_transformations} unexplained transformations without a 'reason'.")
                
        passed = not failures
        job.validation_results.append(ValidationResult(
            stage="story",
            passed=passed,
            message="; ".join(failures) if failures else "Pedagogical validation passed.",
        ))

        job.needs_revision = not passed
        if job.needs_revision:
            job.revision_count += 1
            if job.revision_count >= 2:
                # Avoid an unbounded LLM loop
                job.needs_revision = False
        return job
