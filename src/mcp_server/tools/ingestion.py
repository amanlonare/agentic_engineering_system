import logging

from ..server import mcp, pipeline

logger = logging.getLogger(__name__)


@mcp.tool()
async def index_source(source_url: str) -> str:
    """
    Index a new data source (GitHub URL, Google Doc, or local path).
    Note: Performing a full index may take several minutes for large repos.
    """
    try:
        logger.info("Starting ingestion for: %s", source_url)
        chunks = await pipeline.process(source_url)
        return f"✅ Successfully indexed {source_url}. Generated {len(chunks)} context chunks."
    except Exception as e:
        logger.error("Ingestion failed: %s", e)
        return f"❌ Ingestion failed for {source_url}: {str(e)}"
