import re
from pathlib import Path
from typing import Any, Dict

from src.core.config import settings
from src.ingestion.exceptions import IngestionConnectionError
from src.schemas.ingestion import IdentifiedSource, SourceType


class SourceFetcher:
    """Fetches raw content from identified sources."""

    def __init__(self):
        self.google_key_path = getattr(
            settings, "GOOGLE_SERVICE_ACCOUNT_JSON_PATH", None
        )

        # Resolve google key path
        if self.google_key_path:
            key_path = Path(self.google_key_path)
            if not key_path.is_absolute():
                key_path = Path.cwd().joinpath(self.google_key_path)
            self.google_key_path = str(key_path)

    def fetch(self, identified_source: IdentifiedSource) -> Any:
        """Fetches content based on the source type."""

        if identified_source.source_type == SourceType.PDF_FILE:
            # For PDFs, we just return the path string as the "content"
            # because PdfEngine takes the file path directly.
            return identified_source.identifier

        elif identified_source.source_type == SourceType.GOOGLE_DOC:
            return self._fetch_google_doc(identified_source.identifier)

        elif identified_source.source_type == SourceType.GOOGLE_SHEET:
            return self._fetch_google_sheet(identified_source.identifier)

        elif identified_source.source_type == SourceType.GITHUB_REPO:
            return self._fetch_github_repo(identified_source.identifier)

        elif identified_source.source_type == SourceType.SLACK_CONVERSATION:
            raise NotImplementedError("Slack fetching is not fully implemented yet.")

        else:
            raise ValueError(f"Unknown source type: {identified_source.source_type}")

    def _get_github_headers(self) -> Dict[str, str]:
        github_token = getattr(settings, "GITHUB_TOKEN", None)
        headers = {"Accept": "application/vnd.github.v3+json"}
        if github_token:
            headers["Authorization"] = f"token {github_token}"
        return headers

    def _fetch_github_repo(self, url: str) -> list:
        """
        Fetches the repository file tree and downloads supported files.
        Returns a list of dicts: [{"path": str, "content": str, "url": str}]
        """
        import base64
        from urllib.parse import urlparse

        import requests

        parsed = urlparse(url)
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) < 2:
            raise ValueError(f"Invalid GitHub URL: {url}")

        owner, repo = path_parts[0], path_parts[1]
        headers = self._get_github_headers()

        # We need a branch. We'll query repo details to get default_branch.
        repo_api_url = f"https://api.github.com/repos/{owner}/{repo}"
        repo_resp = requests.get(repo_api_url, headers=headers, timeout=10)
        repo_resp.raise_for_status()
        default_branch = repo_resp.json().get("default_branch", "main")

        # 1. Fetch the recursive tree
        tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
        tree_resp = requests.get(tree_url, headers=headers, timeout=15)
        tree_resp.raise_for_status()
        tree_data = tree_resp.json()

        if "tree" not in tree_data:
            raise IngestionConnectionError(f"No tree found for {owner}/{repo}")

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
        # TODO: Add .dart and .swift in the future when custom tree-sitter grammars are compiled.
        files_to_fetch = []

        for item in tree_data["tree"]:
            if item["type"] == "blob":
                path = item["path"]
                ext = Path(path).suffix.lower()

                # Exclude common noise
                if any(
                    x in path
                    for x in [
                        "node_modules/",
                        "venv/",
                        ".git/",
                        ".vscode/",
                        "dist/",
                        "build/",
                    ]
                ):
                    continue

                if ext in supported_extensions:
                    files_to_fetch.append(item)

        results = []
        for file_item in files_to_fetch:
            # Fetch contents using the blob URL (avoids size limits of the contents API for base64)
            blob_url = file_item["url"]
            blob_resp = requests.get(blob_url, headers=headers, timeout=10)
            if blob_resp.status_code == 200:
                blob_data = blob_resp.json()
                content = blob_data.get("content", "")
                encoding = blob_data.get("encoding", "")

                if encoding == "base64":
                    try:
                        decoded_content = base64.b64decode(content).decode("utf-8")
                        results.append(
                            {
                                "path": file_item["path"],
                                "content": decoded_content,
                                "url": f"https://github.com/{owner}/{repo}/blob/{default_branch}/{file_item['path']}",
                            }
                        )
                    except Exception as e:
                        print(f"DEBUG: Failed to decode {file_item['path']}: {e}")
                else:
                    print(
                        f"DEBUG: Unsupported encoding {encoding} for {file_item['path']}"
                    )
            else:
                print(
                    f"DEBUG: Failed to fetch blob {file_item['path']}. Status: {blob_resp.status_code}"
                )

        return results

    def _extract_google_file_id(self, url: str) -> str:
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

    def _fetch_google_doc(self, url: str) -> Dict[str, Any]:
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

    def _fetch_google_sheet(self, url: str) -> Dict[str, Any]:
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
