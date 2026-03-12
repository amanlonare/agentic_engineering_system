from typing import Any, Dict, List, Optional

from src.core.vector_store import VectorStore
from src.utils.logger import configure_logging

logger = configure_logging()


class LongTermMemory:
    """
    Manages long-term semantic memory for the agents using the unified VectorStore.
    Keeps legacy data in a separate collection to avoid collisions with the knowledge base.
    """

    def __init__(
        self,
        collection_name: str = "engineering_memory",
        persist_directory: str = "long_term_memory/vector",
    ):
        self.collection_name = collection_name
        self.vector_store = VectorStore(
            db_path=persist_directory, collection_name=collection_name
        )
        logger.info("💾 Unified Long-term memory initialized: %s", self.collection_name)

    def store_memory(
        self, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Saves a memory into the specified collection.
        """
        try:
            # We wrap the content in a mock behavior to match the old API
            # but using the new VectorStore upsert logic
            import hashlib

            from src.smart_chunker.schemas import Chunk, ChunkMetadata, ChunkType

            content_hash = hashlib.md5(content.encode()).hexdigest()

            # Create a pseudo-chunk for the legacy storage
            chunk = Chunk(
                content=content,
                chunk_type=ChunkType.TEXT_PARA,
                hash=content_hash,
                metadata=ChunkMetadata(
                    source_id=(
                        metadata.get("repo_name", "legacy_memory")
                        if metadata
                        else "legacy_memory"
                    ),
                    chunk_index="0",  # String required by schema
                    language="text",
                ),
            )
            # Add extra metadata to custom_attributes instead of direct attributes
            if metadata:
                chunk.metadata.custom_attributes.update(metadata)

            self.vector_store.upsert_chunks([chunk])
            logger.debug("Memory stored: %s...", content[:50])
            return True
        except Exception as e:
            logger.error("Failed to store memory: %s", e)
            return False

    def retrieve_relevant_memories(self, query: str, k: int = 3) -> List[Any]:
        """
        Retrieves relevant memories.
        Returns objects with page_content and metadata to maintain compatibility.
        """
        try:
            results = self.vector_store.search_chunks(query, n_results=k)
            docs = []

            if results and "documents" in results and results["documents"]:
                for i in range(len(results["documents"][0])):
                    content = results["documents"][0][i]
                    metadata = results["metadatas"][0][i]

                    # Create a compatibility object (mocking LangChain Document)
                    class CompatibilityDoc:
                        def __init__(self, content, metadata):
                            self.page_content = content
                            self.metadata = metadata

                    docs.append(CompatibilityDoc(content, metadata))

            return docs
        except Exception as e:
            logger.error("Failed to retrieve memory: %s", e)
            return []
