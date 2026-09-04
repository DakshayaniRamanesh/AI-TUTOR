import os
import json
import uuid
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=FutureWarning)
    import google.generativeai as genai
from pypdf import PdfReader
from backend.video_generation.models import VideoJob, JobStatus
from backend.workspace.qdrant_store import QdrantRAGStore

# Desktop knowledge-graph persistence is optional. Modal currently packages the
# backend directory independently, so importing app.storage.database at module
# load time makes cloud video generation unnecessarily depend on the desktop app.
try:
    from app.storage.database import SessionLocal, ConceptNode, ConceptEdge
    _KNOWLEDGE_DB_AVAILABLE = True
except Exception:
    SessionLocal = ConceptNode = ConceptEdge = None
    _KNOWLEDGE_DB_AVAILABLE = False


class DocumentEmbedderAgent:
    def __init__(self, rag_store: QdrantRAGStore):
        self.rag_store = rag_store

    def _parse_page_range(self, range_str: str, max_pages: int) -> set:
        if not range_str:
            return set(range(max_pages))
        pages = set()
        for part in range_str.split(','):
            part = part.strip()
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    start = max(0, start - 1)
                    end = min(max_pages, end)
                    pages.update(range(start, end))
                except ValueError:
                    pass
            elif part.isdigit():
                page_idx = int(part) - 1
                if 0 <= page_idx < max_pages:
                    pages.add(page_idx)
        return pages if pages else set(range(max_pages))

    def _extract_and_save_knowledge_graph(self, subject_id: str, texts: list):
        if not _KNOWLEDGE_DB_AVAILABLE:
            print("[DocumentEmbedderAgent] Knowledge graph DB unavailable in this runtime; skipping persistence.")
            return

        print(f"[DocumentEmbedderAgent] Extracting knowledge graph for subject {subject_id}...")
        combined_text = "\n".join(texts)[:30000]
        prompt = f"""
You are a knowledge graph builder. Extract the core concepts and relationships from the text.
Return ONLY valid JSON:
{{
  "nodes": [{{"name":"Concept Name","description":"Brief definition"}}],
  "edges": [{{"source":"Concept Name","target":"Other Concept Name","relationship":"depends on"}}]
}}
TEXT:
{combined_text}
"""
        try:
            model = genai.GenerativeModel('gemini-3.5-flash-lite')
            response = model.generate_content(prompt)
            raw_json = response.text.strip()
            if raw_json.startswith("```json"):
                raw_json = raw_json[7:-3]
            elif raw_json.startswith("```"):
                raw_json = raw_json[3:-3]
            data = json.loads(raw_json)

            with SessionLocal() as db:
                for n in data.get("nodes", []):
                    exists = db.query(ConceptNode).filter_by(subject_id=subject_id, name=n["name"]).first()
                    if not exists:
                        db.add(ConceptNode(
                            id=uuid.uuid4().hex,
                            subject_id=subject_id,
                            name=n["name"],
                            description=n.get("description", ""),
                        ))
                for e in data.get("edges", []):
                    exists = db.query(ConceptEdge).filter_by(
                        subject_id=subject_id,
                        source_name=e["source"],
                        target_name=e["target"],
                    ).first()
                    if not exists:
                        db.add(ConceptEdge(
                            id=uuid.uuid4().hex,
                            subject_id=subject_id,
                            source_name=e["source"],
                            target_name=e["target"],
                            relationship_desc=e.get("relationship", ""),
                        ))
                db.commit()
        except Exception as e:
            print(f"[DocumentEmbedderAgent] Failed to extract knowledge graph: {e}")

    def run(self, job: VideoJob) -> VideoJob:
        job.step = "document_embedder"
        job.progress_percentage = 10

        if not job.pdf_path or not os.path.exists(job.pdf_path):
            # Board selections already contain their own primary context. Do not
            # pollute their RAG collection with a fabricated generic document.
            if getattr(job, "board_selection", None):
                job.document_text = job.document_text or ""
                return job

            mock_text = f"Topic content for: {job.user_prompt}. Explaining concepts, formulas, and visual proofs."
            job.document_text = mock_text
            material_id = self.rag_store.compute_content_hash(mock_text, "mock")
            job.material_id = material_id
            if not self.rag_store.has_material(material_id):
                self.rag_store.upsert_chunks([{"text": mock_text, "page": 1}], material_id)
            return job

        try:
            reader = PdfReader(job.pdf_path)
            num_pages = len(reader.pages)
            target_pages = self._parse_page_range(job.page_range, num_pages)
            if len(target_pages) > 30:
                job.status = JobStatus.ERROR
                job.error_message = f"PAGE_LIMIT: You selected {len(target_pages)} pages. Maximum allowed per extraction is 30 pages."
                return job

            chunks = []
            full_text_parts = []
            for idx in sorted(target_pages):
                page = reader.pages[idx]
                text = page.extract_text() or ""
                if idx == min(target_pages) and job.emphasis_note:
                    text = f"STUDENT EMPHASIS NOTE: {job.emphasis_note}\n\n" + text
                full_text_parts.append(text)
                for i in range(0, len(text), 1200):
                    sub = text[i:i+1500]
                    if sub.strip():
                        chunks.append({"text": sub.strip(), "page": idx + 1})

            if not chunks:
                fallback = f"Document prompt: {job.user_prompt}"
                chunks.append({"text": fallback, "page": 1})
                full_text_parts.append(fallback)

            job.document_text = "\n\n".join(full_text_parts).strip()
            
            # Use stable material_id to avoid redundant indexing
            material_id = job.material_id or self.rag_store.compute_content_hash(job.document_text, "material")
            job.material_id = material_id
            
            if not self.rag_store.has_material(material_id):
                self.rag_store.upsert_chunks(chunks, material_id)
                print(f"[DocumentEmbedderAgent] Indexed {len(chunks)} chunks from {len(target_pages)} pages for material {material_id}")
            else:
                print(f"[DocumentEmbedderAgent] Material {material_id} already embedded. Skipping upsert.")

            if getattr(job, 'subject_id', None):
                self._extract_and_save_knowledge_graph(job.subject_id, full_text_parts)

        except Exception as e:
            job.status = JobStatus.ERROR
            job.error_message = f"Error extracting PDF: {str(e)}"
        return job
