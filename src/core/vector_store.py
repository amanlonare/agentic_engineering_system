import logging
import os
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.utils import embedding_functions

from src.core.config import settings
from src.smart_chunker.schemas import Chunk

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Wrapper for ChromaDB Vector Database to store semantic embeddings.
    """

    def __init__(
        self,
        db_path: str = "long_term_memory/vector",
        collection_name: str = "kb_chunks",
    ):
        # Ensure the directory exists
        os.makedirs(db_path, exist_ok=True)

        self.client = chromadb.PersistentClient(path=db_path)

        # Use OpenAI if key is available, else default to local embeddings
        if settings.OPENAI_API_KEY:
            self.embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
                api_key=settings.OPENAI_API_KEY, model_name="text-embedding-3-small"
            )
        else:
            logger.warning("OPENAI_API_KEY not found. Using default local embeddings.")
            self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn,  # type: ignore
        )

    def upsert_chunks(self, chunks: List[Chunk]):
        """
        Idempotently adds or updates chunks in the collection.
        """
        if not chunks:
            return

        ids = []
        documents = []
        metadatas = []

        for chunk in chunks:
            # Create a unique ID: doc_path#index
            chunk_id = f"{chunk.metadata.source_id}#{chunk.metadata.chunk_index}"

            # Prepare metadata (flattening complex types)
            meta = {
                "source_id": chunk.metadata.source_id,
                "chunk_index": chunk.metadata.chunk_index,
                "chunk_type": chunk.chunk_type.value,
                "language": chunk.metadata.language or "unknown",
                "symbol_name": chunk.metadata.symbol_name or "unknown",
                "signature": chunk.metadata.signature or "",
                "parent_symbol": chunk.metadata.parent_symbol or "",
            }

            ids.append(chunk_id)
            documents.append(chunk.content)
            metadatas.append(meta)

        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        logger.info(f"Successfully upserted {len(chunks)} chunks to ChromaDB.")

    def search_chunks(self, query: str, n_results: int = 5) -> Any:
        """
        Performs semantic search across all chunks.
        """
        return self.collection.query(query_texts=[query], n_results=n_results)

    def search_relevant_repos(self, query: str, n_results: int = 10) -> List[str]:
        """
        Finds unique source_ids (repositories/sources) related to the query.
        Step 1 of the Hybrid Retrieval Flow.
        """
        results = self.collection.query(query_texts=[query], n_results=n_results)

        source_ids = set()
        if results and "metadatas" in results and results["metadatas"]:
            for meta_list in results["metadatas"]:
                for meta in meta_list:
                    if "source_id" in meta:
                        source_ids.add(meta["source_id"])

        return list(source_ids)

    def search_chunks_filtered(
        self, query: str, filters: Optional[Dict[str, Any]] = None, n_results: int = 5
    ) -> Any:
        """
        Performs semantic search with optional metadata filters.
        Filters use ChromaDB's 'where' syntax, e.g. {"language": "python"}.
        """
        kwargs: Dict[str, Any] = {
            "query_texts": [query],
            "n_results": n_results,
        }
        if filters:
            kwargs["where"] = filters
        return self.collection.query(**kwargs)

    def get_chunk_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single chunk by its ID.
        Returns a dict with 'content' and 'metadata', or None.
        """
        try:
            result = self.collection.get(
                ids=[chunk_id], include=["documents", "metadatas"]
            )
            if result and result["documents"] and len(result["documents"]) > 0:
                return {
                    "content": result["documents"][0],
                    "metadata": result["metadatas"][0] if result["metadatas"] else {},
                }
        except Exception as e:
            logger.warning("Failed to get chunk %s: %s", chunk_id, e)
        return None
