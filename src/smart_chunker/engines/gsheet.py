import hashlib
import json
from typing import Any, Dict, List

from ..base import BaseEngine
from ..schemas import Chunk, ChunkMetadata, ChunkType


class GSheetEngine(BaseEngine):
    """
    Engine for chunking Google Sheets based on the detailed 'Grid Data' JSON structure.
    Expects a dictionary representing the Google Sheets API response.
    """

    MAX_CHUNK_CHARS = 4000

    def chunk(self, content: Any, source_id: str, **kwargs) -> List[Chunk]:
        if isinstance(content, str):
            try:
                sheet_data = json.loads(content)
            except json.JSONDecodeError:
                # If it's not valid JSON, treat it as a file path
                try:
                    with open(content, "r", encoding="utf-8") as f:
                        sheet_data = json.load(f)
                except Exception as e:
                    raise ValueError(f"Failed to parse Google Sheet JSON: {e}")
        elif isinstance(content, dict):
            sheet_data = content
        else:
            raise ValueError(
                "Google Sheets content must be a JSON string or a dictionary."
            )

        return self._chunk_sheets(sheet_data, source_id)

    def _chunk_sheets(self, data: Dict[str, Any], source_id: str) -> List[Chunk]:
        chunks = []
        # Support both full Spreadsheet response and single sheet response
        sheets = data.get("sheets", [data]) if "sheets" in data else [data]

        for sheet_idx, sheet in enumerate(sheets):
            props = sheet.get("properties", {})
            sheet_name = props.get("title", f"Sheet{sheet_idx + 1}")

            for grid_idx, grid_data in enumerate(sheet.get("data", [])):
                row_data = grid_data.get("rowData", [])
                if not row_data:
                    continue

                headers = self._detect_headers(row_data)
                self._process_rows(
                    row_data=row_data,
                    headers=headers,
                    sheet_name=sheet_name,
                    source_id=source_id,
                    chunks=chunks,
                    base_idx=f"gsheet_{sheet_idx}_{grid_idx}",
                )

        return chunks

    def _extract_cell_text(self, cell: Dict[str, Any]) -> str:
        """Extracts the formatted text value from a cell dictionary."""
        return cell.get("formattedValue", "").strip()

    def _is_bold(self, cell: Dict[str, Any]) -> bool:
        """Checks if a cell has bold formatting."""
        format_data = cell.get("effectiveFormat", {}).get("textFormat", {})
        return format_data.get("bold", False)

    def _detect_headers(self, row_data: List[Dict[str, Any]]) -> List[str]:
        """
        Scans the first few rows to heuristically find the best header row.
        Looks for the row with the most text columns, prioritizing bold text.
        """
        best_headers = []
        max_score = -1

        # Scan up to the first 5 rows
        scan_limit = min(5, len(row_data))
        for i in range(scan_limit):
            row = row_data[i]
            cells = row.get("values", [])

            headers = [self._extract_cell_text(cell) for cell in cells]

            # Score: dense text (+1) + bold text (+2)
            score = 0
            for cell, text in zip(cells, headers):
                if text:
                    score += 1
                    if self._is_bold(cell):
                        score += 2

            # We want a row that actually has multiple columns defined
            if score > max_score and len([h for h in headers if h]) > 1:
                max_score = score
                best_headers = headers

        return best_headers

    def _process_rows(
        self,
        row_data: List[Dict[str, Any]],
        headers: List[str],
        sheet_name: str,
        source_id: str,
        chunks: List[Chunk],
        base_idx: str,
    ):
        current_chunk_content = []
        current_chunk_size = 0
        current_row_start = 1

        # We process row by row
        for row_idx, row in enumerate(row_data, start=1):
            cells = row.get("values", [])

            # Skip completely empty rows in serialization
            extracted_cells = [self._extract_cell_text(c) for c in cells]
            if not any(extracted_cells):
                continue

            # Serialize row
            serialized_parts = []
            for col_idx, text in enumerate(extracted_cells):
                if not text:
                    continue
                # Use header if available, otherwise col letter (A, B, C...)
                header_name = (
                    headers[col_idx]
                    if col_idx < len(headers) and headers[col_idx]
                    else f"Col {chr(65 + (col_idx % 26))}"
                )
                serialized_parts.append(f"{header_name}: {text}")

            row_str = f"[Row {row_idx}] " + " | ".join(serialized_parts) + "\n"
            row_size = len(row_str)

            # If adding this row exceeds limit, flush current chunk
            if (
                current_chunk_size + row_size > self.MAX_CHUNK_CHARS
                and current_chunk_content
            ):
                self._flush_chunk(
                    chunks=chunks,
                    content="".join(current_chunk_content),
                    source_id=source_id,
                    sheet_name=sheet_name,
                    start_row=current_row_start,
                    end_row=row_idx - 1,
                    base_idx=base_idx,
                )
                current_chunk_content = []
                current_chunk_size = 0
                current_row_start = row_idx

            # If a single row is massive, we must split it
            if row_size > self.MAX_CHUNK_CHARS:
                # Force flush whatever we have
                if current_chunk_content:
                    self._flush_chunk(
                        chunks=chunks,
                        content="".join(current_chunk_content),
                        source_id=source_id,
                        sheet_name=sheet_name,
                        start_row=current_row_start,
                        end_row=row_idx - 1,
                        base_idx=base_idx,
                    )
                    current_chunk_content = []
                    current_chunk_size = 0

                # Split the massive row
                self._split_massive_row(
                    row_str=row_str,
                    chunks=chunks,
                    source_id=source_id,
                    sheet_name=sheet_name,
                    row_idx=row_idx,
                    base_idx=base_idx,
                )
                current_row_start = row_idx + 1
            else:
                current_chunk_content.append(row_str)
                current_chunk_size += row_size

        # Flush remaining
        if current_chunk_content:
            self._flush_chunk(
                chunks=chunks,
                content="".join(current_chunk_content),
                source_id=source_id,
                sheet_name=sheet_name,
                start_row=current_row_start,
                end_row=len(row_data),
                base_idx=base_idx,
            )

    def _flush_chunk(
        self,
        chunks: List[Chunk],
        content: str,
        source_id: str,
        sheet_name: str,
        start_row: int,
        end_row: int,
        base_idx: str,
    ):
        idx = len(chunks)
        chunks.append(
            Chunk(
                content=content.strip(),
                chunk_type=ChunkType.MARKDOWN_SECTION,  # Using markdown section for general text blocks
                metadata=ChunkMetadata(
                    source_id=source_id,
                    chunk_index=f"{base_idx}_{idx}",
                    symbol_name=sheet_name,
                    signature=f"{sheet_name} (Rows {start_row}-{end_row})",
                    language="gsheet",
                ),
                hash=hashlib.md5(content.encode()).hexdigest(),
            )
        )

    def _split_massive_row(
        self,
        row_str: str,
        chunks: List[Chunk],
        source_id: str,
        sheet_name: str,
        row_idx: int,
        base_idx: str,
    ):
        """Splits a single extremely long row string into multiple chunks."""
        parts = []
        remaining = row_str
        while len(remaining) > self.MAX_CHUNK_CHARS:
            split_at = remaining.rfind(" | ", 0, self.MAX_CHUNK_CHARS)
            if split_at == -1:
                split_at = remaining.rfind(" ", 0, self.MAX_CHUNK_CHARS)
            if split_at == -1:
                split_at = self.MAX_CHUNK_CHARS

            parts.append(remaining[:split_at].strip())
            # Skip the delimiter if we found one
            jump = 3 if remaining[split_at : split_at + 3] == " | " else 1
            remaining = remaining[split_at + jump :].strip()

        if remaining:
            parts.append(remaining)

        for i, part in enumerate(parts):
            idx = len(chunks)
            chunks.append(
                Chunk(
                    content=part,
                    chunk_type=ChunkType.MARKDOWN_SECTION,
                    metadata=ChunkMetadata(
                        source_id=source_id,
                        chunk_index=f"{base_idx}_{idx}_split{i}",
                        symbol_name=sheet_name,
                        signature=f"{sheet_name} (Row {row_idx} pt{i + 1})",
                        language="gsheet",
                    ),
                    hash=hashlib.md5(part.encode()).hexdigest(),
                )
            )
