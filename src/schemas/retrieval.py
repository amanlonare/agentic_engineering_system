"""
Schemas for the Advanced Retrieval module.
"""

from typing import List

from pydantic import BaseModel, Field


class RetrievedContext(BaseModel):
    """A single piece of retrieved context, enriched with graph information."""

    content: str = Field(..., description="The text content of the chunk.")
    source_id: str = Field(..., description="The originating file or document path.")
    chunk_id: str = Field("", description="Unique chunk identifier (source_id#index).")
    symbol_name: str = Field(
        "", description="The symbol name (function/class) if applicable."
    )
    chunk_type: str = Field(
        "", description="The type of chunk (function, class, text_para, etc)."
    )
    language: str = Field("unknown", description="The programming language or 'text'.")
    score: float = Field(
        0.0, description="Combined relevance score (lower is better for distance)."
    )
    graph_depth: int = Field(
        0, description="0 = direct hit, 1+ = discovered via graph traversal."
    )
    related_symbols: List[str] = Field(
        default_factory=list, description="Symbols related via graph edges."
    )


class RetrievalResult(BaseModel):
    """The full result of a retrieval query."""

    query: str = Field(..., description="The original query.")
    contexts: List[RetrievedContext] = Field(
        default_factory=list, description="Ranked list of retrieved contexts."
    )
    sources_searched: int = Field(0, description="Number of unique sources involved.")
    graph_expanded: bool = Field(False, description="Whether graph expansion was used.")
