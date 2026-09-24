import sqlite3
from typing import List, Dict, Optional

from app.storage.database import DB_PATH
from backend.workspace.subject_vector_store import SubjectVectorStore

class SubjectSearchService:
    """
    Canonical subject search service implementing Hybrid Search (FTS + Vector).
    Results are merged and deduplicated.
    """
    
    def __init__(self, vector_store: Optional[SubjectVectorStore] = None):
        self.vector_store = vector_store or SubjectVectorStore()
        
    def _fts_search(self, subject_id: str, query_text: str, top_k: int = 5) -> List[Dict]:
        """Perform SQLite FTS5 lexical search."""
        results = []
        try:
            # Simple sanitization for FTS MATCH
            safe_query = ''.join(c if c.isalnum() else ' ' for c in query_text).strip()
            if not safe_query:
                return results
                
            # SQLite FTS uses match syntax, e.g. "term1 OR term2" or default AND.
            # We'll do a simple match on words
            match_query = ' OR '.join([f'"{word}"*' for word in safe_query.split()])
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # We need to query subject_chunks_fts and join with subject_chunks to get full metadata 
                # OR we just pull from FTS if it has what we need. We'll join to get content_type and material_id.
                sql = """
                    SELECT f.chunk_id, f.text, f.document_title, f.chapter, f.section, 
                           c.content_type, c.page_number, c.material_id
                    FROM subject_chunks_fts f
                    JOIN subject_chunks c ON f.chunk_id = c.id
                    WHERE subject_chunks_fts MATCH ? AND f.subject_id = ?
                    ORDER BY rank
                    LIMIT ?
                """
                cursor.execute(sql, (match_query, subject_id, top_k))
                for row in cursor.fetchall():
                    results.append({
                        "id": row["chunk_id"],
                        "text": row["text"],
                        "document_title": row["document_title"],
                        "chapter": row["chapter"],
                        "section": row["section"],
                        "page_number": row["page_number"],
                        "content_type": row["content_type"],
                        "material_id": row["material_id"],
                        "subject_id": subject_id,
                        "source": "lexical",
                        "score": 1.0  # FTS relative ranking handled by ORDER BY rank
                    })
        except Exception as e:
            print(f"[SubjectSearchService] FTS error: {e}")
            
        return results

    def search(
        self, 
        subject_id: str, 
        query_text: str, 
        content_type: Optional[str] = None, 
        top_k: int = 5
    ) -> List[Dict]:
        """
        Hybrid search: FTS + Qdrant.
        """
        # 1. Lexical Search
        fts_results = self._fts_search(subject_id, query_text, top_k=top_k)
        
        # 2. Vector Search (if embeddings available)
        vector_results = []
        if self.vector_store.embeddings._available:
            try:
                # Qdrant search already scopes by subject_id
                v_hits = self.vector_store.search(subject_id, query_text, top_k=top_k, content_type=content_type)
                for h in v_hits:
                    h["source"] = "vector"
                    vector_results.append(h)
            except Exception as e:
                print(f"[SubjectSearchService] Vector search error: {e}")

        # 3. Deduplicate and Fuse
        fused = {}
        # Add FTS results first (lexical exact match gets priority in simple fusion)
        for i, r in enumerate(fts_results):
            # Reciprocal rank score
            rr_score = 1.0 / (i + 1)
            r["rr_score"] = rr_score
            fused[r["text"]] = r
            
        for i, r in enumerate(vector_results):
            rr_score = 1.0 / (i + 1)
            if r["text"] in fused:
                fused[r["text"]]["rr_score"] += rr_score
                fused[r["text"]]["source"] = "hybrid"
            else:
                r["rr_score"] = rr_score
                fused[r["text"]] = r
                
        # Sort by fused score
        final_list = sorted(list(fused.values()), key=lambda x: x["rr_score"], reverse=True)
        
        # Clean up rr_score for output
        for r in final_list:
            r["score"] = r["rr_score"]
            
        return final_list[:top_k]
