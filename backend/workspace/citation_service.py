"""
CitationService — Developer 2, Step 3
=======================================
The interface between Developer 3's reasoning engine and the document knowledge base.
Developer 3 calls find_relevant_materials() and receives formatted, traceable citations
that can be embedded directly into the AI context and displayed in the hint bubble.

Usage (standalone test):
    python -m backend.workspace.citation_service
"""

import os
import sys
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.workspace.subject_vector_store import SubjectVectorStore


class CitationService:
    """
    Retrieves relevant course material for the tutoring context.

    Public API (called by Developer 3's ContextBuilder):
        find_relevant_materials(subject_id, topic, query_text, preferred_type, top_k)
        → list of citation dicts, each with text + citation_label + metadata
    """

    def __init__(self, store: Optional[SubjectVectorStore] = None):
        # Allow injection for testing; default creates its own store
        self.store = store or SubjectVectorStore()

    def find_relevant_materials(
        self,
        subject_id: str,
        topic: str,
        query_text: str,
        preferred_type: Optional[str] = None,
        top_k: int = 3,
    ) -> list[dict]:
        """
        Retrieves the most relevant chunks for the current tutoring context.

        Args:
            subject_id:     The student's current subject slug (e.g. "calculus_101").
                            Results are strictly scoped to this subject.
            topic:          Human-readable label for logging (e.g. "chain rule").
            query_text:     Full semantic query (e.g. "how do I differentiate composite functions").
            preferred_type: Optional content_type bias — e.g. "worked_example" when the
                            student needs a demonstration rather than a definition.
            top_k:          Maximum number of citations to return. Developer 3's ContextBuilder
                            typically uses top 2 (30% context budget).

        Returns:
            List of citation dicts sorted by relevance score (highest first):
            {
                "text":           str,   # the retrieved chunk text (keep under ~400 tokens)
                "citation_label": str,   # "Title — Section, p.N"
                "document_title": str,
                "chapter":        str,
                "section":        str,
                "page_number":    int,
                "content_type":   str,
                "subject_id":     str,
                "score":          float,
            }
        """
        print(f"[CitationService] Searching subject='{subject_id}' topic='{topic}' "
              f"type={preferred_type or 'any'}")

        # Primary search: with preferred_type filter if specified
        results = self.store.search(
            subject_id=subject_id,
            query_text=query_text,
            top_k=top_k,
            content_type=preferred_type,
        )

        # If preferred_type filter returned too few results, supplement with unfiltered search
        if preferred_type and len(results) < top_k:
            extra_needed = top_k - len(results)
            fallback = self.store.search(
                subject_id=subject_id,
                query_text=query_text,
                top_k=top_k + extra_needed,  # fetch more to deduplicate
                content_type=None,
            )
            # Deduplicate by text, append only new entries
            seen_texts = {r["text"] for r in results}
            for item in fallback:
                if item["text"] not in seen_texts and len(results) < top_k:
                    results.append(item)
                    seen_texts.add(item["text"])

        # Attach formatted citation labels
        citations = []
        for item in results:
            citation = dict(item)
            citation["citation_label"] = self._format_citation_label(item)
            citations.append(citation)

        print(f"[CitationService] Returning {len(citations)} citation(s) for '{topic}'")
        return citations

    def _format_citation_label(self, chunk: dict) -> str:
        """
        Produces a human-readable citation string the AI and hint bubble can display.
        Format: "Document Title — Section Name, p.N"

        Examples:
            "Stewart Calculus 9e — 3.4 The Chain Rule, p.87"
            "Lecture Notes — Chapter 2: Derivatives, p.15"
        """
        title   = chunk.get("document_title", "Unknown Document")
        section = chunk.get("section", "").strip()
        chapter = chunk.get("chapter", "").strip()
        page    = chunk.get("page_number", 0)

        # Prefer section; fall back to chapter if section is empty
        location = section if section else chapter
        if not location:
            location = "Unknown Section"

        page_str = f", p.{page}" if page else ""
        return f"{title} — {location}{page_str}"


# ── Standalone test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import random
    random.seed(42)

    PASS = "[PASS]"
    FAIL = "[FAIL]"

    # ── Bootstrap a small in-memory subject store ──────────────────────────────
    store = SubjectVectorStore()

    sample_chunks = [
        {
            "subject_id": "test_calculus_brain",
            "document_title": "Stewart Calculus 9e",
            "chapter": "Chapter 3: Differentiation Rules",
            "section": "3.4 The Chain Rule",
            "page_number": 87,
            "content_type": "worked_example",
            "text": (
                "Example: Find the derivative of f(x) = sin(x^2). "
                "Solution: Let u = x^2, so f = sin(u). "
                "By the chain rule, f'(x) = cos(u) * 2x = 2x*cos(x^2)."
            ),
        },
        {
            "subject_id": "test_calculus_brain",
            "document_title": "Stewart Calculus 9e",
            "chapter": "Chapter 3: Differentiation Rules",
            "section": "3.4 The Chain Rule",
            "page_number": 85,
            "content_type": "definition",
            "text": (
                "Chain Rule: If g is differentiable at x and f is differentiable at g(x), "
                "then the composite function h(x) = f(g(x)) is differentiable at x and "
                "h'(x) = f'(g(x)) * g'(x)."
            ),
        },
        {
            "subject_id": "test_calculus_brain",
            "document_title": "Stewart Calculus 9e",
            "chapter": "Chapter 2: Derivatives",
            "section": "2.3 Product and Quotient Rules",
            "page_number": 52,
            "content_type": "theorem",
            "text": (
                "Product Rule: If f and g are both differentiable then "
                "d/dx[f(x)g(x)] = f(x)g'(x) + g(x)f'(x)."
            ),
        },
        {
            "subject_id": "test_calculus_brain",
            "document_title": "Stewart Calculus 9e",
            "chapter": "Chapter 4: Integration",
            "section": "4.1 Antiderivatives",
            "page_number": 110,
            "content_type": "text",
            "text": (
                "An antiderivative of a function f is a function F such that F'(x) = f(x). "
                "For example, F(x) = x^3/3 is an antiderivative of f(x) = x^2."
            ),
        },
        {
            "subject_id": "test_physics_brain",
            "document_title": "University Physics",
            "chapter": "Chapter 1: Mechanics",
            "section": "1.2 Newton's Laws",
            "page_number": 20,
            "content_type": "definition",
            "text": "Newton's second law: The net force on an object equals its mass times acceleration (F = ma).",
        },
    ]

    store.ingest_chunks(sample_chunks)
    service = CitationService(store=store)

    # ── Test 1: Basic retrieval ────────────────────────────────────────────────
    print("\n=== Test 1: Basic retrieval ===")
    results = service.find_relevant_materials(
        subject_id="test_calculus_brain",
        topic="chain rule",
        query_text="how to find the derivative of sin(x^2)",
        top_k=3,
    )
    print(f"  {PASS if len(results) > 0 else FAIL} Got {len(results)} results")

    required_fields = {"text", "citation_label", "document_title", "chapter",
                       "section", "page_number", "content_type", "score"}
    if results:
        has_all = required_fields.issubset(results[0].keys())
        print(f"  {PASS if has_all else FAIL} All required fields present")
        print(f"  Top citation_label: \"{results[0]['citation_label']}\"")
        print(f"  Top score: {results[0]['score']:.3f}")
        print(f"  Text preview: \"{results[0]['text'][:80]}\"")

    # ── Test 2: preferred_type filter ─────────────────────────────────────────
    print("\n=== Test 2: preferred_type='worked_example' ===")
    example_results = service.find_relevant_materials(
        subject_id="test_calculus_brain",
        topic="chain rule",
        query_text="show me a step-by-step derivative example",
        preferred_type="worked_example",
        top_k=3,
    )
    has_examples = any(r["content_type"] == "worked_example" for r in example_results)
    print(f"  {PASS if has_examples else FAIL} worked_example in top results")

    # ── Test 3: Subject isolation (physics must not appear) ───────────────────
    print("\n=== Test 3: Subject isolation ===")
    all_calculus = all(r["subject_id"] == "test_calculus_brain" for r in results)
    print(f"  {PASS if all_calculus else FAIL} No physics chunks leaked into calculus results")

    # ── Test 4: Citation label format ─────────────────────────────────────────
    print("\n=== Test 4: Citation label format ===")
    for r in results[:3]:
        label = r["citation_label"]
        has_title   = "Stewart Calculus" in label
        has_page    = "p." in label
        has_section = " — " in label
        ok = has_title and has_page and has_section
        print(f"  {PASS if ok else FAIL} \"{label}\"")

    # ── Test 5: Empty preferred_type fallback ─────────────────────────────────
    print("\n=== Test 5: Fallback when preferred_type returns 0 results ===")
    rare_results = service.find_relevant_materials(
        subject_id="test_calculus_brain",
        topic="integration",
        query_text="antiderivatives and integration techniques",
        preferred_type="exercise",   # no exercises in our sample → should fallback
        top_k=2,
    )
    print(f"  {PASS if len(rare_results) > 0 else FAIL} Fallback returned {len(rare_results)} result(s)")

    print("\n=== All citation_service tests complete ===")
