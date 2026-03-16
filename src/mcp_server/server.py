from mcp.server.fastmcp import FastMCP

from src.core.context_retriever import ContextRetriever
from src.ingestion.pipeline import IngestionPipeline
from src.utils.logger import configure_logging

__all__ = ["mcp", "retriever", "pipeline", "logger"]

# Specialized logger for MCP operations (stderr-safe)
logger = configure_logging("mcp_server")

# Initialize the FastMCP server
mcp = FastMCP("Smart Context Gateway")

# Shared engine instances
retriever = ContextRetriever()
pipeline = IngestionPipeline()
