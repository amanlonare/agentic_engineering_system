from abc import ABC, abstractmethod
from typing import List, Optional

from .schemas import Chunk


class BaseEngine(ABC):
    """Abstract base class for all chunking engines (Python, MD, PDF, etc)."""

    @abstractmethod
    def chunk(self, content: str, source_id: str, **kwargs) -> List[Chunk]:
        """Process raw content into a list of structured Chunks."""


class SmartChunker:
    """
    Main entry point for the Smart Chunker library.
    It routes content to the appropriate engine based on format.
    """

    def __init__(self, engines: Optional[dict] = None):
        self.engines = engines or {}

    def register_engine(self, name: str, engine: BaseEngine):
        self.engines[name] = engine

    def chunk(
        self, content: str, source_id: str, chunk_format: str, **kwargs
    ) -> List[Chunk]:
        engine = self.engines.get(chunk_format)
        if not engine:
            raise ValueError(f"No engine registered for format: {chunk_format}")
        return engine.chunk(content, source_id, **kwargs)
