import os
from backend.pipeline.models import VideoJob
from backend.rag.qdrant_store import QdrantRAGStore


class StoryAgent:
    def __init__(self, rag_store: QdrantRAGStore):
        self.rag_store = rag_store
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self._sdk = None
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                self._sdk = "new"
            except ImportError:
                import google.generativeai as genai_legacy  # type: ignore
                genai_legacy.configure(api_key=self.api_key)
                self._legacy = genai_legacy
                self._sdk = "legacy"

    def _generate(self, prompt: str) -> str:
        if self._sdk == "new":
            # Try gemini-2.0-flash first; fall back to gemini-1.5-flash if 429 rate-limited
            for model_name in ["gemini-2.0-flash", "gemini-1.5-flash"]:
                try:
                    response = self._client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                    )
                    if response.text:
                        return response.text
                except Exception as e:
                    print(f"[StoryAgent] Model {model_name} error: {e}")
        elif self._sdk == "legacy":
            model = self._legacy.GenerativeModel("gemini-1.5-flash")
            return model.generate_content(prompt).text
        return ""

    def run(self, job: VideoJob) -> VideoJob:
        job.step = "story_agent"
        job.progress_percentage = 30

        relevant_chunks = self.rag_store.search(job.user_prompt, job.job_id, top_k=3)
        context_text = "\n---\n".join([c["text"] for c in relevant_chunks]) if relevant_chunks else ""
        doc_text = (job.document_text or "")[:3000]
        full_context = (context_text or doc_text or "No specific document context found.")

        prompt = f"""You are an award-winning 3Blue1Brown mathematical animator and computer science educator.
User Topic: "{job.user_prompt}"
Reference Material / Document Excerpts:
{full_context}

Create a deep-dive, step-by-step visual lesson script explaining the mechanics of "{job.user_prompt}".
DO NOT just repeat the topic name on screen. Explain HOW it works step by step!

Structure:
## Scene 1: Intuition & Visual Setup
- Title banner and visual intuition setup.
- Narration explaining the core problem "{job.user_prompt}" solves.

## Scene 2: Deep-Dive Mechanics & Architecture
- Step-by-step visual components (e.g. matrices, feature layers, sliding kernels, function curves, or network nodes).
- Mathematical formulas or algorithmic steps in LaTeX format.
- Narration explaining how data flows through each step.

## Scene 3: Transformation & Output Result
- Show the visual transformation from input to output.
- Narration explaining the final result.

## Scene 4: Key Insights Summary
- 3 key takeaways highlighting why this concept is important.

Output ONLY the structured lesson script."""

        if self.api_key:
            try:
                script = self._generate(prompt)
                if script and len(script) > 50:
                    job.story_script = script
                    return job
            except Exception as e:
                print(f"[StoryAgent] LLM error: {e}. Using educational fallback script.")

        # Educational fallback script template
        topic = (job.user_prompt or "Machine Learning Concept")[:60]
        doc_snippet = (job.document_text or "Convolutional layers process grid data via sliding filters.")[:180].replace("\n", " ")

        job.story_script = f"""## Scene 1: What is {topic}?
- Visual: Large header "{topic}" with animated geometric grid background.
- Narration: Let's understand how {topic} works step-by-step.

## Scene 2: Visual Architecture & Mechanics
- Visual: Input grid matrix receiving a 3x3 sliding filter kernel.
- Equation: Y = f(W \\cdot X + b)
- Text: Excerpt: "{doc_snippet}"
- Narration: Feature extraction transforms high-dimensional input into structured feature maps.

## Scene 3: Feature Transformation
- Visual: Feature map matrix shrinking via Max Pooling down to high-level representations.
- Narration: Downsampling reduces spatial dimensions while preserving spatial invariant patterns.

## Scene 4: Summary
- Visual: 3 key takeaways card for {topic}.
- Narration: That is how {topic} processes data visually."""
        return job
