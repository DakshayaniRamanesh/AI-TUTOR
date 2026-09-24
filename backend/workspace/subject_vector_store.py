"""
SubjectVectorStore — Developer 2, Step 2
=========================================
Qdrant wrapper that stores educational chunks per-subject and retrieves them
with mandatory subject_id scoping. Calculus queries never return physics chunks.

Reuses GeminiEmbeddings from qdrant_store.py — no duplicate embedding code.
Falls back to in-memory Qdrant when no server is available (safe for dev/testing).

Usage (standalone test):
    python -m backend.workspace.subject_vector_store
"""

import os
import sys
import uuid
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
    Filter, FieldCondition, MatchValue,
)

# Reuse the existing embedding wrapper — don't duplicate it
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.workspace.qdrant_store import GeminiEmbeddings

# Load .env so GOOGLE_API_KEY / QDRANT_URL are available
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, "backend", ".env"))
except ImportError:
    pass

# ── Constants ──────────────────────────────────────────────────────────────────
COLLECTION      = "kestrel-subject-brain-v1"
EMBEDDING_DIM   = 3072   # models/gemini-embedding-2


class SubjectVectorStore:
    """
    Qdrant vector store for Kestrel's educational knowledge layer.

    Key difference from the existing QdrantRAGStore:
      - Uses a separate collection (kestrel-subject-brain-v1)
      - Every insert and search is scoped by subject_id
      - Supports optional content_type filtering for preferred retrieval
      - Stores full chapter/section/page metadata per point
    """

    def __init__(self):
        self.embeddings = GeminiEmbeddings(api_key=os.getenv("GOOGLE_API_KEY"))
        self.client = self._connect()
        self._ensure_collection()

    # ── Connection ─────────────────────────────────────────────────────────────

    def _connect(self) -> QdrantClient:
        qdrant_url = os.getenv("QDRANT_URL", ":memory:")
        qdrant_key = os.getenv("QDRANT_API_KEY", "")

        if qdrant_url == ":memory:":
            print("[SubjectVectorStore] Using in-memory Qdrant (dev mode)")
            return QdrantClient(location=":memory:")

        try:
            client = QdrantClient(
                url=qdrant_url,
                api_key=qdrant_key or None,
                timeout=5,
                check_compatibility=False,
            )
            client.get_collections()  # probe
            print(f"[SubjectVectorStore] Connected to remote Qdrant at {qdrant_url}")
            return client
        except Exception as e:
            print(f"[SubjectVectorStore] Remote unreachable ({e}); using in-memory fallback")
            return QdrantClient(location=":memory:")

    def _ensure_collection(self):
        """Create the collection and payload indexes if they don't exist yet."""
        try:
            existing = {c.name for c in self.client.get_collections().collections}
            if COLLECTION not in existing:
                self.client.create_collection(
                    collection_name=COLLECTION,
                    vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
                )
                print(f"[SubjectVectorStore] Created collection '{COLLECTION}' (dim={EMBEDDING_DIM})")

            # Keyword indexes for fast filtered queries
            for field in ("subject_id", "content_type", "material_id"):
                try:
                    self.client.create_payload_index(
                        collection_name=COLLECTION,
                        field_name=field,
                        field_schema="keyword",
                    )
                except Exception:
                    pass  # index already exists or in-memory (no-op)

        except Exception as e:
            print(f"[SubjectVectorStore] Collection setup error: {e}")

    # ── Ingest ─────────────────────────────────────────────────────────────────

    def ingest_chunks(self, chunks: list[dict], cancel_check=None) -> int:
        """
        Embed and upsert a list of chunk dicts into Qdrant.
        Each chunk must contain the 7 fields from PdfHierarchicalParser.
        Returns the number of points successfully stored.
        """
        if not chunks:
            return 0

        points = []
        for chunk in chunks:
            if cancel_check and cancel_check():
                raise Exception("Cancelled during vectorization")
            
            text = chunk.get("text", "").strip()
            if not text:
                continue

            vector = self.embeddings.embed_text(text)
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "chunk_id":       chunk.get("id", ""),
                        "subject_id":     chunk.get("subject_id", ""),
                        "material_id":    chunk.get("material_id", ""),
                        "document_title": chunk.get("document_title", ""),
                        "chapter":        chunk.get("chapter", ""),
                        "section":        chunk.get("section", ""),
                        "page_number":    chunk.get("page_number", 0),
                        "content_type":   chunk.get("content_type", "text"),
                        "text":           text,
                        "content_hash":   chunk.get("content_hash", ""),
                    },
                )
            )

        if points:
            self.client.upsert(collection_name=COLLECTION, points=points)
            print(f"[SubjectVectorStore] Upserted {len(points)} chunks "
                  f"(subject={chunks[0].get('subject_id', '?')})")

        return len(points)

    # ── Search ─────────────────────────────────────────────────────────────────

    def search(
        self,
        subject_id: str,
        query_text: str,
        top_k: int = 5,
        content_type: Optional[str] = None,
    ) -> list[dict]:
        """
        Semantic search scoped to a single subject.

        Args:
            subject_id:   mandatory — restricts results to this subject only
            query_text:   the natural-language query
            top_k:        number of results to return
            content_type: optional — filter to e.g. 'worked_example' only

        Returns list of dicts with all chunk metadata + similarity score.
        """
        query_vector = self.embeddings.embed_text(query_text)
        search_filter = self._build_filter(subject_id, content_type)

        try:
            hits = self.client.query_points(
                collection_name=COLLECTION,
                query=query_vector,
                query_filter=search_filter,
                limit=top_k,
            ).points

            return [
                {
                    "score":          hit.score,
                    "text":           hit.payload.get("text", ""),
                    "subject_id":     hit.payload.get("subject_id", ""),
                    "document_title": hit.payload.get("document_title", ""),
                    "chapter":        hit.payload.get("chapter", ""),
                    "section":        hit.payload.get("section", ""),
                    "page_number":    hit.payload.get("page_number", 0),
                    "content_type":   hit.payload.get("content_type", "text"),
                }
                for hit in hits
            ]

        except Exception as e:
            print(f"[SubjectVectorStore] Search failed: {e}")
            return []

    def _build_filter(self, subject_id: str, content_type: Optional[str] = None) -> Filter:
        """Builds a Qdrant Filter combining subject_id + optional content_type."""
        conditions = [
            FieldCondition(key="subject_id", match=MatchValue(value=subject_id))
        ]
        if content_type:
            conditions.append(
                FieldCondition(key="content_type", match=MatchValue(value=content_type))
            )
        return Filter(must=conditions)

    # ── Utility ────────────────────────────────────────────────────────────────

    def delete_by_material(self, subject_id: str, material_id: str) -> bool:
        """Deletes all chunks for a specific material from Qdrant."""
        try:
            self.client.delete(
                collection_name=COLLECTION,
                points_selector=Filter(
                    must=[
                        FieldCondition(key="subject_id", match=MatchValue(value=subject_id)),
                        FieldCondition(key="material_id", match=MatchValue(value=material_id))
                    ]
                )
            )
            print(f"[SubjectVectorStore] Deleted points for material {material_id} in subject {subject_id}")
            return True
        except Exception as e:
            print(f"[SubjectVectorStore] Failed to delete points for material {material_id}: {e}")
            return False

    def count(self, subject_id: str) -> int:
        """Returns the number of chunks stored for a given subject."""
        try:
            result = self.client.count(
                collection_name=COLLECTION,
                count_filter=Filter(
                    must=[FieldCondition(key="subject_id", match=MatchValue(value=subject_id))]
                ),
                exact=True,
            )
            return result.count
        except Exception:
            return 0


# ── Standalone test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    PASS = "[PASS]"
    FAIL = "[FAIL]"

    store = SubjectVectorStore()

    # Build 50 synthetic calculus chunks across chapters/types
    import random
    random.seed(42)

    CHAPTER_SECTIONS = [
        ("Chapter 1: Limits",         "1.1 Introduction to Limits"),
        ("Chapter 1: Limits",         "1.2 Limit Laws"),
        ("Chapter 2: Derivatives",    "2.1 Definition of the Derivative"),
        ("Chapter 2: Derivatives",    "2.2 Differentiation Rules"),
        ("Chapter 3: Applications",   "3.1 Related Rates"),
        ("Chapter 4: Integration",    "4.1 Antiderivatives"),
        ("Chapter 4: Integration",    "4.2 The Definite Integral"),
    ]
    CONTENT_TYPES = ["definition", "theorem", "worked_example", "exercise", "text"]
    BODIES = [
        "The limit of f(x) as x approaches a is L if for every epsilon > 0 there exists delta > 0.",
        "To factor x^2 - 5x + 6 we look for two numbers that multiply to 6 and add to -5: (x-2)(x-3).",
        "The derivative of sin(x) is cos(x) by the definition of the derivative.",
        "Example: Find the derivative of f(x) = x^2 + 3x. Solution: f'(x) = 2x + 3.",
        "Exercise: Differentiate f(x) = e^x * sin(x) using the product rule.",
        "Definition: A function f is continuous at a if lim(x->a) f(x) = f(a).",
        "Theorem: If f is differentiable at a then f is continuous at a.",
        "The chain rule states d/dx[f(g(x))] = f'(g(x)) * g'(x).",
        "The quadratic formula is x = (-b +/- sqrt(b^2 - 4ac)) / 2a.",
        "The fundamental theorem of calculus links differentiation and integration.",
    ]

    calculus_chunks = []
    for i in range(50):
        ch, sec = CHAPTER_SECTIONS[i % len(CHAPTER_SECTIONS)]
        calculus_chunks.append({
            "subject_id":     "test_calculus_brain",
            "document_title": "Stewart Calculus 9e",
            "chapter":        ch,
            "section":        sec,
            "page_number":    (i % 200) + 1,
            "content_type":   CONTENT_TYPES[i % len(CONTENT_TYPES)],
            "text":           BODIES[i % len(BODIES)] + f" (chunk {i})",
        })

    # Also insert 10 physics chunks to prove subject isolation
    physics_chunks = [
        {
            "subject_id":     "test_physics_brain",
            "document_title": "University Physics",
            "chapter":        "Chapter 1: Mechanics",
            "section":        "1.1 Newton's Laws",
            "page_number":    i + 1,
            "content_type":   "text",
            "text":           f"Newton's second law: F = ma. Forces cause acceleration. (chunk {i})",
        }
        for i in range(10)
    ]

    print("\n=== Inserting chunks ===")
    n_calc = store.ingest_chunks(calculus_chunks)
    n_phys = store.ingest_chunks(physics_chunks)
    print(f"  {PASS if n_calc == 50 else FAIL} Inserted {n_calc}/50 calculus chunks")
    print(f"  {PASS if n_phys == 10 else FAIL} Inserted {n_phys}/10 physics chunks")

    print("\n=== Search: subject scoping ===")
    results = store.search("test_calculus_brain", "how to factor quadratic expressions", top_k=5)
    print(f"  {PASS if len(results) > 0 else FAIL} Got {len(results)} results")
    all_calculus = all(r["subject_id"] == "test_calculus_brain" for r in results)
    print(f"  {PASS if all_calculus else FAIL} All results are calculus (subject isolation)")
    if results:
        print(f"  Top result (score={results[0]['score']:.3f}): \"{results[0]['text'][:80]}\"")

    print("\n=== Search: content_type filter ===")
    examples = store.search("test_calculus_brain", "derivative example", top_k=5, content_type="worked_example")
    all_examples = all(r["content_type"] == "worked_example" for r in examples)
    print(f"  {PASS if all_examples else FAIL} All filtered results are worked_example "
          f"(got {len(examples)})")

    print("\n=== Result fields ===")
    if results:
        required = {"score", "text", "subject_id", "document_title",
                    "chapter", "section", "page_number", "content_type"}
        has_all = required.issubset(results[0].keys())
        print(f"  {PASS if has_all else FAIL} Top result has all required fields")

    print("\n=== Done ===")
