"""
VectorDB utilities for long-term semantic memory.
This module manages ChromaDB to index and retrieve past successful solutions or docs.
"""

import os
from typing import Any, Dict, List, Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from src.core.config import settings
from src.utils.logger import configure_logging

# Ensure OpenAI API Key is available in the environment for LangChain components
if settings.OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

logger = configure_logging()


class LongTermMemory:
    """
    Manages long-term semantic memory for the agents using ChromaDB.
    """

    def __init__(
        self,
        collection_name: str = "engineering_memory",
        persist_directory: str = "./long_term_memory",
    ):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.embeddings = OpenAIEmbeddings()

        try:
            self.vector_store = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory,
            )
            logger.info("💾 Long-term memory initialized: %s", self.collection_name)
        except Exception as e:
            logger.error("Failed to initialize ChromaDB: %s", e)
            self.vector_store = None

    def store_memory(
        self, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Saves a memory (e.g., successful task plan, bug fix) into the index.
        """
        if not self.vector_store:
            return False

        try:
            doc = Document(page_content=content, metadata=metadata or {})
            self.vector_store.add_documents([doc])
            logger.debug("Memory stored: %s...", content[:50])
            return True
        except Exception as e:
            logger.error("Failed to store memory: %s", e)
            return False

    def retrieve_relevant_memories(self, query: str, k: int = 3) -> List[Document]:
        """
        Retrieves the top-k most relevant memories based on the query.
        """
        if not self.vector_store:
            return []

        try:
            docs = self.vector_store.similarity_search(query, k=k)
            logger.debug(
                "Retrieved %d relevant memories for query: %s", len(docs), query
            )
            return docs
        except Exception as e:
            logger.error("Failed to retrieve memory: %s", e)
            return []
