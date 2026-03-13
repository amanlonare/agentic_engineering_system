import os
import sys

# Add src to path
sys.path.append(os.getcwd())

from src.ingestion.pipeline import IngestionPipeline
from src.core.graph_store import GraphStore
from src.core.vector_store import VectorStore
from src.core.config import settings

def ingest_eval_data():
    """Points the pipeline at our dummy evaluation repos."""
    print("🚀 Starting Isolated Ingestion for Evaluation Data...")
    print(f"   ChromaDB Collection : {settings.EVAL_CHROMA_COLLECTION_NAME}")
    print(f"   Kuzu DB Path        : {settings.EVAL_KUZU_DB_PATH}")
    
    # Isolate Vector Store (uses named eval settings)
    vector_store = VectorStore(
        db_path=settings.EVAL_CHROMA_DB_PATH,
        collection_name=settings.EVAL_CHROMA_COLLECTION_NAME
    )
    
    # Isolate Graph Store (uses named eval settings)
    graph_store = GraphStore(db_path=settings.EVAL_KUZU_DB_PATH)
    
    pipeline = IngestionPipeline(vector_store=vector_store, graph_store=graph_store)

    eval_repos = [
        "evaluation/test_data/core_lib",
        "evaluation/test_data/service_api",
        "evaluation/test_data/web_app"
    ]

    for repo in eval_repos:
        repo_abs = os.path.abspath(repo)
        print(f"📦 Indexing repo: {repo}")
        # Note: In our current local implementation, we can pass local paths
        pipeline.process(repo_abs)

    print("✅ Ingestion complete. Ready for Ragas.")

if __name__ == "__main__":
    ingest_eval_data()
