import asyncio
import logging
from typing import Optional

from src.core.graph_store import GraphStore
from src.core.memory import LongTermMemory
from src.core.resource_manager import ResourceManager

logger = logging.getLogger(__name__)


class IngestionManager:
    """
    Handles on-demand ingestion of remote repositories and documents.
    Seeds the VectorStore and GraphStore for dynamic discovery.
    """

    def __init__(self):
        self.resource_manager = ResourceManager()
        self.memory = LongTermMemory(collection_name="workspace_context")
        self.graph_store = GraphStore()

    async def ingest_remote_repo(
        self, repo_url: str, repo_name: Optional[str] = None, deep_index: bool = True
    ) -> str:
        """
        Ingests search-optimized metadata (README, structure) from a remote GitHub repo.
        """
        if not repo_name:
            # Extract name from URL: https://github.com/owner/repo -> repo
            repo_name = repo_url.rstrip("/").split("/")[-1]

        logger.info(f"🚀 Ingesting remote repository: {repo_name} ({repo_url})")

        mcp_prefix = f"mcp://github/{repo_url.replace('https://github.com/', '')}"

        # 1. Fetch README for semantic discovery
        readme_content = ""
        possible_readmes = ["README.md", "readme.md", "README", "docs/index.md"]

        for p in possible_readmes:
            try:
                uri = f"{mcp_prefix}/{p}"
                readme_content = await self.resource_manager.read_resource(uri)
                if readme_content:
                    logger.info(f"Found README at {p}")
                    break
            except Exception:
                continue

        if not readme_content:
            readme_content = (
                f"Repository: {repo_name}\nURL: {repo_url}\n(No README found)"
            )

        # 2. Index in VectorStore for discovery
        self.memory.store_memory(
            content=readme_content,
            metadata={
                "repo_name": repo_name,
                "type": "workspace_context",
                "source": "remote",
                "remote_url": repo_url,
                "mcp_uri": mcp_prefix,
            },
        )

        # 3. Add to GraphStore
        self.graph_store.conn.execute(
            "MERGE (r:Repository {name: $name}) SET r.remote_url = $url, r.type = 'github', r.mcp_uri = $mcp",
            {"name": repo_name, "url": repo_url, "mcp": mcp_prefix},
        )

        # 4. Deep Indexing via Smarter Chunker and Ephemeral Clone
        if deep_index:
            logger.info(
                "Starting deep indexing of %s via ephemeral clone...", repo_name
            )
            try:
                local_path = await self.resource_manager.ensure_local_context(
                    mcp_prefix
                )

                import os
                from pathlib import Path

                from src.core.vector_store import VectorStore
                from src.smart_chunker.base import SmartChunker
                from src.smart_chunker.engines.code import CodeEngine
                from src.smart_chunker.engines.markdown import MarkdownEngine

                chunker = SmartChunker()
                chunker.register_engine("python", CodeEngine("python"))
                chunker.register_engine("javascript", CodeEngine("javascript"))
                chunker.register_engine("typescript", CodeEngine("typescript"))
                chunker.register_engine("tsx", CodeEngine("tsx"))
                chunker.register_engine("java", CodeEngine("java"))
                chunker.register_engine("kotlin", CodeEngine("kotlin"))
                chunker.register_engine("markdown", MarkdownEngine())

                supported_exts = {
                    ".py": "python",
                    ".js": "javascript",
                    ".ts": "typescript",
                    ".tsx": "tsx",
                    ".jsx": "tsx",
                    ".md": "markdown",
                    ".java": "java",
                    ".kt": "kotlin",
                }

                all_chunks = []
                for root, _, files in os.walk(local_path):
                    if any(
                        ignored in root
                        for ignored in [".git", "node_modules", "venv", "__pycache__"]
                    ):
                        continue

                    for file in files:
                        ext = Path(file).suffix.lower()
                        if ext in supported_exts:
                            file_path = os.path.join(root, file)
                            relative_path = os.path.relpath(file_path, local_path)

                            try:
                                with open(file_path, "r", encoding="utf-8") as f:
                                    content = f.read()

                                format_name = supported_exts[ext]
                                file_mcp_uri = f"{mcp_prefix}/{relative_path}"

                                file_chunks = chunker.chunk(
                                    content,
                                    source_id=file_mcp_uri,
                                    chunk_format=format_name,
                                )
                                for c in file_chunks:
                                    if not c.metadata.custom_attributes:
                                        c.metadata.custom_attributes = {}
                                    c.metadata.custom_attributes["repo_name"] = (
                                        repo_name
                                    )
                                    c.metadata.custom_attributes["mcp_uri"] = (
                                        file_mcp_uri
                                    )

                                all_chunks.extend(file_chunks)
                            except Exception as e:
                                logger.debug(
                                    "Deep indexing failed on %s: %s", relative_path, e
                                )

                if all_chunks:
                    v_store = VectorStore()
                    v_store.upsert_chunks(all_chunks)
                    logger.info(
                        "Successfully deep-indexed %d chunks for %s.",
                        len(all_chunks),
                        repo_name,
                    )

            except Exception as e:
                logger.error("Deep indexing logic failed: %s", e)

        logger.info(f"✅ Successfully ingested {repo_name}")
        return repo_name

    async def ingest_gdrive_folder(self, folder_id: str, folder_name: str) -> str:
        """
        Ingests metadata for a Google Drive folder.
        """
        logger.info(f"🚀 Ingesting GDrive folder: {folder_name} ({folder_id})")

        mcp_uri = f"mcp://gdrive/{folder_id}"

        # Index description in VectorStore
        self.memory.store_memory(
            content=f"Google Drive Folder: {folder_name}\nContains project documentation and requirements.",
            metadata={
                "repo_name": folder_name,
                "type": "workspace_context",
                "source": "gdrive",
                "folder_id": folder_id,
                "mcp_uri": mcp_uri,
            },
        )

        # Add to GraphStore
        self.graph_store.conn.execute(
            "MERGE (r:Repository {name: $name}) SET r.remote_url = $url, r.type = 'gdrive', r.mcp_uri = $mcp",
            {
                "name": folder_name,
                "url": f"https://drive.google.com/drive/folders/{folder_id}",
                "mcp": mcp_uri,
            },
        )

        return folder_name


if __name__ == "__main__":
    # Quick test harness
    async def test():
        # Example: ingest this system's repo if it were remote
        # await IngestionManager().ingest_remote_repo("https://github.com/amanlonare/agentic_engineering_system")
        print("Ingestion logic ready.")

    asyncio.run(test())
