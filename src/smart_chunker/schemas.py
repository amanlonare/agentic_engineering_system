from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChunkType(str, Enum):
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    MODULE = "module"
    MARKDOWN_SECTION = "markdown_section"
    NOTEBOOK_CELL = "notebook_cell"
    TEXT_PARA = "text_paragraph"
    SHEET_BLOCK = "sheet_block"


class ChunkMetadata(BaseModel):
    """Metadata for a single chunk, designed to be modular and agnostic."""

    source_id: str  # File path, URL, or ID
    chunk_index: str  # Supports hierarchical (e.g., "1.0", "1.1")
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    symbol_name: Optional[str] = None  # function or class name
    signature: Optional[str] = None  # line of definition
    language: Optional[str] = None  # python, dart, php, etc.
    parent_symbol: Optional[str] = None  # For inheritance/hierarchy
    dependencies: List[str] = Field(default_factory=list)
    custom_attributes: Dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    """The atomic unit of data produced by the Smart Chunker."""

    content: str
    chunk_type: ChunkType
    metadata: ChunkMetadata
    hash: str  # For staleness detection
