import os
import hashlib
import uuid
import datetime

from backend.workspace.pdf_hierarchical_parser import PdfHierarchicalParser
from app.services.document.image_extraction import ImageExtractionAdapter
from app.storage.database_ops import update_material_status, replace_subject_chunks
from backend.workspace.subject_vector_store import SubjectVectorStore
from app.services.knowledge.graph_extraction_service import KnowledgeGraphExtractionService
from app.services.knowledge.graph_reconciliation_service import GraphReconciliationService
from app.services.knowledge.semantic_graph_extractor import SemanticGraphExtractor


class SubjectIngestionService:
    """
    Pure-Python service for ingesting materials (PDFs, Images) into the Subject Brain.
    Handles extraction, chunking, database storage, FTS indexing, and vector indexing.
    """
    
    def __init__(self):
        self.pdf_parser = PdfHierarchicalParser()
        self.image_extractor = ImageExtractionAdapter()
        self.vector_store = SubjectVectorStore()
        
    def _compute_hash(self, file_path: str) -> str:
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _generate_chunk_id(self, subject_id: str, material_id: str, page: int, index: int, text: str) -> str:
        """Deterministic chunk ID based on content and location."""
        raw = f"{subject_id}_{material_id}_{page}_{index}_{text}"
        return hashlib.md5(raw.encode('utf-8')).hexdigest()

    def ingest_material(self, material_id: str, subject_id: str, file_path: str, resource_type: str, force_reindex: bool = False, cancel_check=None) -> dict:
        """
        Main ingestion entrypoint. Runs synchronously.
        Should be called from a background thread/worker.
        """
        try:
            if cancel_check and cancel_check():
                raise Exception("Cancelled")
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            file_size = os.path.getsize(file_path)
            content_hash = self._compute_hash(file_path)

            # Check if unchanged (unless forced)
            # In real system, we'd read DB here to check old hash, but we just always update for safety if forced
            # Or we let DB caller decide `force_reindex`
            
            update_material_status(material_id, "EXTRACTING", content_hash=content_hash, file_size=file_size)
            
            # Extract
            raw_chunks = []
            if resource_type.upper() == "PDF":
                raw_chunks = self.pdf_parser.parse(file_path, subject_id)
            elif resource_type.upper() in ["IMAGE", "JPG", "PNG", "JPEG"]:
                raw_chunks = self.image_extractor.extract(file_path, subject_id)
            else:
                raise ValueError(f"Unsupported resource type: {resource_type}")

            # Normalize and prepare DB chunks
            db_chunks = []
            for i, rc in enumerate(raw_chunks):
                if cancel_check and cancel_check():
                    raise Exception("Cancelled during parsing")
                    
                text = rc.get("text", "")
                page = rc.get("page_number", 1)
                chunk_id = self._generate_chunk_id(subject_id, material_id, page, i, text)
                
                db_chunks.append({
                    "id": chunk_id,
                    "chunk_index": i,
                    "document_title": rc.get("document_title", ""),
                    "chapter": rc.get("chapter", ""),
                    "section": rc.get("section", ""),
                    "page_number": page,
                    "content_type": rc.get("content_type", "text"),
                    "text": text,
                    "token_count": len(text.split()),  # approximate
                    "content_hash": hashlib.md5(text.encode()).hexdigest(),
                    "parent_path": f"{rc.get('chapter', '')}/{rc.get('section', '')}",
                    "subject_id": subject_id,
                    "material_id": material_id
                })

            update_material_status(material_id, "INDEXING")

            # Transactional replace in SQLite (Triggers FTS)
            replace_subject_chunks(material_id, subject_id, db_chunks)

            # Attempt vector indexing
            # Delete old points first
            self.vector_store.delete_by_material(subject_id, material_id)
            
            n_vector = 0
            if len(db_chunks) == 0 and resource_type.upper() in ["IMAGE", "JPG", "PNG", "JPEG"]:
                status = "PARTIAL"  # No chunks from stub image extraction
            else:
                # Only vector index if Gemini is available
                if self.vector_store.embeddings._available and len(db_chunks) > 0:
                    n_vector = self.vector_store.ingest_chunks(db_chunks, cancel_check=cancel_check)
                    status = "READY"
                else:
                    status = "PARTIAL"

            update_material_status(material_id, status, chunk_count=len(db_chunks), last_indexed_at=datetime.datetime.utcnow())
            
            # --- Graph Extraction ---
            try:
                if cancel_check and cancel_check():
                    raise Exception("Cancelled before graph extraction")

                from app.storage.database import get_session_factory, Material
                with get_session_factory()() as session:
                    mat = session.query(Material).filter_by(id=material_id).first()
                    if not mat or mat.content_hash != content_hash:
                        print("Stale material build detected, aborting graph extraction.")
                        raise Exception("Stale build")
                        
                graph_service = KnowledgeGraphExtractionService()
                snapshot = graph_service.extract_structural_graph(subject_id, material_id)
                
                # Optional Semantic Extraction
                semantic_edges = SemanticGraphExtractor().extract_semantic_edges(subject_id, material_id, db_chunks)
                snapshot.edges.extend(semantic_edges)
                
                # Stale check before applying
                with get_session_factory()() as session:
                    mat = session.query(Material).filter_by(id=material_id).first()
                    if not mat or mat.content_hash != content_hash:
                        raise Exception("Stale build detected right before reconciliation.")

                GraphReconciliationService().reconcile_material_graph(subject_id, material_id, snapshot.nodes, snapshot.edges)
            except Exception as graph_err:
                # Don't fail the whole ingestion if graph extraction fails
                print(f"Graph extraction failed: {graph_err}")

            return {
                "status": status,
                "material_id": material_id,
                "chunks_extracted": len(db_chunks),
                "chunks_vectorized": n_vector
            }

        except Exception as e:
            update_material_status(material_id, "FAILED", error=str(e))
            return {
                "status": "FAILED",
                "material_id": material_id,
                "error": str(e)
            }
