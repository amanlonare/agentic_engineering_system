import logging
import sys
import warnings

from src.mcp_server.server import mcp
from src.utils.logger import configure_logging

# Save original stdout to restore it later for the MCP protocol
original_stdout = sys.stdout

# Redirect all current stdout to stderr to catch initialization noise
sys.stdout = sys.stderr

# Suppress annoying library warnings and telemetry banners
warnings.filterwarnings("ignore", category=FutureWarning)
logging.getLogger("chromadb.telemetry").setLevel(logging.ERROR)

logger = configure_logging()


@mcp.tool()
async def health_check() -> str:
    """Check the health and status of the Smart Context MCP server."""
    return "🚀 Smart Context MCP Server is healthy and connected to Knowledge Engines."


if __name__ == "__main__":
    try:
        logger.info("Starting Smart Context MCP Server (Modular)...")

        # CRITICAL: Restore stdout before running the server
        # MCP stdio transport MUST use the original stdout for JSON-RPC
        sys.stdout = original_stdout

        mcp.run()
    except Exception as e:
        # If we fail here, ensure we log to stderr (logger handles this)
        # We use a backup print to stderr just in case logger fails
        sys.stderr.write(f"\n❌ CRITICAL CRASH: MCP Server failed to start: {str(e)}\n")
        sys.stderr.flush()
        logger.critical("MCP Server failed to start: %s", e, exc_info=True)
        sys.exit(1)
