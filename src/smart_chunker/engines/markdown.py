import hashlib
import os
import re
from typing import Any, List, Union

from src.smart_chunker.base import BaseEngine
from src.smart_chunker.schemas import Chunk, ChunkMetadata, ChunkType


class MarkdownEngine(BaseEngine):
    """
    Chunking engine for Markdown documentation.
    Splits by headers (H1-H3) to maintain structural context.
    """

    def chunk(
        self, content: Union[str, dict, Any], source_id: str, **_kwargs
    ) -> List[Chunk]:
        if not isinstance(content, str):
            content = str(content)
        # Split by secondary headers (H1, H2, H3)
        # We look for lines starting with #, ##, or ###
        header_pattern = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)

        chunks = []
        last_pos = 0
        current_headers = ["", "", ""]  # H1, H2, H3

        # Initial chunk if content starts before the first header
        matches = list(header_pattern.finditer(content))

        if not matches:
            # No headers, treat as a single chunk named after the file
            doc_name = os.path.basename(source_id)
            return [
                Chunk(
                    content=content,
                    chunk_type=ChunkType.MARKDOWN_SECTION,
                    metadata=ChunkMetadata(
                        source_id=source_id,
                        chunk_index="0",
                        symbol_name=doc_name,
                        signature=doc_name,
                        language="markdown",
                    ),
                    hash=hashlib.md5(content.encode()).hexdigest(),
                )
            ]

        for i, match in enumerate(matches):
            # Extract content from previous header to this one
            if match.start() > last_pos:
                chunk_text = content[last_pos : match.start()].strip()
                if chunk_text:
                    path = " -> ".join([h for h in current_headers if h])
                    chunks.append(
                        self._create_chunk(
                            chunk_text, source_id, f"{len(chunks)}", path
                        )
                    )

            # Update current context
            level = len(match.group(1)) - 1
            current_headers[level] = match.group(2).strip()
            # Clear lower levels
            for j in range(level + 1, 3):
                current_headers[j] = ""

            last_pos = match.start()

            # If it's the last header, grab the rest of the file
            if i == len(matches) - 1:
                chunk_text = content[match.start() :].strip()
                path = " -> ".join([h for h in current_headers if h])
                chunks.append(
                    self._create_chunk(chunk_text, source_id, f"{len(chunks)}", path)
                )

        return chunks

    def _create_chunk(
        self, content: str, source_id: str, index: str, path: str
    ) -> Chunk:
        return Chunk(
            content=content,
            chunk_type=ChunkType.FUNCTION,  # Markdown blocks are treated as functional units
            metadata=ChunkMetadata(
                source_id=source_id,
                chunk_index=index,
                symbol_name=path.split(" -> ")[-1],
                signature=path,
                language="markdown",
            ),
            hash=hashlib.md5(content.encode()).hexdigest(),
        )
