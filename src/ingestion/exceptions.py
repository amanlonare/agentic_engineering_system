class IngestionError(Exception):
    """Base exception for ingestion errors."""


class UnsupportedSourceError(IngestionError):
    """Raised when a source cannot be identified."""


class UnauthorizedSourceError(IngestionError):
    """Raised when access to a identified source is denied."""


class IngestionConnectionError(IngestionError):
    """Raised when a health check or connection to a source fails."""
