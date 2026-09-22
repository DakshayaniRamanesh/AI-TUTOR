"""
PdfHierarchicalParser — Developer 2, Step 1
============================================
Converts a PDF textbook or lecture notes into structured educational chunks.
Each chunk retains its full document hierarchy: subject, chapter, section,
page number, and content type. This metadata is what makes Kestrel subject-aware.

Usage (standalone test):
    python -m backend.workspace.pdf_hierarchical_parser path/to/textbook.pdf calculus_101
"""

import re
import json
import os
from typing import Optional

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("[PdfHierarchicalParser] WARNING: PyMuPDF not installed. Run: pip install pymupdf")


# ── Content type keyword patterns ──────────────────────────────────────────────
_CONTENT_TYPE_PATTERNS = [
    ("definition",    re.compile(r"^\s*(definition|def\.)\b", re.IGNORECASE)),
    ("theorem",       re.compile(r"^\s*(theorem|lemma|corollary|proposition)\b", re.IGNORECASE)),
    ("worked_example",re.compile(r"^\s*(example|worked example|solution|solved)\b", re.IGNORECASE)),
    ("exercise",      re.compile(r"^\s*(exercise|problem|practice|question)\b", re.IGNORECASE)),
]

# Font-size thresholds (points) for heading detection
_CHAPTER_FONT_SIZE  = 18.0
_SECTION_FONT_SIZE  = 13.0
_BODY_FONT_SIZE     = 9.0

# Minimum characters for a chunk to be worth keeping
_MIN_CHUNK_CHARS = 60


class PdfHierarchicalParser:
    """
    Parses a PDF into a list of structured educational chunks.

    Each chunk dict has:
        subject_id      : str   — caller-supplied slug (e.g. "calculus_101")
        document_title  : str   — PDF filename or supplied title
        chapter         : str   — e.g. "Chapter 3: Differentiation"
        section         : str   — e.g. "3.4 The Chain Rule"
        page_number     : int   — 1-indexed page
        content_type    : str   — definition | theorem | worked_example | exercise | text
        text            : str   — the actual paragraph text
    """

    def parse(
        self,
        pdf_path: str,
        subject_id: str,
        document_title: Optional[str] = None,
    ) -> list[dict]:
        """
        Main entry point. Returns list of chunk dicts.
        Falls back to page-by-page text if TOC and font-detection both fail.
        """
        if not PYMUPDF_AVAILABLE:
            raise RuntimeError("PyMuPDF is required. Install with: pip install pymupdf")

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        doc = fitz.open(pdf_path)
        title = document_title or os.path.splitext(os.path.basename(pdf_path))[0]

        # Try TOC-based hierarchy first, fall back to font-size heuristics
        toc_entries = self._extract_toc(doc)
        if toc_entries:
            chunks = self._parse_with_toc(doc, toc_entries, subject_id, title)
        else:
            chunks = self._parse_with_layout(doc, subject_id, title)

        doc.close()
        print(f"[PdfHierarchicalParser] Parsed '{title}' → {len(chunks)} chunks "
              f"({'TOC' if toc_entries else 'layout'} mode)")
        return chunks

    # ── TOC-based parsing ──────────────────────────────────────────────────────

    def _extract_toc(self, doc) -> list[tuple]:
        """
        Returns list of (level, title, start_page_0indexed) from PDF bookmarks.
        Empty list if no TOC available.
        """
        raw = doc.get_toc()  # [[level, title, page_1indexed], ...]
        if not raw:
            return []
        # Convert to 0-indexed pages
        return [(level, title.strip(), max(0, page - 1)) for level, title, page in raw]

    def _parse_with_toc(self, doc, toc_entries, subject_id, title) -> list[dict]:
        """
        Uses bookmarks to assign chapter/section labels to page ranges,
        then extracts text per block within each range.
        """
        chunks = []
        n_pages = len(doc)

        # Build page-range map: for each TOC entry, its text spans until the next entry
        for i, (level, heading, start_page) in enumerate(toc_entries):
            end_page = toc_entries[i + 1][2] if i + 1 < len(toc_entries) else n_pages

            chapter, section = self._resolve_hierarchy(toc_entries, i, level, heading)

            for page_idx in range(start_page, min(end_page, n_pages)):
                page = doc[page_idx]
                page_chunks = self._extract_page_chunks(
                    page, page_idx + 1, subject_id, title, chapter, section
                )
                chunks.extend(page_chunks)

        # Catch any pages before the first TOC entry
        first_toc_page = toc_entries[0][2] if toc_entries else 0
        if first_toc_page > 0:
            for page_idx in range(0, first_toc_page):
                page = doc[page_idx]
                chunks.extend(self._extract_page_chunks(
                    page, page_idx + 1, subject_id, title, "Preface", ""
                ))

        return chunks

    def _resolve_hierarchy(self, toc_entries, idx, level, heading) -> tuple[str, str]:
        """
        Walks backwards to find the nearest level-1 ancestor (chapter) for
        a given TOC entry, returning (chapter_label, section_label).
        """
        if level == 1:
            return heading, ""

        # Find the nearest level-1 ancestor above this entry
        chapter = "Unknown Chapter"
        for j in range(idx - 1, -1, -1):
            if toc_entries[j][0] == 1:
                chapter = toc_entries[j][1]
                break

        section = heading if level == 2 else ""
        return chapter, section

    # ── Font-size heuristic parsing ────────────────────────────────────────────

    def _parse_with_layout(self, doc, subject_id, title) -> list[dict]:
        """
        Fallback: detect chapter/section boundaries by font size.
        Larger fonts → chapter headings; medium fonts → section headings.
        """
        chunks = []
        current_chapter = "Chapter 1"
        current_section = ""

        for page_idx, page in enumerate(doc):
            blocks = page.get_text("dict").get("blocks", [])

            for block in blocks:
                if block.get("type") != 0:  # 0 = text block
                    continue

                block_text, max_size = self._extract_block_text_and_size(block)
                if not block_text.strip():
                    continue

                # Update hierarchy based on font size
                if max_size >= _CHAPTER_FONT_SIZE:
                    current_chapter = block_text.strip()
                    current_section = ""
                    continue  # headings are not content chunks themselves

                if _SECTION_FONT_SIZE <= max_size < _CHAPTER_FONT_SIZE:
                    current_section = block_text.strip()
                    continue

                # Body text → emit as chunk
                if max_size >= _BODY_FONT_SIZE and len(block_text.strip()) >= _MIN_CHUNK_CHARS:
                    chunks.append({
                        "subject_id":     subject_id,
                        "document_title": title,
                        "chapter":        current_chapter,
                        "section":        current_section,
                        "page_number":    page_idx + 1,
                        "content_type":   self._classify_content_type(block_text),
                        "text":           block_text.strip(),
                    })

        return chunks

    def _extract_block_text_and_size(self, block) -> tuple[str, float]:
        """Returns (full_text, max_font_size) for a text block."""
        lines_text = []
        max_size = 0.0
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                size = span.get("size", 0.0)
                if size > max_size:
                    max_size = size
                lines_text.append(span.get("text", ""))
        return " ".join(lines_text), max_size

    # ── Page-level chunk extraction ────────────────────────────────────────────

    def _extract_page_chunks(
        self,
        page,
        page_number: int,
        subject_id: str,
        document_title: str,
        chapter: str,
        section: str,
    ) -> list[dict]:
        """
        Extracts individual paragraph-level text blocks from a single page
        and wraps each into a chunk dict.
        """
        chunks = []
        blocks = page.get_text("dict").get("blocks", [])

        # Collect body text blocks (skip images, tiny font, very short snippets)
        current_paragraph = []

        for block in blocks:
            if block.get("type") != 0:
                continue

            block_text, max_size = self._extract_block_text_and_size(block)
            text = block_text.strip()

            if not text or max_size < _BODY_FONT_SIZE:
                continue

            # Flush accumulated paragraph if we hit a likely heading
            if max_size >= _SECTION_FONT_SIZE and current_paragraph:
                combined = " ".join(current_paragraph).strip()
                if len(combined) >= _MIN_CHUNK_CHARS:
                    chunks.append(self._make_chunk(
                        combined, subject_id, document_title, chapter, section, page_number
                    ))
                current_paragraph = []
                # Update section label inline for sub-headings on the page
                if max_size < _CHAPTER_FONT_SIZE:
                    section = text
                continue

            current_paragraph.append(text)

            # Flush at natural paragraph breaks (ends with period / is long enough)
            if len(" ".join(current_paragraph)) > 600:
                combined = " ".join(current_paragraph).strip()
                chunks.append(self._make_chunk(
                    combined, subject_id, document_title, chapter, section, page_number
                ))
                current_paragraph = []

        # Final flush
        if current_paragraph:
            combined = " ".join(current_paragraph).strip()
            if len(combined) >= _MIN_CHUNK_CHARS:
                chunks.append(self._make_chunk(
                    combined, subject_id, document_title, chapter, section, page_number
                ))

        return chunks

    def _make_chunk(self, text, subject_id, document_title, chapter, section, page_number) -> dict:
        return {
            "subject_id":     subject_id,
            "document_title": document_title,
            "chapter":        chapter,
            "section":        section,
            "page_number":    page_number,
            "content_type":   self._classify_content_type(text),
            "text":           text,
        }

    # ── Content type classifier ────────────────────────────────────────────────

    def _classify_content_type(self, text: str) -> str:
        """
        Classifies a text block by its opening keywords.
        Returns: definition | theorem | worked_example | exercise | text
        """
        for content_type, pattern in _CONTENT_TYPE_PATTERNS:
            if pattern.match(text):
                return content_type
        return "text"


# ── Standalone test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        # Use any PDF found in backend/workspace/pdfs/
        pdfs_dir = os.path.join(os.path.dirname(__file__), "pdfs")
        pdfs = [f for f in os.listdir(pdfs_dir) if f.endswith(".pdf")] if os.path.isdir(pdfs_dir) else []
        if not pdfs:
            print("Usage: python -m backend.workspace.pdf_hierarchical_parser <path/to/file.pdf> [subject_id]")
            print("  No PDFs found in backend/workspace/pdfs/ either.")
            sys.exit(1)
        pdf_path = os.path.join(pdfs_dir, pdfs[0])
        subject_id = "test_subject"
        print(f"Auto-selected: {pdf_path}")
    else:
        pdf_path   = sys.argv[1]
        subject_id = sys.argv[2] if len(sys.argv) > 2 else "test_subject"

    parser = PdfHierarchicalParser()
    chunks = parser.parse(pdf_path, subject_id)

    print(f"\nTotal chunks: {len(chunks)}")
    print("\n--- First 5 chunks ---")
    for i, c in enumerate(chunks[:5]):
        print(json.dumps(c, indent=2, ensure_ascii=False))
        print()

    # Verify all required fields exist
    required = {"subject_id", "document_title", "chapter", "section",
                "page_number", "content_type", "text"}
    missing_field_chunks = [i for i, c in enumerate(chunks) if not required.issubset(c.keys())]
    if missing_field_chunks:
        print(f"[FAIL] {len(missing_field_chunks)} chunks missing required fields: {missing_field_chunks[:5]}")
    else:
        print(f"[PASS] All {len(chunks)} chunks have all 7 required fields")

    # Content type distribution
    from collections import Counter
    types = Counter(c["content_type"] for c in chunks)
    print(f"\nContent type distribution: {dict(types)}")
