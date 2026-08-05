import os
from pypdf import PdfReader
from backend.video_generation.models import VideoJob, JobStatus
from backend.workspace.qdrant_store import QdrantRAGStore


class DocumentEmbedderAgent:
    def __init__(self, rag_store: QdrantRAGStore):
        self.rag_store = rag_store

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
            if num_pages > 20:
                job.status = JobStatus.ERROR
                job.error_message = f"INVALID_PDF: PDF has {num_pages} pages. Maximum allowed is 20 pages."
                return job

            chunks = []
            full_text_parts = []
            for idx, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                full_text_parts.append(text)
                # Chunk into ~500-token segments (~1200 chars with 1500 max)
                sub_chunks = [text[i:i+1500] for i in range(0, len(text), 1200)]
                for sub in sub_chunks:
                    if sub.strip():
                        chunks.append({"text": sub.strip(), "page": idx + 1})

            if not chunks:
                fallback = f"Document prompt: {job.user_prompt}"
                chunks.append({"text": fallback, "page": 1})
                full_text_parts.append(fallback)

            # Store plain text on the job state for LLM agents
            job.document_text = "\n\n".join(full_text_parts).strip()

            self.rag_store.upsert_chunks(chunks, job.job_id)
            print(f"[DocumentEmbedderAgent] Indexed {len(chunks)} chunks for job {job.job_id}")

        except Exception as e:
            job.status = JobStatus.ERROR
            job.error_message = f"Error extracting PDF: {str(e)}"

        return job
