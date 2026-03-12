import hashlib
import json
from typing import Any, Dict, List, Optional

from ..base import BaseEngine
from ..schemas import Chunk, ChunkMetadata, ChunkType


class GDocEngine(BaseEngine):
    """
    Engine for chunking Google Docs based on their native JSON structure.
    Expects a dictionary representing the Google Doc JSON (from the Docs API).
    """

    MAX_CHUNK_CHARS = 4000

    def chunk(self, content: Any, source_id: str, **kwargs) -> List[Chunk]:
        """
        Chunks a Google Doc JSON object.
        `content` can be a JSON string or a dictionary.
        """
        if isinstance(content, str):
            try:
                doc_data = json.loads(content)
            except json.JSONDecodeError:
                # If it's not valid JSON, treat it as a file path to load
                try:
                    with open(content, "r", encoding="utf-8") as f:
                        doc_data = json.load(f)
                except Exception as e:
                    raise ValueError(f"Failed to parse Google Doc JSON: {e}")
        elif isinstance(content, dict):
            doc_data = content
        else:
            raise ValueError(
                "Google Docs content must be a JSON string or a dictionary."
            )

        return self._chunk_hierarchically(doc_data, source_id)

    def _chunk_hierarchically(self, doc: Dict[str, Any], source_id: str) -> List[Chunk]:
        chunks = []
        body = doc.get("body", {})
        content_items = body.get("content", [])

        current_hierarchy = ["Document Start"]
        current_section_content = []

        # Mapping for heading levels to hierarchy index
        # 1-indexed for HEADING_1, etc.
        def get_heading_level(style_type: str) -> Optional[int]:
            if style_type.startswith("HEADING_"):
                try:
                    return int(style_type.split("_")[1])
                except (ValueError, IndexError):
                    return None
            return None

        # Helper to flush current section
        def flush_section():
            if current_section_content:
                text = "".join(current_section_content).strip()
                if text:
                    symbol_name = current_hierarchy[-1]
                    signature = " -> ".join(current_hierarchy)

                    self._add_chunks_with_splitting(
                        chunks=chunks,
                        content=text,
                        source_id=source_id,
                        symbol_name=symbol_name,
                        signature=signature,
                        base_idx=f"gdoc_{len(chunks)}",
                    )
                current_section_content.clear()

        for item in content_items:
            # Handle Paragraphs (Text, Headings, Lists)
            if "paragraph" in item:
                para = item["paragraph"]
                style = para.get("paragraphStyle", {}).get(
                    "namedStyleType", "NORMAL_TEXT"
                )

                # Extract text elements
                para_text = ""
                for element in para.get("elements", []):
                    if "textRun" in element:
                        para_text += element["textRun"].get("content", "")

                level = get_heading_level(style)
                if level is not None:
                    # It's a heading
                    flush_section()

                    # Adjust hierarchy
                    # Ensure we have enough levels. If level is 1, hierarchy should have 2 items (Doc Start, H1)
                    # We keep "Document Start" as base.
                    new_hierarchy = current_hierarchy[:level]
                    new_hierarchy.append(para_text.strip())
                    current_hierarchy = new_hierarchy
                else:
                    # Normal text or list item
                    # Check for list markers if needed, but simple extraction first
                    current_section_content.append(para_text)

            # Handle Tables (Simple text extraction for now)
            elif "table" in item:
                table_text = "\n[Table Start]\n"
                for row in item["table"].get("tableRows", []):
                    row_cells = []
                    for cell in row.get("tableCells", []):
                        cell_text = ""
                        for cell_content in cell.get("content", []):
                            if "paragraph" in cell_content:
                                for element in cell_content["paragraph"].get(
                                    "elements", []
                                ):
                                    if "textRun" in element:
                                        cell_text += element["textRun"].get(
                                            "content", ""
                                        )
                        row_cells.append(cell_text.strip())
                    table_text += " | ".join(row_cells) + "\n"
                table_text += "[Table End]\n"
                current_section_content.append(table_text)

        # Final flush
        flush_section()

        return chunks

    def _add_chunks_with_splitting(
        self,
        chunks: List[Chunk],
        content: str,
        source_id: str,
        symbol_name: str,
        signature: str,
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
                        symbol_name=symbol_name,
                        signature=signature,
                        language="gdoc",
                    ),
                    hash=hashlib.md5(content.encode()).hexdigest(),
                )
            )
            return

        # Split into sub-chunks
        parts = []
        remaining = content
        while len(remaining) > self.MAX_CHUNK_CHARS:
            # Try splitting by newline first
            split_at = remaining.rfind("\n", 0, self.MAX_CHUNK_CHARS)

            # If no newline, try splitting by period or full-width period (CJK)
            if split_at == -1:
                period_at = remaining.rfind(".", 0, self.MAX_CHUNK_CHARS)
                cjk_period_at = remaining.rfind("。", 0, self.MAX_CHUNK_CHARS)
                split_at = max(period_at, cjk_period_at)

            # Fallback to hard limit
            if split_at == -1 or split_at < self.MAX_CHUNK_CHARS // 2:
                split_at = self.MAX_CHUNK_CHARS

            parts.append(remaining[: split_at + 1].strip())
            remaining = remaining[split_at + 1 :].strip()
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
                        symbol_name=symbol_name,
                        signature=signature,
                        language="gdoc",
                    ),
                    hash=hashlib.md5(part.encode()).hexdigest(),
                )
            )
