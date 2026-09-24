import sqlite3
from typing import List, Dict, Optional

from app.storage.database import get_db_path
from backend.workspace.subject_vector_store import SubjectVectorStore

class SubjectSearchService:
    """
    Canonical subject search service implementing Hybrid Search (Exact Title + FTS + Vector).
    Results are strictly subject-scoped, merged, and deduplicated.
    """
    
    def __init__(self, vector_store: Optional[SubjectVectorStore] = None):
        self.vector_store = vector_store or SubjectVectorStore()
        
    def _exact_title_search(self, subject_id: str, query_text: str, top_k: int = 5) -> List[Dict]:
        """Check if query explicitly refers to an uploaded material by title/filename (e.g. 'Tutorial 1')."""
        results = []
        try:
            with sqlite3.connect(get_db_path()) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT id, filename FROM materials WHERE subject_id = ?", (subject_id,))
                materials = cursor.fetchall()
                matched_mat_ids = []
                q_lower = query_text.lower()

                for m in materials:
                    fname = (m["filename"] or "").lower()
                    base_name = fname.rsplit(".", 1)[0]
                    if base_name and len(base_name) >= 3 and base_name in q_lower:
                        matched_mat_ids.append(m["id"])
                    elif "tutorial 1" in q_lower and ("tutorial" in fname or "tut1" in fname or "1" in fname):
                        matched_mat_ids.append(m["id"])

                # Also search chunk document titles
                cursor.execute("""
                    SELECT DISTINCT material_id, document_title 
                    FROM subject_chunks 
                    WHERE subject_id = ? AND document_title IS NOT NULL
                """, (subject_id,))
                for row in cursor.fetchall():
                    dtitle = (row["document_title"] or "").lower()
                    if dtitle and len(dtitle) >= 3 and dtitle in q_lower:
                        if row["material_id"] not in matched_mat_ids:
                            matched_mat_ids.append(row["material_id"])

                for mat_id in matched_mat_ids:
                    cursor.execute("""
                        SELECT id as chunk_id, text, document_title, chapter, section, 
                               content_type, page_number, material_id
                        FROM subject_chunks
                        WHERE material_id = ? AND subject_id = ?
                        ORDER BY page_number ASC
                        LIMIT ?
                    """, (mat_id, subject_id, top_k))
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
                            "source": "exact_title",
                            "score": 2.0
                        })
        except Exception as e:
            print(f"[SubjectSearchService] Exact title search error: {e}")
        return results

    def _fts_search(self, subject_id: str, query_text: str, top_k: int = 5) -> List[Dict]:
        """Perform SQLite FTS5 lexical search strictly scoped to subject_id."""
        results = []
        try:
            safe_query = ''.join(c if c.isalnum() else ' ' for c in query_text).strip()
            if not safe_query:
                return results
                
            match_query = ' OR '.join([f'"{word}"*' for word in safe_query.split() if len(word) >= 2])
            if not match_query:
                return results
            
            with sqlite3.connect(get_db_path()) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
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
                        "score": 1.0
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
        Hybrid search: Exact Title + FTS + Qdrant.
        Deduplicates by chunk ID and encourages material diversity.
        """
        if not subject_id:
            return []

        # 1. Check for exact material title references
        exact_results = self._exact_title_search(subject_id, query_text, top_k=top_k)

        # 2. Lexical Search (FTS)
        fts_results = self._fts_search(subject_id, query_text, top_k=top_k)
        
        # 3. Vector Search (if embeddings available)
        vector_results = []
        if getattr(self.vector_store.embeddings, "_available", False):
            try:
                v_hits = self.vector_store.search(subject_id, query_text, top_k=top_k, content_type=content_type)
                for h in v_hits:
                    h["source"] = "vector"
                    vector_results.append(h)
            except Exception as e:
                print(f"[SubjectSearchService] Vector search error: {e}")

        # 4. Deduplicate and Fuse by chunk ID
        fused = {}
        # Exact title hits receive top priority
        for i, r in enumerate(exact_results):
            cid = r.get("id") or r.get("chunk_id")
            r["rr_score"] = 2.0 + (1.0 / (i + 1))
            fused[cid] = r

        for i, r in enumerate(fts_results):
            cid = r.get("id") or r.get("chunk_id")
            if cid not in fused:
                r["rr_score"] = 1.0 / (i + 1)
                fused[cid] = r
            else:
                fused[cid]["rr_score"] += (1.0 / (i + 1))
            
        for i, r in enumerate(vector_results):
            cid = r.get("id") or r.get("chunk_id")
            rr_score = 1.0 / (i + 1)
            if cid in fused:
                fused[cid]["rr_score"] += rr_score
                if fused[cid].get("source") != "exact_title":
                    fused[cid]["source"] = "hybrid"
            else:
                r["rr_score"] = rr_score
                fused[cid] = r
                
        # Sort by fused score
        final_list = sorted(list(fused.values()), key=lambda x: x["rr_score"], reverse=True)
        
        # Enforce material diversity: max 2 chunks from same material if others available
        diverse_list = []
        material_counts = {}
        for r in final_list:
            mat = r.get("material_id") or "unknown"
            cnt = material_counts.get(mat, 0)
            if cnt < 2 or len(diverse_list) + (len(final_list) - len(diverse_list)) <= top_k:
                diverse_list.append(r)
                material_counts[mat] = cnt + 1
            if len(diverse_list) >= top_k:
                break

        # Fallback to remaining if diverse_list is smaller than top_k
        if len(diverse_list) < top_k:
            for r in final_list:
                if r not in diverse_list:
                    diverse_list.append(r)
                if len(diverse_list) >= top_k:
                    break

        for r in diverse_list:
            r["score"] = r["rr_score"]
            
        return diverse_list[:top_k]
