import json
from pathlib import Path
from typing import Any, Dict

from mcp.types import TextContent

from src.core.config import settings
from src.ingestion.exceptions import IngestionConnectionError
from src.schemas.ingestion import IdentifiedSource, SourceType


class SourceFetcher:
    """Fetches raw content from identified sources."""

    def __init__(self, mcp_manager=None):
        from src.core.mcp_client import MCPClientManager

        self.mcp_manager = mcp_manager or MCPClientManager()
        self.google_key_path = getattr(
            settings, "GOOGLE_SERVICE_ACCOUNT_JSON_PATH", None
        )

        # Resolve google key path
        if self.google_key_path:
            key_path = Path(self.google_key_path)
            if not key_path.is_absolute():
                key_path = Path.cwd().joinpath(self.google_key_path)
            self.google_key_path = str(key_path)

    async def fetch(self, identified_source: IdentifiedSource) -> Any:
        """Fetches content based on the source type."""

        if identified_source.source_type == SourceType.PDF_FILE:
            # For PDFs, we just return the path string as the "content"
            # because PdfEngine takes the file path directly.
            return identified_source.identifier

        elif identified_source.source_type == SourceType.GOOGLE_DOC:
            return await self._fetch_google_doc(identified_source.identifier)

        elif identified_source.source_type == SourceType.GOOGLE_SHEET:
            return await self._fetch_google_sheet(identified_source.identifier)

        elif identified_source.source_type == SourceType.GITHUB_REPO:
            return await self._fetch_github_repo(identified_source.identifier)

        elif identified_source.source_type == SourceType.SLACK_CONVERSATION:
            raise NotImplementedError("Slack fetching is not fully implemented yet.")

        elif identified_source.source_type == SourceType.LOCAL_DIR:
            return await self._fetch_local_dir(identified_source.identifier)

        else:
            raise ValueError(f"Unknown source type: {identified_source.source_type}")

    async def _fetch_local_dir(self, dir_path: str) -> list:
        """
        Scans a local directory and returns a list of supported files.
        """
        results = []
        base_path = Path(dir_path)
        supported_extensions = {
            ".py",
            ".md",
            ".ipynb",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".java",
            ".kt",
        }

        for p in base_path.rglob("*"):
            if p.is_file() and p.suffix.lower() in supported_extensions:
                # Exclude noise
                if any(
                    x in str(p) for x in ["node_modules", "venv", ".git", "__pycache__"]
                ):
                    continue

                try:
                    with open(p, "r", encoding="utf-8") as f:
                        results.append(
                            {
                                "path": str(p.relative_to(base_path)),
                                "content": f.read(),
                                "url": str(
                                    p.absolute()
                                ),  # Using path as URL for local files
                            }
                        )
                except Exception as e:
                    print(f"DEBUG: Failed to read local file {p}: {e}")

        return results

    async def _fetch_github_repo(self, url: str) -> list:
        """
        Fetches the repository file tree and downloads supported files using GitHub MCP.
        Returns a list of dicts: [{"path": str, "content": str, "url": str}]
        """
        from urllib.parse import urlparse

        parsed = urlparse(url)
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) < 2:
            raise ValueError(f"Invalid GitHub URL: {url}")

        owner, repo = path_parts[0], path_parts[1]
        # Strip .git extension if present for the MCP tool call
        if repo.lower().endswith(".git"):
            repo = repo[:-4]

        # Ensure GitHub MCP is connected
        if "github" not in self.mcp_manager.sessions:
            cmd_str = str(settings.GITHUB_MCP_COMMAND)
            cmd_parts = cmd_str.split()
            await self.mcp_manager.connect_stdio("github", cmd_parts[0], cmd_parts[1:])

        session = self.mcp_manager.sessions["github"]

        # 1. Recursive helper using the get_file_contents MCP tool
        results = []
        supported_extensions = {
            ".py",
            ".md",
            ".ipynb",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".java",
            ".kt",
        }

        async def recurse(path: str):
            try:
                resp = await session.call_tool(
                    "get_file_contents", {"owner": owner, "repo": repo, "path": path}
                )

                # Ensure we have TextContent
                content_item = resp.content[0]
                if not isinstance(content_item, TextContent):
                    print(
                        f"DEBUG: Unexpected non-text content from GitHub MCP for {path}"
                    )
                    return

                data = json.loads(content_item.text)

                if isinstance(data, list):
                    # Directory listing
                    for item in data:
                        # Exclude noise
                        item_path = item["path"]
                        if any(
                            x in item_path
                            for x in [
                                "node_modules/",
                                "venv/",
                                ".git/",
                                ".vscode/",
                                "dist/",
                                "build/",
                                "__pycache__/",
                            ]
                        ):
                            continue

                        if item["type"] == "dir":
                            await recurse(item_path)
                        elif item["type"] == "file":
                            ext = Path(item_path).suffix.lower()
                            if ext in supported_extensions:
                                # Fetch individual file content
                                file_resp = await session.call_tool(
                                    "get_file_contents",
                                    {"owner": owner, "repo": repo, "path": item_path},
                                )
                                file_content_item = file_resp.content[0]
                                if isinstance(file_content_item, TextContent):
                                    file_data = json.loads(file_content_item.text)
                                    results.append(
                                        {
                                            "path": item_path,
                                            "content": file_data["content"],
                                            "url": f"https://github.com/{owner}/{repo}/blob/main/{item_path}",
                                        }
                                    )
                else:
                    # Single file content (unlikely at root, but possible if path points to a file)
                    results.append(
                        {
                            "path": path,
                            "content": data["content"],
                            "url": f"https://github.com/{owner}/{repo}/blob/main/{path}",
                        }
                    )
            except Exception as e:
                print(f"DEBUG: Error fetching {path} via MCP: {e}")

        await recurse("")
        return results

    def _extract_google_file_id(self, url: str) -> str:
        import re

        match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
        if not match:
            raise ValueError(f"Could not extract file ID from URL: {url}")
        return match.group(1)

    def _get_google_creds(self, scopes: list):
        if not self.google_key_path or not Path(self.google_key_path).exists():
            raise ValueError(
                f"Google Service Account key not found at {self.google_key_path}"
            )

        from google.oauth2 import service_account

        return service_account.Credentials.from_service_account_file(
            self.google_key_path, scopes=scopes
        )

    async def _fetch_google_doc(self, url: str) -> Dict[str, Any]:
        """Fetches the Google Doc JSON representation."""

        file_id = self._extract_google_file_id(url)
        creds = self._get_google_creds(
            ["https://www.googleapis.com/auth/documents.readonly"]
        )

        try:
            from googleapiclient.discovery import build

            service = build("docs", "v1", credentials=creds)
            # pylint: disable=no-member
            document = service.documents().get(documentId=file_id).execute()
            return document
        except Exception as e:
            raise IngestionConnectionError(f"Failed to fetch Google Doc: {e}") from e

    async def _fetch_google_sheet(self, url: str) -> Dict[str, Any]:
        """Fetches the Google Sheet grid data JSON."""
        file_id = self._extract_google_file_id(url)
        creds = self._get_google_creds(
            ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        )

        try:
            from googleapiclient.discovery import build

            service = build("sheets", "v4", credentials=creds)
            # pylint: disable=no-member
            sheet = (
                service.spreadsheets()
                .get(spreadsheetId=file_id, includeGridData=True)
                .execute()
            )
            return sheet
        except Exception as e:
            raise IngestionConnectionError(f"Failed to fetch Google Sheet: {e}") from e
