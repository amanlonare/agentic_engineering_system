import asyncio
import logging
from src.core.ingestion import IngestionManager
from src.core.workspace import WorkspaceManager

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_ingestion")

async def test_remote_ingestion():
    """
    Test the full remote-first discovery flow:
    1. Ingest a remote repo metadata.
    2. Use WorkspaceManager to identify it.
    """
    ingestor = IngestionManager()
    workspace = WorkspaceManager()
    
    # We'll use a public repo as a test target
    repo_url = "https://github.com/amanlonare/agentic_engineering_system"
    repo_name = "agentic_engineering_system"
    
    logger.info("--- Step 1: Ingesting %s ---", repo_url)
    await ingestor.ingest_remote_repo(repo_url, repo_name)
    
    logger.info(f"--- Step 2: Testing Discovery ---")
    # A query that should match the README or name
    task = "I need to fix a bug in the agentic engineering system core logic."
    identified_repo = await workspace.identify_repository(task)
    
    logger.info("Result: Task '%s' matched to Repo: %s", task, identified_repo)
    
    if identified_repo == repo_name:
        logger.info(f"✅ SUCCESS: Remote repo identified correctly as {repo_name}!")
    else:
        logger.error("❌ FAILURE: Repo identification failed.")

if __name__ == "__main__":
    asyncio.run(test_remote_ingestion())
