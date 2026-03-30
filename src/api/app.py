import asyncio
import yaml
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, TypedDict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.api.webhooks import router as webhooks_router
from src.api.orchestration import router as orchestration_router
from src.core.config import settings
from src.core.workspace import WorkspaceManager
from src.utils.logger import configure_logging

logger = configure_logging()


class AppState(TypedDict):
    """Type definition for the shared application state."""

    graph: Any
    workspace_manager: WorkspaceManager
    memory: Any


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for FastAPI.
    Sets up expensive components (DB, embedding models, Graph) ONCE at boot,
    making them available to all requests via dependency injection.
    """
    logger.info("🚀 Booting API Server... Initializing singletons.")

    # 1. Initialize DB Memory
    logger.info("📡 Connecting to Checkpoint DB...")

    # We create the generic SqliteSaver without passing a connection object directly
    # The SqliteSaver from_conn_string requires entering its context to set up tables
    # Sync context managers inside asynccontextmanagers can be tricky.
    # Instead, we will instantiate it dynamically per request in the dependency.
    # Instead, we will initialize the connection manually here so the graph can use it.

    # For SqliteSaver, the standard pattern in LangGraph is a context manager.
    # To share it across requests safely without holding a transaction open forever,
    # we'll let LangGraph manage it per-invocation, or we'll open it here.
    # Let's use the DB path directly in a way that is thread-safe.
    # Actually, we will just pass the path to a factory when we need it,
    # but for WorkspaceManager we initialize it once.

    # 2. Initialize WorkspaceManager (this loads embeddings if needed)
    logger.info("📂 Initializing WorkspaceManager...")
    workspace_manager = WorkspaceManager()
    
    # 3. Automatic Context Ingestion (if missing)
    if not workspace_manager.is_ingested():
        sources_path = Path("ingestion_sources.yaml")
        if sources_path.exists():
            try:
                with open(sources_path, "r") as f:
                    config = yaml.safe_load(f)
                    
                sources = []
                # Transform YAML formats to the flat source list expected by WorkspaceManager
                for repo_url in config.get("repositories", []):
                    sources.append({"url": repo_url, "type": "repo"})
                for doc_url in config.get("google_docs", []):
                    sources.append({"url": doc_url, "type": "doc"})

                if sources:
                    logger.info("🚀 Starting mandatory context ingestion of %d sources...", len(sources))
                    await workspace_manager.bulk_ingest(sources)
                    logger.info("✅ Initial context ingestion complete. Application is now starting up.")
            except Exception as e:
                logger.error("Failed to read ingestion_sources.yaml for auto-ingestion: %s", e)
    
    # Attach to app state so dependencies can find it
    app.state.workspace_manager = workspace_manager

    yield

    logger.info("🛑 Shutting down API Server... Cleaning up.")
    # Add cleanup logic here if necessary


def create_app() -> FastAPI:
    """Factory function to create and configure the FastAPI application."""
    app = FastAPI(
        title="Agentic Engineering API",
        description="Webhooks and external integrations for the Agentic Framework.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS configuration to allow external consumers (like local UIs)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Routers
    app.include_router(webhooks_router, prefix="/api/webhooks", tags=["Webhooks"])
    app.include_router(orchestration_router, prefix="/api/orchestration", tags=["Orchestration"])

    @app.get("/health", tags=["System"])
    async def health_check(request: Request):
        """Basic health check endpoint."""
        workspace_manager = getattr(request.app.state, "workspace_manager", None)
        workspace_ready = workspace_manager is not None
        context_ingested = workspace_manager.is_ingested() if workspace_ready else False
        
        return {
            "status": "ok",
            "service": "agentic-engineering-api",
            "workspace_ready": workspace_ready,
            "context_ingested": context_ingested,
        }

    return app
