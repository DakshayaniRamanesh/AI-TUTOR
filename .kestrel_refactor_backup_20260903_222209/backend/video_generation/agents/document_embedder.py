import os
import re
import json
import uuid
import google.generativeai as genai
from pypdf import PdfReader
from backend.video_generation.models import VideoJob, JobStatus
from backend.workspace.qdrant_store import QdrantRAGStore
from app.storage.database import SessionLocal, ConceptNode, ConceptEdge


class DocumentEmbedderAgent:
    def __init__(self, rag_store: QdrantRAGStore):
        self.rag_store = rag_store

    def _parse_page_range(self, range_str: str, max_pages: int) -> set:
        """Parses a string like '1, 3-5' into a set of 0-indexed page numbers."""
        if not range_str:
            return set(range(max_pages))
            
        pages = set()
        for part in range_str.split(','):
            part = part.strip()
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    # Convert to 0-indexed and clamp to max_pages
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
        print(f"[DocumentEmbedderAgent] Extracting knowledge graph for subject {subject_id}...")
        # Combine text but limit to ~30k chars so we don't blow up the prompt context on huge books
        combined_text = "\n".join(texts)[:30000] 
        
        prompt = f"""
        You are a knowledge graph builder. Extract the core concepts and their relationships from the following text.
        Return ONLY valid JSON in this exact format, with no markdown formatting or backticks:
        {{
            "nodes": [
                {{"name": "Concept Name", "description": "Brief definition"}}
            ],
            "edges": [
                {{"source": "Concept Name", "target": "Other Concept Name", "relationship": "depends on"}}
            ]
        }}
        
        TEXT:
        {combined_text}
        """
        
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            raw_json = response.text.strip()
            
            # Clean up markdown formatting if Gemini adds it
            if raw_json.startswith("```json"):
                raw_json = raw_json[7:-3]
            elif raw_json.startswith("```"):
                raw_json = raw_json[3:-3]
            
            data = json.loads(raw_json)
            
            with SessionLocal() as db:
                # 1. Insert Nodes (only if they don't already exist for this subject)
                for n in data.get("nodes", []):
                    exists = db.query(ConceptNode).filter_by(subject_id=subject_id, name=n["name"]).first()
                    if not exists:
                        node = ConceptNode(
                            id=uuid.uuid4().hex,
                            subject_id=subject_id,
                            name=n["name"],
                            description=n.get("description", "")
                        )
                        db.add(node)
                
                # 2. Insert Edges (only if they don't already exist)
                for e in data.get("edges", []):
                    exists = db.query(ConceptEdge).filter_by(
                        subject_id=subject_id, 
                        source_name=e["source"], 
                        target_name=e["target"]
                    ).first()
                    if not exists:
                        edge = ConceptEdge(
                            id=uuid.uuid4().hex,
                            subject_id=subject_id,
                            source_name=e["source"],
                            target_name=e["target"],
                            relationship_desc=e.get("relationship", "")
                        )
                        db.add(edge)
                        
                db.commit()
                print(f"[DocumentEmbedderAgent] Saved {len(data.get('nodes', []))} nodes and {len(data.get('edges', []))} edges to Knowledge Graph!")
                
        except Exception as e:
            print(f"[DocumentEmbedderAgent] Failed to extract knowledge graph: {e}")


    def run(self, job: VideoJob) -> VideoJob:
        job.step = "document_embedder"
        job.progress_percentage = 10

        if not job.pdf_path or not os.path.exists(job.pdf_path):
            print(f"[DocumentEmbedderAgent] PDF path '{job.pdf_path}' not found. Using mock content.")
            mock_text = f"Topic content for: {job.user_prompt}. Explaining concepts, formulas, and visual proofs."
            job.document_text = mock_text
            self.rag_store.upsert_chunks([{"text": mock_text, "page": 1}], job.job_id)
            return job

        try:
            reader = PdfReader(job.pdf_path)
            num_pages = len(reader.pages)
            
            # NEW: Figure out which pages to actually read
            target_pages = self._parse_page_range(job.page_range, num_pages)
            
            # We removed the hard 20-page limit for the whole PDF! 
            # We only enforce a limit on the targeted extraction block so the LLM doesn't blow up.
            if len(target_pages) > 30:
                job.status = JobStatus.ERROR
                job.error_message = f"PAGE_LIMIT: You selected {len(target_pages)} pages. Maximum allowed per extraction is 30 pages."
                return job

            chunks = []
            full_text_parts = []
            
            # NEW: Iterate only over the targeted pages
            for idx in sorted(target_pages):
                page = reader.pages[idx]
                text = page.extract_text() or ""
                
                # NEW: If the student provided an emphasis note, inject it right at the top 
                # so the LLM keeps it heavily prioritized when analyzing this text.
                if idx == min(target_pages) and job.emphasis_note:
                    text = f"STUDENT EMPHASIS NOTE: {job.emphasis_note}\n\n" + text

                full_text_parts.append(text)
                
                # Chunk into ~500-token segments (~1200 chars with 1500 max)
                sub_chunks = [text[i:i+1500] for i in range(0, len(text), 1200)]
                for sub in sub_chunks:
                    if sub.strip():
                        # Page numbers in chunks should be 1-indexed for the user
                        chunks.append({"text": sub.strip(), "page": idx + 1})

            if not chunks:
                fallback = f"Document prompt: {job.user_prompt}"
                chunks.append({"text": fallback, "page": 1})
                full_text_parts.append(fallback)

            # Store plain text on the job state for LLM agents
            job.document_text = "\n\n".join(full_text_parts).strip()

            self.rag_store.upsert_chunks(chunks, job.job_id)
            print(f"[DocumentEmbedderAgent] Indexed {len(chunks)} chunks from {len(target_pages)} pages for job {job.job_id}")

            if getattr(job, 'subject_id', None):
                self._extract_and_save_knowledge_graph(job.subject_id, full_text_parts)

        except Exception as e:
            job.status = JobStatus.ERROR
            job.error_message = f"Error extracting PDF: {str(e)}"

        return job
