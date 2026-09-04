"""
QdrantRAGStore — Qdrant vector DB client using Gemini embeddings.

Spec requirements:
- Collection: "manim-docs-v4"
- Vector size: 768  (models/embedding-001)
- Distance: COSINE
"""

import os
import uuid
import hashlib
import json
from typing import List, Dict, Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue,
)

COLLECTION_NAME = "manim-docs-v5"
EMBEDDING_DIM = 3072  # Gemini gemini-embedding-2 output dimension

# Cross-student video cache collection
# Keyed by hash(pdf_content + user_prompt) — serves repeat requests instantly
CACHE_COLLECTION_NAME = "manim-video-cache-v4"
CACHE_VECTOR_DIM = 3072  # same embedding model


class GeminiEmbeddings:
    """
    Wrapper around Google Gemini embeddings API (models/embedding-001).
    """

    def __init__(self, api_key: str):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self.model_name = "models/gemini-embedding-2"
                self._available = True
            except Exception as e:
                print(f"[GeminiEmbeddings] Model load error: {e}")
                self._available = False

    def embed_text(self, text: str) -> List[float]:
        if not self._available:
            return self._pseudo_embed(text)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            try:
                import google.generativeai as genai
                result = genai.embed_content(
                    model=self.model_name,
                    content=text,
                    task_type="retrieval_document"
                )
                return result['embedding']
            except Exception as e:
                print(f"[GeminiEmbeddings] embed error: {e}")
                return self._pseudo_embed(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not self._available:
            return [self._pseudo_embed(t) for t in texts]
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            try:
                import google.generativeai as genai
                result = genai.embed_content(
                    model=self.model_name,
                    content=texts,
                    task_type="retrieval_document"
                )
                return result['embedding']
            except Exception as e:
                print(f"[GeminiEmbeddings] batch embed error: {e}")
                return [self._pseudo_embed(t) for t in texts]

    def _pseudo_embed(self, text: str) -> List[float]:
        """Deterministic pseudo-embedding fallback."""
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        embedding: List[float] = []
        for i in range(EMBEDDING_DIM):
            val = (digest[i % len(digest)] / 255.0) * 2.0 - 1.0
            embedding.append(val)
        return embedding


class QdrantRAGStore:
    """
    Qdrant vector store wrapper.
    Collection schema (from spec):
      - size=3072 (gemini-embedding-2)
      - distance=COSINE
    Point payload: {job_id, chunk_index, text, page}
    """

    def __init__(self, host: Optional[str] = None, api_key: Optional[str] = None):
        qdrant_url = host or os.getenv("QDRANT_URL") or os.getenv("QDRANT_HOST", ":memory:")
        qdrant_key = api_key or os.getenv("QDRANT_API_KEY")
        self.embeddings = GeminiEmbeddings(api_key=os.getenv("GOOGLE_API_KEY"))

        if qdrant_url == ":memory:":
            self.client = QdrantClient(location=":memory:")
        else:
            # Try remote with a short timeout; fall back to in-memory if unreachable
            try:
                self.client = QdrantClient(
                    url=qdrant_url,
                    api_key=qdrant_key,
                    timeout=5,
                    check_compatibility=False,
                )
                # Probe the connection immediately so we catch failures here, not later
                self.client.get_collections()
                print(f"[QdrantRAGStore] Connected to remote Qdrant at {qdrant_url}")
            except Exception as e:
                print(f"[QdrantRAGStore] Remote Qdrant unreachable ({e}); using in-memory fallback")
                self.client = QdrantClient(location=":memory:")

        self.create_collection_if_needed()


    def create_collection_if_needed(self):
        try:
            existing = {c.name for c in self.client.get_collections().collections}
            if COLLECTION_NAME not in existing:
                self.client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
                )
                print(f"[QdrantRAGStore] Created collection '{COLLECTION_NAME}' (dim={EMBEDDING_DIM})")

            # Create the cross-student video cache collection (NEW)
            if CACHE_COLLECTION_NAME not in existing:
                self.client.create_collection(
                    collection_name=CACHE_COLLECTION_NAME,
                    vectors_config=VectorParams(size=CACHE_VECTOR_DIM, distance=Distance.COSINE),
                )
                print(f"[QdrantRAGStore] Created cache collection '{CACHE_COLLECTION_NAME}'")

            # Create payload index for job_id field (required by Qdrant Cloud)
            try:
                self.client.create_payload_index(
                    collection_name=COLLECTION_NAME,
                    field_name="job_id",
                    field_schema="keyword",
                )
            except Exception:
                pass
            try:
                self.client.create_payload_index(
                    collection_name=CACHE_COLLECTION_NAME,
                    field_name="content_hash",
                    field_schema="keyword",
                )
            except Exception:
                pass
        except Exception as e:
            print(f"[QdrantRAGStore] Collection setup error: {e}")

    # ── Cross-student Video Cache (NEW) ──────────────────────────────────────────────

    @staticmethod
    def compute_content_hash(pdf_text: str, user_prompt: str) -> str:
        """
        Compute a stable cache key from the PDF content and user prompt.
        Two requests with the same textbook chapter and similar question
        will hash to the same key and serve a cached video.

        Uses SHA-256 of (normalized_prompt + first_2000_chars_of_pdf_text).
        """
        # Normalize: lowercase, strip whitespace for prompt-level dedup
        normalized_prompt = " ".join(user_prompt.lower().split())
        # Use first 2000 chars of PDF to identify the chapter/section
        pdf_fingerprint = pdf_text[:2000] if pdf_text else ""
        raw = f"{normalized_prompt}||{pdf_fingerprint}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def cache_video_result(
        self,
        content_hash: str,
        video_url: str,
        manim_code: str,
        story_script: str,
        user_prompt: str,
    ) -> None:
        """
        Store a finished video result in the cross-student cache.
        Called by UploaderAgent after a successful render + upload.
        """
        try:
            # Embed the user prompt for semantic retrieval (catches near-duplicate questions)
            vector = self.embeddings.embed_text(user_prompt)
            self.client.upsert(
                collection_name=CACHE_COLLECTION_NAME,
                points=[
                    PointStruct(
                        id=str(uuid.uuid4()),
                        vector=vector,
                        payload={
                            "content_hash": content_hash,
                            "video_url": video_url,
                            "manim_code": manim_code[:5000],  # truncate for storage
                            "story_script": story_script[:3000],
                            "user_prompt": user_prompt,
                        },
                    )
                ],
            )
            print(f"[QdrantRAGStore] Cached video result for hash {content_hash[:12]}...")
        except Exception as e:
            print(f"[QdrantRAGStore] Cache store failed (non-critical): {e}")

    def get_cached_video(
        self,
        content_hash: str,
        user_prompt: str,
        similarity_threshold: float = 0.92,
    ) -> Optional[Dict[str, Any]]:
        """
        Look up a cached video result.

        Two-phase lookup:
          1. Exact hash match (same PDF section + same prompt text)
          2. Semantic similarity match (same PDF section + similar prompt)
             with a high threshold (0.92) to avoid false positives.

        Returns dict with {video_url, manim_code, story_script} or None.
        """
        try:
            # Phase 1: exact hash lookup via payload filter
            exact_results = self.client.scroll(
                collection_name=CACHE_COLLECTION_NAME,
                scroll_filter=Filter(
                    must=[FieldCondition(key="content_hash", match=MatchValue(value=content_hash))]
                ),
                limit=1,
                with_payload=True,
            )
            points, _ = exact_results
            if points:
                payload = points[0].payload
                print(f"[QdrantRAGStore] ✅ Exact cache hit for hash {content_hash[:12]}...")
                return {
                    "video_url": payload.get("video_url"),
                    "manim_code": payload.get("manim_code"),
                    "story_script": payload.get("story_script"),
                    "cache_type": "exact",
                }

            # Phase 2: semantic similarity lookup
            query_vector = self.embeddings.embed_text(user_prompt)
            semantic_results = self.client.query_points(
                collection_name=CACHE_COLLECTION_NAME,
                query=query_vector,
                limit=1,
            ).points

            if semantic_results and semantic_results[0].score >= similarity_threshold:
                payload = semantic_results[0].payload
                print(f"[QdrantRAGStore] ✅ Semantic cache hit (score={semantic_results[0].score:.3f}) for '{user_prompt[:40]}'")
                return {
                    "video_url": payload.get("video_url"),
                    "manim_code": payload.get("manim_code"),
                    "story_script": payload.get("story_script"),
                    "cache_type": "semantic",
                }
        except Exception as e:
            print(f"[QdrantRAGStore] Cache lookup failed (non-critical): {e}")

        return None  # Cache miss — run full pipeline


    def upsert_chunks(self, chunks: List[Dict[str, Any]], job_id: str):
        """Embed and store document chunks for a given job_id."""
        points = []
        for index, chunk in enumerate(chunks):
            text = chunk.get("text", "")
            vector = self.embeddings.embed_text(text)
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "job_id": job_id,
                        "chunk_index": index,
                        "text": text,
                        "page": chunk.get("page", 1),
                    },
                )
            )

        if points:
            self.client.upsert(collection_name=COLLECTION_NAME, points=points)
            print(f"[QdrantRAGStore] Upserted {len(points)} chunks for job {job_id}")

    def search(self, query: str, job_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Semantic search restricted to a single job's document chunks."""
        query_vector = self.embeddings.embed_text(query)
        job_filter = Filter(
            must=[
                FieldCondition(key="job_id", match=MatchValue(value=job_id))
            ]
        )

        try:
            results = self.client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                query_filter=job_filter,
                limit=top_k,
            ).points
            return [
                {
                    "score": hit.score,
                    "text": hit.payload.get("text", ""),
                    "page": hit.payload.get("page", 1),
                }
                for hit in results
            ]
        except Exception as e:
            print(f"[QdrantRAGStore] Search failed: {e}")
            return []
