"""
ValidatorAgent — Structural lesson script validation.

Improved from v1 (which only checked len > 20) to perform:
  1. Scene count check (at least 2 Scene sections)
  2. Topic relevance check (script mentions user topic, not generic)
  3. Visual element check (at least one Visual: line)
  4. RAG grounding check (if document context was provided)
  5. Structured revision feedback stored in job.metadata["revision_reason"]
"""

from backend.video_generation.models import VideoJob


class ValidatorAgent:
    MAX_REVISIONS = 2

    def run(self, job: VideoJob) -> VideoJob:
        job.step = "validator_agent"
        job.friendly_step = "Reviewing lesson structure..."
        job.progress_percentage = 45

        script = job.story_script or ""

        # Guard: already hit max revisions → force through
        if job.revision_count >= self.MAX_REVISIONS:
            job.needs_revision = False
            print(f"[ValidatorAgent] Max revisions ({self.MAX_REVISIONS}) reached — forcing through.")
            return job

        failures = []

        # ── Check 1: Minimum length ───────────────────────────────────────────
        if len(script.strip()) < 100:
            failures.append("Script is too short (under 100 characters). Generate a full 4-scene lesson.")

        # ── Check 2: Scene structure ──────────────────────────────────────────
        import re
        scene_markers = re.findall(r'(?:##\s*Scene\s*\d+|Scene\s*\d+:)', script, re.IGNORECASE)
        if len(scene_markers) < 2:
            failures.append(
                f"Script only has {len(scene_markers)} scene section(s). Must have at least 2 '## Scene N:' sections."
            )

        # ── Check 3: Visual element descriptions ─────────────────────────────
        has_visual = bool(re.search(r'\bVisual\s*:', script, re.IGNORECASE))
        if not has_visual:
            failures.append(
                "Script has no 'Visual:' lines. Every scene must specify a concrete visual element description."
            )

        # ── Check 4: Topic relevance ──────────────────────────────────────────
        topic_words = [w.lower() for w in (job.user_prompt or "").split() if len(w) > 3]
        topic_found = any(word in script.lower() for word in topic_words[:5])
        if topic_words and not topic_found:
            failures.append(
                f"Script doesn't appear to mention the topic '{job.user_prompt}'. Make the lesson specific to this topic."
            )

        # ── Check 5: RAG grounding (if document was provided) ─────────────────
        if job.document_text and len(job.document_text) > 100:
            # Check that at least 5 consecutive chars from the document appear in the script
            doc_words = [w.lower() for w in re.findall(r'\b\w{5,}\b', job.document_text)][:50]
            doc_grounded = sum(1 for w in doc_words if w in script.lower())
            if doc_grounded < 3:
                failures.append(
                    "Script does not use the uploaded document's content. "
                    "Reference specific terms, definitions, or concepts from the student's material."
                )

        if failures:
            job.needs_revision = True
            job.revision_count += 1
            revision_reason = " | ".join(failures)
            job.metadata["revision_reason"] = revision_reason
            print(f"[ValidatorAgent] Script needs revision (attempt {job.revision_count}): {revision_reason[:150]}")
        else:
            job.needs_revision = False
            job.metadata.pop("revision_reason", None)
            print(f"[ValidatorAgent] Script passed all checks (scenes: {len(scene_markers)}, has_visual: {has_visual})")

        return job
