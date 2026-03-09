import re
from pathlib import Path
from urllib.parse import urlparse

import requests

from src.core.config import settings
from src.ingestion.exceptions import (
    IngestionConnectionError,
    UnauthorizedSourceError,
    UnsupportedSourceError,
)
from src.schemas.ingestion import IdentifiedSource, SourceType


class SourceIdentifier:
    """ Identifies and verifies data sources for ingestion."""

    def __init__(self):
        self.github_token = settings.GITHUB_TOKEN
        self.google_key_path = getattr(settings, "GOOGLE_SERVICE_ACCOUNT_JSON_PATH", None)
        self.slack_token = getattr(settings, "SLACK_BOT_TOKEN", None)

    def identify(self, source: str) -> IdentifiedSource:
        """Determines the type of source from a URL, path, or ID."""
        source = source.strip()

        # 1. GitHub Repository
        if self._is_github(source):
            return IdentifiedSource(
                source_type=SourceType.GITHUB_REPO,
                identifier=source,
                is_verified=self._verify_github(source)
            )

        # 2. Google Docs / Sheets
        if "docs.google.com" in source:
            if "/document/" in source:
                return IdentifiedSource(
                    source_type=SourceType.GOOGLE_DOC,
                    identifier=source,
                    is_verified=self._verify_google(source)
                )
            elif "/spreadsheets/" in source:
                return IdentifiedSource(
                    source_type=SourceType.GOOGLE_SHEET,
                    identifier=source,
                    is_verified=self._verify_google(source)
                )

        # 3. PDF File
        if source.lower().endswith(".pdf") or Path(source).is_file():
            if source.lower().endswith(".pdf"):
                return IdentifiedSource(
                    source_type=SourceType.PDF_FILE,
                    identifier=source,
                    is_verified=Path(source).exists()
                )

        # 4. Slack (Simplified detection for Phase 1)
        if re.match(r"^[C|D|G][A-Z0-9]{8,11}$", source):
            return IdentifiedSource(
                source_type=SourceType.SLACK_CONVERSATION,
                identifier=source,
                is_verified=self._verify_slack(source)
            )

        raise UnsupportedSourceError(f"Could not identify source: {source}")

    def _is_github(self, source: str) -> bool:
        parsed = urlparse(source)
        return "github.com" in parsed.netloc or Path(source).joinpath(".git").exists()

    def _verify_github(self, source: str) -> bool:
        """Lightweight health check for GitHub access."""
        if not self.github_token:
            return False
        
        # Extract owner/repo from URL
        parsed = urlparse(source)
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) < 2:
            return False
        
        owner, repo = path_parts[0], path_parts[1]
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        headers = {"Authorization": f"token {self.github_token}"}
        
        try:
            response = requests.get(api_url, headers=headers, timeout=10)
            if response.status_code == 200:
                return True
            elif response.status_code == 401 or response.status_code == 403:
                raise UnauthorizedSourceError(f"Unauthorized access to GitHub repo: {source}")
            return False
        except requests.RequestException as e:
            raise IngestionConnectionError(f"Failed to connect to GitHub API: {str(e)}") from e

    def _verify_google(self, source: str) -> bool:
        """Check if Google credentials are configured and have access to the source."""
        if not self.google_key_path:
            return False

        # Resolve relative path if necessary
        key_path = Path(self.google_key_path)
        if not key_path.is_absolute():
            # Try relative to current working directory (usually project root)
            # or could use a more robust way to find the project root
            key_path = Path.cwd().joinpath(self.google_key_path)

        if not key_path.exists():
            print(f"DEBUG: Google key file not found at {key_path}")
            return False

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            # Load credentials from service account JSON
            scopes = ["https://www.googleapis.com/auth/drive.readonly"]
            creds = service_account.Credentials.from_service_account_file(
                str(key_path), scopes=scopes
            )

            # Extract File ID from URL
            match = re.search(r"/d/([a-zA-Z0-9-_]+)", source)
            if not match:
                return False
            file_id = match.group(1)

            # Use Drive API to check file existence and access
            service = build("drive", "v3", credentials=creds)
            # pylint: disable=no-member
            service.files().get(fileId=file_id, fields="name").execute()
            return True

        except Exception as e:
            print(f"DEBUG: Google Verification Failed for {source}: {str(e)}")
            return False

    def _verify_slack(self, _source: str) -> bool:
        """Check if Slack token is configured (Verification logic added in Phase 2)."""
        return bool(self.slack_token)
