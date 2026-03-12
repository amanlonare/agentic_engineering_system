import hashlib
from typing import Any, List

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from src.smart_chunker.base import BaseEngine
from src.smart_chunker.schemas import Chunk, ChunkMetadata, ChunkType


class PdfEngine(BaseEngine):
    """
    Chunking engine for PDF documents using PyMuPDF.
    Attempts hierarchical chunking via TOC (Table of Contents).
    Falls back to page-by-page block chunking if no TOC exists.
    """

    MAX_CHUNK_CHARS = 4000  # Threshold for sub-splitting large sections

    def chunk(self, content: str, source_id: str, **_kwargs) -> List[Chunk]:
        """
        Note: For PDFs, `content` is expected to be the absolute file path,
        since we cannot easily read binary PDF data as a UTF-8 string directly
        into the router. The caller should pass the path instead.
        """
        if fitz is None:
            raise ImportError(
                "PyMuPDF is required for PDF chunking. Install with `pip install pymupdf`"
            )

        # Assume `content` is the file path for PDF engine
        file_path = content

        try:
            doc = fitz.open(file_path)
        except Exception as e:
            raise ValueError(f"Failed to open PDF {file_path}: {e}")

        toc = doc.get_toc()

        # Sanity check: Ensure the TOC actually breaks down the document
        is_useful_toc = False
        if toc:
            num_entries = len(toc)
            num_pages = doc.page_count

            # If there are multiple entries, it's good.
            # If there's only 1 or 2 entries for a long document, it's likely a fake TOC.
            if num_entries > 2 or (num_entries > 0 and num_pages <= 3):
                is_useful_toc = True

        if is_useful_toc:
            return self._chunk_by_toc(doc, toc, source_id)

        # Try heuristics (font-size based)
        heuristic_chunks = self._chunk_by_heuristics(doc, source_id)
        if heuristic_chunks:
            return heuristic_chunks

        return self._chunk_by_page(doc, source_id)

    def _chunk_by_toc(
        self, doc: Any, toc: List[List[Any]], source_id: str
    ) -> List[Chunk]:
        """
        Chunks the document based on the Table of Contents hierarchy.
        toc format: [[level, title, page_number], ...]
        """
        chunks = []

        # Build hierarchy breadcrumbs
        # E.g. [1, "Intro", 1] -> path: "Intro"
        #      [2, "Background", 1] -> path: "Intro -> Background"

        current_path = []

        for i, item in enumerate(toc):
            level, title, page_num = item[:3]
            page_idx = (
                page_num - 1
            )  # PyMuPDF pages are 1-indexed in TOC, 0-indexed in API

            # Adjust current path based on level (1-indexed depth)
            if level <= len(current_path):
                current_path = current_path[: level - 1]
            current_path.append(title)

            signature_path = " -> ".join(current_path)

            # Determine end page for this section by looking at the next TOC item
            end_page_idx = doc.page_count - 1
            if i + 1 < len(toc):
                next_page_num = toc[i + 1][2]
                end_page_idx = next_page_num - 1

            # Extract text from page_idx to end_page_idx
            # Note: A real implementation might need to split individual pages if multiple
            # headings start on the same page. For this first iteration, we'll extract
            # the full pages covering the section range to ensure no data loss.
            section_text = []
            for p in range(page_idx, end_page_idx + 1):
                page = doc.load_page(p)
                # Ensure we only add text once if multiple headings share a page
                # This simplistic approach will duplicate text if multiple TOC items share a page.
                # A robust approach filters text blocks by y-coordinates.
                # For v1, we gather all text on the starting page.
                if p == page_idx:
                    section_text.append(page.get_text())
                elif p > page_idx and p < end_page_idx:
                    section_text.append(page.get_text())

            combined_text = "\n".join(section_text).strip()

            if combined_text:
                self._add_chunks_with_splitting(
                    chunks=chunks,
                    content=combined_text,
                    source_id=source_id,
                    symbol_name=title,
                    signature=signature_path,
                    start_page=page_num,
                    end_page=end_page_idx + 1,
                    base_idx=f"toc_{i}",
                )

        return chunks

    def _chunk_by_heuristics(self, doc: Any, source_id: str) -> List[Chunk]:
        """
        Detects headings based on dynamic font size heuristics.
        Returns empty list if no headers are detected to allow fallback.
        """
        # --- Step 1: Calculate dynamic header threshold ---
        font_sizes = []
        scan_pages = min(doc.page_count, 5)  # Scan up to first 5 pages
        for page_num in range(scan_pages):
            page = doc.load_page(page_num)
            blocks = page.get_text("dict")["blocks"]
            for b in blocks:
                if "lines" not in b:
                    continue
                # Basic filter: only consider blocks with enough text to be body text
                text_len = sum(
                    len(s["text"]) for line in b["lines"] for s in line["spans"]
                )
                if text_len > 20:
                    for line in b["lines"]:
                        for s in line["spans"]:
                            font_sizes.append(round(s["size"]))

        # Most common font size is likely the body text
        if font_sizes:
            from collections import Counter

            body_font_size = Counter(font_sizes).most_common(1)[0][0]
            header_min_size = body_font_size + 1.0
        else:
            header_min_size = 14.0  # Safe fallback

        # --- Step 2: Extract chunks using the dynamic threshold ---
        chunks = []
        current_header = "Document Start"
        current_content = []
        current_start_page = 1
        headers_found = 0

        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            blocks = page.get_text("dict")["blocks"]

            for b in blocks:
                if "lines" not in b:
                    continue

                block_text = ""
                max_font_size = 0

                for line in b["lines"]:
                    for s in line["spans"]:
                        block_text += s["text"]
                        max_font_size = max(max_font_size, s["size"])

                block_text = block_text.strip()
                if not block_text:
                    continue

                # Heuristic 1: Ignore short numeric blocks (likely page numbers)
                if block_text.isdigit() and len(block_text) <= 3:
                    continue

                if max_font_size >= header_min_size and len(block_text) < 120:
                    # Flush previous chunk
                    if current_content:
                        combined = "\n".join(current_content).strip()
                        if combined:
                            self._add_chunks_with_splitting(
                                chunks=chunks,
                                content=combined,
                                source_id=source_id,
                                symbol_name=current_header,
                                signature=f"Heuristic -> {current_header}",
                                start_page=current_start_page,
                                end_page=page_num + 1,
                                base_idx=f"h_{headers_found}",
                            )

                    # Start new section
                    current_header = block_text
                    current_content = []
                    current_start_page = page_num + 1
                    headers_found += 1
                else:
                    current_content.append(block_text)

        # If only one header (likely just the title) or no headers were found,
        # return empty to trigger a more granular page-by-page fallback.
        if headers_found <= 1:
            return []

        # Flush last chunk
        if current_content:
            combined = "\n".join(current_content).strip()
            if combined:
                self._add_chunks_with_splitting(
                    chunks=chunks,
                    content=combined,
                    source_id=source_id,
                    symbol_name=current_header,
                    signature=f"Heuristic -> {current_header}",
                    start_page=current_start_page,
                    end_page=doc.page_count,
                    base_idx=f"h_{headers_found}",
                )

        return chunks

    def _add_chunks_with_splitting(
        self,
        chunks: List[Chunk],
        content: str,
        source_id: str,
        symbol_name: str,
        signature: str,
        start_page: int,
        end_page: int,
        base_idx: str,
    ) -> None:
        """Splits content if it exceeds MAX_CHUNK_CHARS and appends to chunks list."""
        if len(content) <= self.MAX_CHUNK_CHARS:
            chunks.append(
                Chunk(
                    content=content,
                    chunk_type=ChunkType.MARKDOWN_SECTION,
                    metadata=ChunkMetadata(
                        source_id=source_id,
                        chunk_index=base_idx,
                        start_line=start_page,
                        end_line=end_page,
                        symbol_name=symbol_name,
                        signature=signature,
                        language="pdf",
                    ),
                    hash=hashlib.md5(content.encode()).hexdigest(),
                )
            )
            return

        # Split into sub-chunks
        parts = []
        remaining = content
        while len(remaining) > self.MAX_CHUNK_CHARS:
            split_at = remaining.rfind("\n", 0, self.MAX_CHUNK_CHARS)
            if split_at == -1:
                split_at = self.MAX_CHUNK_CHARS
            parts.append(remaining[:split_at].strip())
            remaining = remaining[split_at:].strip()
        if remaining:
            parts.append(remaining)

        for i, part in enumerate(parts):
            chunks.append(
                Chunk(
                    content=part,
                    chunk_type=ChunkType.MARKDOWN_SECTION,
                    metadata=ChunkMetadata(
                        source_id=source_id,
                        chunk_index=f"{base_idx}.{i}",
                        start_line=start_page,
                        end_line=end_page,
                        symbol_name=symbol_name,
                        signature=signature,
                        language="pdf",
                    ),
                    hash=hashlib.md5(part.encode()).hexdigest(),
                )
            )

    def _create_chunk(
        self,
        content: str,
        source_id: str,
        symbol: str,
        start: int,
        end: int,
        existing_chunks: List[Chunk],
    ) -> Chunk:
        """Helper to create a Chunk object. (Deprecated in favor of _add_chunks_with_splitting)"""
        return Chunk(
            content=content,
            chunk_type=ChunkType.MARKDOWN_SECTION,
            metadata=ChunkMetadata(
                source_id=source_id,
                chunk_index=f"h_{len(existing_chunks)}",
                start_line=start,
                end_line=end,
                symbol_name=symbol,
                signature=f"Heuristic -> {symbol}",
                language="pdf",
            ),
            hash=hashlib.md5(content.encode()).hexdigest(),
        )

    def _chunk_by_page(self, doc: Any, source_id: str) -> List[Chunk]:
        """Fallback: chunk page by page if no structure is found."""
        chunks = []
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            text = page.get_text().strip()

            if text:
                self._add_chunks_with_splitting(
                    chunks=chunks,
                    content=text,
                    source_id=source_id,
                    symbol_name=f"Page {page_num + 1}",
                    signature=f"Document -> Page {page_num + 1}",
                    start_page=page_num + 1,
                    end_page=page_num + 1,
                    base_idx=str(page_num),
                )
        return chunks
