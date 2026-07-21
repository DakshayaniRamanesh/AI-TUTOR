"""
QdrantRAGStore — Qdrant vector DB client using gemini-embedding-2.

Spec requirements:
- Collection: "manim-docs"
- Vector size: 3072  (gemini-embedding-2 output dimension, GA April 2026)
- Distance: COSINE
- Env var: GOOGLE_API_KEY  (not GEMINI_API_KEY)
"""

import os
import uuid
import hashlib
from typing import List, Dict, Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue,
)

COLLECTION_NAME = "manim-docs"
EMBEDDING_DIM = 768  # text-embedding-004 output dimension


class GeminiEmbeddings:
    """
    Wrapper around text-embedding-004.
    Falls back to a deterministic pseudo-embedding for offline/mock testing.
    """

    MODEL = "models/text-embedding-004"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self._client = None
        if self.api_key:
            try:
                # Prefer new google.genai SDK; fall back to legacy google.generativeai
                try:
                    import google.genai as genai  # type: ignore
                    self._client = genai.Client(api_key=self.api_key)
                    self._sdk = "new"
                except ImportError:
                    import google.generativeai as genai  # type: ignore
                    genai.configure(api_key=self.api_key)
                    self._legacy_genai = genai
                    self._sdk = "legacy"
            except Exception as e:
                print(f"[GeminiEmbeddings] SDK init error: {e}. Falling back to pseudo-embeddings.")
                self._sdk = None
        else:
            self._sdk = None

    def embed_text(self, text: str) -> List[float]:
        if self._sdk == "new":
            try:
                result = self._client.models.embed_content(
                    model=self.MODEL,
                    contents=text,
                )
                return result.embedding.values
            except Exception as e:
                print(f"[GeminiEmbeddings] embed_text error: {e}. Using pseudo-embedding.")
        elif self._sdk == "legacy":
            try:
                result = self._legacy_genai.embed_content(
                    model=self.MODEL,
                    content=text,
                    task_type="retrieval_document",
                )
                return result["embedding"]
            except Exception as e:
                print(f"[GeminiEmbeddings] (legacy) embed_text error: {e}. Using pseudo-embedding.")

        return self._pseudo_embed(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]

    def _pseudo_embed(self, text: str) -> List[float]:
        """Deterministic pseudo-embedding for offline/mock testing."""
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
        self.embeddings = GeminiEmbeddings()

        if qdrant_url == ":memory:":
            self.client = QdrantClient(location=":memory:")
        else:
            self.client = QdrantClient(url=qdrant_url, api_key=qdrant_key)

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
            
            # Create payload index for job_id field (required by Qdrant Cloud)
            try:
                self.client.create_payload_index(
                    collection_name=COLLECTION_NAME,
                    field_name="job_id",
                    field_schema="keyword",
                )
            except Exception:
                pass
        except Exception as e:
            print(f"[QdrantRAGStore] Collection setup error: {e}")

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
