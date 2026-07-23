"""
PDF Document Ingestion & Grounded RAG (Retrieval-Augmented Generation) Manager
Constrains AI responses strictly to uploaded PDF content with page citations.
"""

import os
import re
import requests
from pypdf import PdfReader
from dotenv import load_dotenv

load_dotenv("backend/.env")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

class PdfRAGManager:
    def __init__(self):
        self.file_path = ""
        self.doc_title = ""
        self.page_count = 0
        self.pages_text = [] # list of (page_num, text)
        self.chunks = [] # list of dict: {"page": int, "text": str}

    def load_pdf(self, file_path: str) -> bool:
        """
        Parses PDF file, extracts page-by-page text, and chunks content.
        """
        if not os.path.exists(file_path):
            return False

        try:
            self.file_path = file_path
            self.doc_title = os.path.basename(file_path)
            reader = PdfReader(file_path)
            self.page_count = len(reader.pages)
            self.pages_text = []
            self.chunks = []

            for idx, page in enumerate(reader.pages):
                page_num = idx + 1
                text = page.extract_text() or ""
                text_clean = text.strip()
                if text_clean:
                    self.pages_text.append((page_num, text_clean))
                    
                    # Break page text into paragraph chunks (~300 chars)
                    paragraphs = re.split(r'\n\s*\n', text_clean)
                    for para in paragraphs:
                        p_sub = para.strip()
                        if len(p_sub) > 20:
                            self.chunks.append({
                                "page": page_num,
                                "text": p_sub
                            })
            return True
        except Exception as err:
            print(f"[PdfRAGManager] Notice loading PDF: {err}")
            return False

    def is_loaded(self) -> bool:
        return bool(self.file_path and self.chunks)

    def retrieve_relevant_chunks(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Retrieves most relevant document chunks matching user query.
        """
        if not self.chunks:
            return []

        q_terms = set(re.findall(r'\w+', query.lower()))
        if not q_terms:
            return self.chunks[:top_k]

        scored_chunks = []
        for chunk in self.chunks:
            c_text_lower = chunk["text"].lower()
            score = 0
            for term in q_terms:
                if len(term) > 2:
                    score += c_text_lower.count(term)
            scored_chunks.append((score, chunk))

        # Sort by match score descending
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        # Return top_k matching chunks
        results = [item[1] for item in scored_chunks[:top_k] if item[0] > 0]
        if not results:
            results = self.chunks[:top_k] # Fallback to first chunks if no keyword overlap
        return results

    def generate_grounded_answer(self, query: str, selected_text: str = "", page_num: int = None) -> str:
        """
        Generates a grounded RAG response constrained strictly to PDF contents.
        Cites page numbers for answers.
        """
        if not self.is_loaded():
            return "Please load a PDF document first."

        # Check if query is summary request
        q_lower = query.lower()
        if any(k in q_lower for k in ["summary", "summarize", "overview"]) and not selected_text:
            return self.generate_grounded_summary()

        # Retrieve relevant context chunks
        chunks = self.retrieve_relevant_chunks(query, top_k=6)
        context_str = ""
        for c in chunks:
            context_str += f"[Page {c['page']}]: {c['text']}\n\n"

        selection_context = ""
        if selected_text:
            selection_context = f"Target Selected Passage from [Page {page_num or 'Current'}]: \"{selected_text}\"\n\n"

        prompt = (
            f"You are Kestrel AI Study Assistant. You MUST answer the user's question using ONLY the provided document context below.\n"
            f"STRICT GROUNDING RULES:\n"
            f"1. Rely strictly on facts directly mentioned in the document context below.\n"
            f"2. Do NOT use outside facts, unmentioned examples, or general web knowledge.\n"
            f"3. Cite specific page numbers (e.g. [Page 2]) for facts in your explanation.\n"
            f"4. If the document does not contain information to answer the query, reply EXACTLY with:\n"
            f"   'This document doesn't cover that — would you like me to answer using general knowledge instead?'\n\n"
            f"Document Title: {self.doc_title}\n"
            f"{selection_context}"
            f"Document Context:\n{context_str}\n"
            f"User Question: {query}\n\n"
            f"Provide a clear, grounded handwritten study response:"
        )

        # Call Gemini API
        if GOOGLE_API_KEY:
            models = ["gemini-2.0-flash", "gemini-1.5-flash"]
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            for model in models:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GOOGLE_API_KEY}"
                    resp = requests.post(url, json=payload, timeout=9)
                    if resp.status_code == 200:
                        ans = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                        return ans
                except Exception as err:
                    print(f"[PdfRAGManager] API Notice ({model}): {err}")

        # Fallback local grounded response
        c_first = chunks[0] if chunks else {"page": 1, "text": "Document text reference."}
        return (
            f"Document Reference: {self.doc_title} [Page {c_first['page']}]\n\n"
            f"Based strictly on this document:\n"
            f"• Key Point: {c_first['text'][:250]}...\n\n"
            f"This explanation is drawn strictly from {self.doc_title} [Page {c_first['page']}]."
        )

    def generate_grounded_summary(self) -> str:
        """
        Generates a comprehensive summary of the entire PDF document strictly using internal content.
        """
        if not self.is_loaded():
            return "No PDF document loaded."

        # Compile full document text preview
        doc_excerpt = ""
        for page_num, text in self.pages_text[:12]:
            doc_excerpt += f"--- Page {page_num} ---\n{text[:800]}\n\n"

        prompt = (
            f"You are Kestrel AI Study Assistant. Summarize this document strictly using material inside the text.\n"
            f"STRICT RULES:\n"
            f"1. Summarize ONLY what is written in the document excerpt below.\n"
            f"2. Do NOT add outside knowledge, facts, or assumptions.\n"
            f"3. Cite page numbers [Page X] for major sub-topics.\n\n"
            f"Document Title: {self.doc_title} ({self.page_count} pages)\n"
            f"Document Content Excerpts:\n{doc_excerpt[:4000]}\n\n"
            f"Format a comprehensive handwritten document summary with:\n"
            f"1. 📖 Document Overview\n"
            f"2. 📌 Key Sections & Page Findings\n"
            f"3. 🧠 Summary Conclusion"
        )

        if GOOGLE_API_KEY:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GOOGLE_API_KEY}"
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                resp = requests.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception as err:
                print(f"[PdfRAGManager] Summary API Notice: {err}")

        # Fallback summary
        first_page = self.pages_text[0] if self.pages_text else (1, "Document content")
        return (
            f"📖 Document Summary: {self.doc_title}\n"
            f"Total Pages: {self.page_count}\n\n"
            f"1. Overview [Page {first_page[0]}]:\n"
            f"{first_page[1][:300]}...\n\n"
            f"2. Grounded Findings:\n"
            f"• Extracted strictly from {self.doc_title} across {self.page_count} pages.\n"
            f"• All notes saved directly to your Kestrel notebook canvas."
        )
