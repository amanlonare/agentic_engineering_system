from pathlib import Path
from typing import List, Optional

import yaml

from src.core.graph_store import GraphStore
from src.core.vector_store import VectorStore
from src.ingestion.fetcher import SourceFetcher
from src.ingestion.identifier import SourceIdentifier
from src.schemas.ingestion import SourceType
from src.smart_chunker.base import SmartChunker
from src.smart_chunker.engines.code import CodeEngine
from src.smart_chunker.engines.gdoc import GDocEngine
from src.smart_chunker.engines.gsheet import GSheetEngine
from src.smart_chunker.engines.markdown import MarkdownEngine
from src.smart_chunker.engines.notebook import NotebookEngine
from src.smart_chunker.engines.pdf import PdfEngine
from src.smart_chunker.schemas import Chunk


class IngestionPipeline:
    """Orchestrates source identification, fetching, and chunking."""

    @staticmethod
    def load_sources_from_yaml(file_path: str) -> List[str]:
        """Loads source URLs from a YAML file."""
        path = Path(file_path)
        if not path.exists():
            return []

        with open(path, "r") as f:
            data = yaml.safe_load(f)

        if not data:
            return []

        sources = []
        # Flatten all sections (repositories, google_docs, urls) into a single list
        for section in ["repositories", "google_docs", "urls"]:
            if section in data and isinstance(data[section], list):
                sources.extend(data[section])

        return sources

    def __init__(
        self,
        chunker: Optional[SmartChunker] = None,
        graph_store: Optional[GraphStore] = None,
        vector_store: Optional[VectorStore] = None,
    ):
        self.identifier = SourceIdentifier()
        self.fetcher = SourceFetcher()
        self.graph_store = graph_store or GraphStore()
        self.vector_store = vector_store or VectorStore()

        if chunker:
            self.chunker = chunker
        else:
            self.chunker = SmartChunker()
            self.chunker.register_engine("python", CodeEngine("python"))
            self.chunker.register_engine("javascript", CodeEngine("javascript"))
            self.chunker.register_engine("typescript", CodeEngine("typescript"))
            self.chunker.register_engine("tsx", CodeEngine("tsx"))
            self.chunker.register_engine("markdown", MarkdownEngine())
            self.chunker.register_engine("notebook", NotebookEngine())
            self.chunker.register_engine("pdf", PdfEngine())
            self.chunker.register_engine("gdoc", GDocEngine())
            self.chunker.register_engine("gsheet", GSheetEngine())

    async def close(self):
        """Clean up resources like MCP connections."""
        if hasattr(self.fetcher, "mcp_manager"):
            await self.fetcher.mcp_manager.disconnect_all()

    def _map_source_to_engine(self, source_type: SourceType) -> str:
        """Maps an internal SourceType to the appropriate chunk engine format name."""
        mapping = {
            SourceType.GOOGLE_DOC: "gdoc",
            SourceType.GOOGLE_SHEET: "gsheet",
            SourceType.PDF_FILE: "pdf",
            # GitHub Repo maps individually per file extension later
        }
        if source_type not in mapping:
            raise ValueError(
                f"No default engine mapping for source type: {source_type}"
            )
        return mapping[source_type]

    async def process(self, source_url: str) -> List[Chunk]:
        """
        End-to-end processing pipeline:
        1. Identify the source.
        2. Fetch the raw content.
        3. Chunk the content using the appropriate engine.
        """
        # Step 1: Identify
        identified_source = self.identifier.identify(source_url)
        if not identified_source.is_verified:
            raise PermissionError(
                f"Cannot verify access to source: {source_url}. "
                "Check tokens/credentials."
            )

        # Step 2: Fetch
        raw_content = await self.fetcher.fetch(identified_source)

        # Step 3: Chunk
        repo_name = "Other Sources"  # Default fallback
        repo_type = "Unknown"

        if identified_source.source_type == SourceType.GITHUB_REPO:
            repo_type = "GitHub"
            from urllib.parse import urlparse

            parsed = urlparse(identified_source.identifier)
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 2:
                repo_name = f"{parts[0]}/{parts[1]}"
                if repo_name.endswith(".git"):
                    repo_name = repo_name[:-4]
        elif identified_source.source_type == SourceType.LOCAL_DIR:
            repo_type = "Local"
            repo_name = Path(identified_source.identifier).name
        elif identified_source.source_type == SourceType.GOOGLE_DOC:
            repo_type = "Google Drive"
            title = "Unknown Google Doc"
            if isinstance(raw_content, dict):
                title = raw_content.get("title", "Unknown Google Doc")
            repo_name = f"[GDoc] {title}"
        elif identified_source.source_type == SourceType.GOOGLE_SHEET:
            repo_type = "Google Drive"
            title = "Unknown Google Sheet"
            if isinstance(raw_content, dict):
                # Sheets API has title inside properties
                title = raw_content.get("properties", {}).get(
                    "title", "Unknown Google Sheet"
                )
            repo_name = f"[GSheet] {title}"

        if identified_source.source_type in [
            SourceType.GITHUB_REPO,
            SourceType.LOCAL_DIR,
        ]:
            # For repos or local dirs, raw_content is a list of file dicts: [{"path": str, "content": str, "url": str}]
            chunks = []
            for file_data in raw_content:
                ext = (
                    file_data["path"].split(".")[-1].lower()
                    if "." in file_data["path"]
                    else ""
                )

                # Determine engine based on extension
                if ext == "py":
                    engine_format = "python"
                elif ext == "js":
                    engine_format = "javascript"
                elif ext == "ts":
                    engine_format = "typescript"
                elif ext in ["jsx", "tsx"]:
                    engine_format = "tsx"
                elif ext == "java":
                    engine_format = "java"
                elif ext == "kt":
                    engine_format = "kotlin"
                elif ext == "md":
                    engine_format = "markdown"
                elif ext == "ipynb":
                    engine_format = "notebook"
                else:
                    continue  # Skip unsupported inside the loop just in case

                try:
                    file_chunks = self.chunker.chunk(
                        content=file_data["content"],
                        source_id=file_data["url"],
                        chunk_format=engine_format,
                    )

                    if repo_name:
                        for c in file_chunks:
                            c.metadata.custom_attributes["repo_name"] = repo_name

                    chunks.extend(file_chunks)
                except Exception as e:
                    print(f"DEBUG: Failed to chunk {file_data['path']}: {e}")

        else:
            engine_format = self._map_source_to_engine(identified_source.source_type)
            # Pass the identified source identifier (URL/path) as the source_id
            chunks = self.chunker.chunk(
                content=raw_content,
                source_id=identified_source.identifier,
                chunk_format=engine_format,
            )

        # Step 4: Index into Graph and Vector DB
        self.graph_store.upsert_source(identified_source)
        if repo_name:
            self.graph_store.upsert_repository(
                repo_name, identified_source.identifier, repo_type
            )
        self.graph_store.upsert_chunks(identified_source, chunks)
        self.vector_store.upsert_chunks(chunks)

        return chunks
