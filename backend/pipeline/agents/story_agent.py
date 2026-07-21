import os
from backend.pipeline.models import VideoJob
from backend.rag.qdrant_store import QdrantRAGStore


class StoryAgent:
    def __init__(self, rag_store: QdrantRAGStore):
        self.rag_store = rag_store
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self._model = None
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
        else:
            self._sdk = None

    def _generate(self, prompt: str) -> str:
        if self._sdk == "new":
            response = self._client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            return response.text
        elif self._sdk == "legacy":
            model = self._legacy.GenerativeModel("gemini-2.0-flash")
            return model.generate_content(prompt).text
        return ""

    def run(self, job: VideoJob) -> VideoJob:
        job.step = "story_agent"
        job.progress_percentage = 30

        relevant_chunks = self.rag_store.search(job.user_prompt, job.job_id, top_k=3)
        context_text = "\n---\n".join([c["text"] for c in relevant_chunks]) if relevant_chunks else ""
        doc_text = (job.document_text or "")[:3000]
        full_context = (context_text or doc_text or "No specific document context found.")

        prompt = f"""You are an expert Manim video storyteller and educator.
User prompt: "{job.user_prompt}"
Document context:
{full_context}

Create a structured narrative script for a Manim animation explainer video.
Structure:
- Scene titles (e.g. ## Scene 1: Introduction)
- Visual elements to create (shapes, text, equations in LaTeX)
- Narration/commentary for each scene
- Keep it concise (3-5 scenes) and visually clear.
Output ONLY the script, no preamble."""

        if self.api_key:
            try:
                job.story_script = self._generate(prompt)
                return job
            except Exception as e:
                print(f"[StoryAgent] LLM error: {e}. Using fallback script.")

        # Fallback script template — dynamically generated from PDF text and prompt
        topic = (job.user_prompt or "Document Concept Analysis")[:60]
        snippet = (job.document_text or "Visual breakdown of main principles.")[:200].replace("\n", " ")
        job.story_script = f"""## Scene 1: Introduction to {topic}
- Visual: Title text "{topic}" fades in with a dark gradient background.
- Narration: Welcome to this visual explanation of {topic}.

## Scene 2: Core Analysis
- Visual: Key excerpts and formula breakdown: "{snippet}".
- Visual: Geometric nodes and connections illustrating principles.
- Narration: Let's inspect the underlying principles extracted from the document.

## Scene 3: Summary & Takeaways
- Visual: Summary card highlighting main takeaways for {topic}.
- Narration: That concludes our visual explanation of {topic}."""
        return job
