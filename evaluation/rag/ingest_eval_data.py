import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from src.ingestion.pipeline import IngestionPipeline

from src.core.config import settings

import argparse


async def ingest_eval(source_url: str | None = None):
    """
    Ingests data from YAML sources or a specific URL for evaluation.
    """
    from src.core.vector_store import VectorStore
    from src.core.graph_store import GraphStore

    pipeline = IngestionPipeline(
        vector_store=VectorStore(
            db_path=settings.EVAL_CHROMA_DB_PATH,
            collection_name=settings.EVAL_CHROMA_COLLECTION_NAME,
        ),
        graph_store=GraphStore(db_path=settings.EVAL_KUZU_DB_PATH),
    )

    try:
        sources = []
        if source_url:
            sources = [source_url]
        else:
            # Load from YAML if no specific URL provided
            sources = pipeline.load_sources_from_yaml(settings.INGESTION_SOURCES_FILE)
            if not sources:
                print(f"⚠️ No sources found in {settings.INGESTION_SOURCES_FILE}")
                return

        for source in sources:
            print(f"🎬 Ingesting: {source}")
            try:
                chunks = await pipeline.process(source)
                print(f"✅ Successfully ingested: {source} ({len(chunks)} chunks)")
            except Exception as e:
                print(f"❌ Failed to ingest {source}: {e}")
                import traceback

                traceback.print_exc()

    finally:
        await pipeline.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest data for RAG evaluation.")
    parser.add_argument(
        "--url", type=str, help="Source URL to ingest (GitHub repo or Google Doc)"
    )
    args = parser.parse_args()

    asyncio.run(ingest_eval(args.url))
