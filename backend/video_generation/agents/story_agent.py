"""
StoryAgent — Topic-aware, RAG-grounded lesson script generator.

Improvements over v1:
  - Topic classifier: identifies subject (math/physics/cs/chemistry/biology/statistics/general)
  - Subject-specific visual strategy injected into prompt
  - RAG grounding enforced: LLM is explicitly instructed to use the document
  - Structured script output with clear Scene sections and Visual hints
  - Records model_used and topic_subject on the job for traceability
  - Migrated to suppress FutureWarning from deprecated google.generativeai
"""

import os
import warnings
from backend.video_generation.models import VideoJob

# ── Visual strategy map: subject → Manim-safe visual strategies ──────────────
SUBJECT_VISUAL_STRATEGIES = {
    "math": (
        "equations displayed with Text(), graphs using Axes/NumberPlane, "
        "geometric proofs with Polygon/Line/Dot, transformation animations with Transform(). "
        "Show each step of a derivation one at a time. Do NOT describe LaTeX — use plain ASCII math like x^2, d/dx."
    ),
    "physics": (
        "vector arrows with Arrow(), labeled force/motion diagrams with Text labels, "
        "motion curves plotted on Axes, body diagrams drawn with Rectangle+Arrow. "
        "Show before/after states. Use slow animations for dynamics."
    ),
    "cs": (
        "flowchart boxes (RoundedRectangle) connected with Arrow(), "
        "tree/graph nodes as Dot+Line, algorithm steps as numbered Text boxes, "
        "data structure states with VGroup grids. Show state transitions step by step."
    ),
    "chemistry": (
        "element circles (Circle+Text label), bond lines (Line), "
        "reaction arrow diagrams (left molecule → Arrow → right molecule), "
        "labeled component groups. Show structural formulas as connected dots and lines."
    ),
    "biology": (
        "labeled process boxes (RoundedRectangle+Text), cycle diagrams with curved Arrow, "
        "cell/organism components as nested shapes, annotated diagram steps. "
        "Show process flow with directional arrows."
    ),
    "statistics": (
        "bar charts (BarChart), probability curves plotted on Axes, "
        "data transformation steps (VGroup tables), distribution shapes. "
        "Show concrete numbers. Animate transitions between distributions."
    ),
    "general": (
        "concept overview boxes (RoundedRectangle), progressive text reveal with FadeIn, "
        "comparison panels (side-by-side with VS divider), "
        "process flow arrows. Keep visuals clean and uncluttered."
    ),
}

# ── Subject classification signals ───────────────────────────────────────────
_SUBJECT_SIGNALS = {
    "math": ["derivative", "integral", "calculus", "algebra", "geometry", "theorem",
             "proof", "equation", "matrix", "vector", "eigenvalue", "polynomial",
             "trigonometry", "logarithm", "limit", "function", "graph", "formula"],
    "physics": ["force", "energy", "velocity", "acceleration", "momentum", "gravity",
                "electromagnetism", "quantum", "wave", "thermodynamics", "optics",
                "circuit", "resistor", "newton", "coulomb", "motion", "field"],
    "cs": ["algorithm", "data structure", "tree", "graph", "sorting", "binary",
           "neural network", "machine learning", "recursion", "complexity", "big-o",
           "database", "sql", "api", "protocol", "compiler", "operating system",
           "convolution", "attention", "transformer", "gradient"],
    "chemistry": ["reaction", "molecule", "atom", "bond", "element", "compound",
                  "acid", "base", "oxidation", "reduction", "periodic table",
                  "covalent", "ionic", "electron", "protein", "enzyme"],
    "biology": ["cell", "dna", "rna", "evolution", "photosynthesis", "mitosis",
                "meiosis", "neuron", "anatomy", "ecosystem", "genetics", "species",
                "chromosome", "membrane", "organelle", "respiration"],
    "statistics": ["probability", "distribution", "mean", "variance", "regression",
                   "hypothesis", "p-value", "confidence interval", "bayesian",
                   "correlation", "sample", "population", "standard deviation"],
}


def classify_subject(user_prompt: str, story_script: str = "") -> str:
    """Classify the topic into a subject category based on keyword signals."""
    text = (user_prompt + " " + story_script).lower()
    scores = {subject: 0 for subject in _SUBJECT_SIGNALS}
    for subject, signals in _SUBJECT_SIGNALS.items():
        for s in signals:
            if s in text:
                scores[subject] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "general"


class StoryAgent:
    def __init__(self, rag_store):
        self.rag_store = rag_store
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.google_api_key = os.getenv("GOOGLE_API_KEY")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            try:
                import google.generativeai as genai
                if self.google_api_key:
                    genai.configure(api_key=self.google_api_key)
                    # Try preferred model, fall back to stable alternative
                    for model_name in ["gemini-1.5-flash", "gemini-1.5-flash-latest"]:
                        try:
                            self.gemini_model = genai.GenerativeModel(model_name)
                            self._gemini_model_name = model_name
                            break
                        except Exception:
                            self.gemini_model = None
                            self._gemini_model_name = ""
                else:
                    self.gemini_model = None
                    self._gemini_model_name = ""
            except ImportError:
                self.gemini_model = None
                self._gemini_model_name = ""

        self._groq_client = None
        if self.groq_api_key:
            try:
                from groq import Groq
                self._groq_client = Groq(api_key=self.groq_api_key)
            except ImportError:
                pass

    def _generate(self, prompt: str) -> tuple[str, str]:
        """Returns (generated_text, model_name_used)."""
        if self.gemini_model:
            try:
                response = self.gemini_model.generate_content(prompt)
                if response and response.text:
                    return response.text, self._gemini_model_name
            except Exception as e:
                print(f"[StoryAgent] Gemini error: {e}. Falling back to Groq...")

        if self._groq_client:
            try:
                response = self._groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=2048,
                )
                if response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content, "groq/llama-3.3-70b-versatile"
            except Exception as e:
                print(f"[StoryAgent] Groq error: {e}")
        return "", ""

    def run(self, job: VideoJob) -> VideoJob:
        job.step = "story_agent"
        job.friendly_step = "Designing visual explanation..."
        job.progress_percentage = 30

        # ── 1. Classify topic subject ─────────────────────────────────────────
        subject = classify_subject(job.user_prompt)
        job.topic_subject = subject
        visual_strategy = SUBJECT_VISUAL_STRATEGIES.get(subject, SUBJECT_VISUAL_STRATEGIES["general"])
        print(f"[StoryAgent] Topic subject classified as: '{subject}'")

        # ── 2. Retrieve RAG context ───────────────────────────────────────────
        relevant_chunks = []
        try:
            relevant_chunks = self.rag_store.search(job.user_prompt, job.job_id, top_k=5)
        except Exception as e:
            print(f"[StoryAgent] RAG search failed: {e}. Will use document_text fallback.")

        rag_context = "\n---\n".join([c["text"] for c in relevant_chunks]) if relevant_chunks else ""
        doc_text = (job.document_text or "")[:3000]
        has_document = bool(rag_context or doc_text)
        full_context = rag_context or doc_text

        print(f"[StoryAgent] RAG chunks: {len(relevant_chunks)} | doc_text length: {len(doc_text)} | has_document: {has_document}")
        print(f"[StoryAgent] Context source: {'RAG chunks' if rag_context else 'doc_text fallback' if doc_text else 'NO CONTEXT — generic lesson will be generated'}")

        # ── 3. Build grounded, subject-aware prompt ───────────────────────────
        revision_note = ""
        if job.metadata.get("revision_reason"):
            revision_note = f"\n[REVISION NEEDED]: {job.metadata['revision_reason']}\nAddress this issue in your new script.\n"

        grounding_instruction = ""
        if has_document:
            grounding_instruction = f"""IMPORTANT: The student has uploaded a document. Your explanation MUST directly quote or reference
specific content from the document excerpts below. Do NOT produce a generic lesson based only on
your training data. Ground every key concept in the document's language and examples.

Document Excerpts:
{full_context}

"""
        else:
            grounding_instruction = "No document was uploaded. Generate a clear, accurate lesson based on your knowledge.\n"

        prompt = f"""You are an expert educational video scriptwriter creating a Manim animation lesson.

TOPIC: "{job.user_prompt}"
SUBJECT AREA: {subject}
{grounding_instruction}{revision_note}
VISUAL STRATEGY for {subject}:
{visual_strategy}

Create a lesson script with EXACTLY 4 scenes. Each scene must include:
  - A "Narration:" line (what the narrator says — max 2 sentences, simple and clear)
  - A "Visual:" line (specific Manim visual — concrete description using shapes/animations listed in the visual strategy above)
  - A "Duration:" line (seconds the scene should last — 4 to 10 seconds)

RULES:
- DO NOT write generic text like "show a visual" or "display information".
- EVERY visual must specify concrete Manim primitives (e.g., "NumberPlane with a parabola plot", "Three Arrow vectors labeled Fx, Fy, Fz", "RoundedRectangle boxes connected by Arrows").
- Math expressions must be in plain ASCII, NOT LaTeX (e.g., "x^2 + 2x + 1", NOT "x^{{2}}+2x+1").
- Text labels must be SHORT (max 40 characters each).
- If the student's document is provided, directly quote or reference at least ONE specific fact, definition, or formula from it.
- Adapt the structure to the topic — not every topic needs the same 4-scene structure. Skip irrelevant scenes.

OUTPUT FORMAT (use exactly this structure):
## Scene 1: [Scene Title]
Narration: [1-2 clear sentences]
Visual: [Specific Manim elements and animations]
Duration: [N seconds]

## Scene 2: [Scene Title]
...

## Scene 3: [Scene Title]
...

## Scene 4: Key Takeaway
Narration: [Summary sentence]
Visual: [Summary visual — e.g., 3 bullet points on a card]
Duration: [N seconds]
"""

        api_key_present = bool(self.google_api_key or self.groq_api_key)
        print(f"[StoryAgent] API key present: {api_key_present} | Gemini: {bool(self.google_api_key)} | Groq: {bool(self.groq_api_key)}")

        if api_key_present:
            try:
                script, model_name = self._generate(prompt)
                if script and len(script) > 50:
                    job.story_script = script
                    job.model_used = model_name
                    print(f"[StoryAgent] Script generated via {model_name} ({len(script)} chars)")
                    return job
            except Exception as e:
                print(f"[StoryAgent] Generation error: {e}. Using subject-aware fallback.")

        # ── 4. Subject-aware fallback (no API key or all LLMs failed) ─────────
        topic = (job.user_prompt or "Concept").strip().replace("\n", " ")[:60]
        doc_snippet = full_context[:200].replace("\n", " ") if has_document else f"Core principles of {topic}."
        job.story_script = self._subject_fallback(topic, subject, doc_snippet)
        job.model_used = "fallback_template"
        print(f"[StoryAgent] Using subject-aware fallback for '{subject}'")
        return job

    def _subject_fallback(self, topic: str, subject: str, doc_snippet: str) -> str:
        """Returns a subject-appropriate fallback script that avoids ML-specific defaults."""
        visual_strategy = SUBJECT_VISUAL_STRATEGIES.get(subject, SUBJECT_VISUAL_STRATEGIES["general"])
        if subject == "math":
            return f"""## Scene 1: Introduction
Narration: Let's explore {topic} step by step.
Visual: Title "{topic}" written in large Text on screen with a simple axis grid (NumberPlane) in background.
Duration: 5 seconds

## Scene 2: Core Concept
Narration: Here is the key formula and what it means.
Visual: Text equation centered on screen. Arrow pointing to each component with short label.
Duration: 6 seconds

## Scene 3: Visual Example
Narration: We can visualize this on a graph.
Visual: Axes with a plotted curve. Dot and dashed line showing a key point value.
Duration: 8 seconds

## Scene 4: Key Takeaway
Narration: {topic} allows us to {doc_snippet[:80]}
Visual: Three bullet points summarizing the concept on a blue card.
Duration: 5 seconds"""

        if subject == "physics":
            return f"""## Scene 1: Introduction
Narration: Let's understand {topic} through diagrams and motion.
Visual: Title "{topic}" with an arrow diagram showing the key force or motion direction.
Duration: 5 seconds

## Scene 2: The Physics Principle
Narration: Here is the fundamental principle at work.
Visual: Body diagram with labeled Arrow vectors showing forces or motion.
Duration: 7 seconds

## Scene 3: Worked Example
Narration: Let's apply this to a concrete example.
Visual: Axes with a motion curve plotted. Key values annotated with Text labels.
Duration: 8 seconds

## Scene 4: Key Takeaway
Narration: {topic} tells us that {doc_snippet[:80]}
Visual: Summary card with the key formula as Text and a simple diagram.
Duration: 5 seconds"""

        if subject == "cs":
            return f"""## Scene 1: Introduction
Narration: Let's trace through {topic} step by step.
Visual: Title "{topic}" and a simple flowchart showing Input → Process → Output boxes.
Duration: 5 seconds

## Scene 2: Algorithm Steps
Narration: Here are the key steps in the process.
Visual: Numbered RoundedRectangle boxes connected with Arrow, each labeled with a step.
Duration: 7 seconds

## Scene 3: Data Transformation
Narration: Watch how data changes at each stage.
Visual: VGroup showing before/after state of data structure with highlighted changes.
Duration: 8 seconds

## Scene 4: Key Takeaway
Narration: {topic} enables {doc_snippet[:80]}
Visual: Three bullet-point summary boxes. Time/space complexity annotated.
Duration: 5 seconds"""

        # General fallback
        return f"""## Scene 1: Introduction
Narration: Let's explore {topic}.
Visual: Title "{topic}" in large Text, centered on screen. Background: dark gradient.
Duration: 5 seconds

## Scene 2: Core Concept
Narration: Here is the central idea.
Visual: RoundedRectangle card with "{topic}" and 2-line description text.
Duration: 6 seconds

## Scene 3: Key Components
Narration: The main components work together as follows.
Visual: Three labeled boxes with connecting Arrow objects showing relationships.
Duration: 8 seconds

## Scene 4: Key Takeaway
Narration: {doc_snippet[:100]}
Visual: Summary card with three bullet points listing key facts.
Duration: 5 seconds"""
