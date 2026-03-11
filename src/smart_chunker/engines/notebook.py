import json
from typing import List

from src.smart_chunker.base import BaseEngine
from src.smart_chunker.engines.python_ast import PythonEngine
from src.smart_chunker.schemas import Chunk


class NotebookEngine(BaseEngine):
    """
    Chunking engine for Jupyter Notebooks (.ipynb).
    Extracts code cells and hands them over to the Python AST engine.
    """

    def __init__(self):
        self.python_engine = PythonEngine()

    def chunk(self, content: str, source_id: str, **_kwargs) -> List[Chunk]:
        try:
            nb = json.loads(content)
        except json.JSONDecodeError:
            return []

        chunks = []
        cell_idx = 0

        for cell in nb.get("cells", []):
            if cell.get("cell_type") == "code":
                cell_content = "".join(cell.get("source", []))
                if not cell_content.strip():
                    continue

                # Use Python engine to extract symbols from this cell
                cell_id = f"{source_id}#cell_{cell_idx}"
                cell_chunks = self.python_engine.chunk(cell_content, cell_id, **_kwargs)

                # Add cell-specific metadata
                for c in cell_chunks:
                    c.metadata.chunk_index = f"{cell_idx}.{c.metadata.chunk_index}"
                    chunks.append(c)

                cell_idx += 1

        return chunks
