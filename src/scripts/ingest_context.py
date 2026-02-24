from src.core.workspace import WorkspaceManager
from src.utils.logger import configure_logging

logger = configure_logging()

def ingest():
    """
    Ingests all README files from the .context directory into ChromaDB.
    """
    logger.info("🎬 Starting workspace context ingestion...")
    wm = WorkspaceManager()
    wm.index_repositories()
    logger.info("✅ Ingestion complete.")

if __name__ == "__main__":
    ingest()
