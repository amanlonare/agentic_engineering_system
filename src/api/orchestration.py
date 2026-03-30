import asyncio
import json
import uuid
import yaml
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, cast

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from src.core.graph import build_graph
from src.core.state import EngineeringState
from src.schemas import TriggerContext
from src.utils.logger import configure_logging, ui_log_queue

logger = configure_logging("orchestration")
router = APIRouter()

class SourceItem(BaseModel):
    """Represents a single data source for ingestion/execution."""
    id: str
    url: str
    type: str = Field(..., description="'repo', 'doc', or 'sheet'")

class IngestRequest(BaseModel):
    """Payload for bulk-ingesting multiple sources."""
    sources: List[SourceItem]

    # Credentials (in case they are needed for ingestion)
    github_token: Optional[str] = None
    google_service_account_json: Optional[str] = None

class ExecuteRequest(BaseModel):
    """Payload for executing a new agentic engineering task via the UI."""
    query: str = Field(..., description="The user's goal or task description.")
    sources: List[SourceItem] = Field(default_factory=list, description="List of sources to act on.")
    repo_url: Optional[str] = Field(None, description="Legacy field for single repo URL.")

    # Mode & Model Selection
    mode: str = Field("standard", description="'standard' (defaults) or 'custom' (user keys).")
    provider: str = Field("openai", description="'openai' or 'bedrock'")
    model: str = Field("gpt-4o", description="The specific LLM model ID.")

    # Ephemeral Credentials
    openai_api_key: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: Optional[str] = "us-east-1"
    github_token: Optional[str] = None
    google_service_account_json: Optional[str] = None

async def event_generator(request_data: ExecuteRequest) -> AsyncGenerator[str, None]:
    """Streams logs and completion events back to the UI via SSE."""
    log_queue = asyncio.Queue()

    # Set the queue in the context so the logger can find it
    token = ui_log_queue.set(log_queue)

    try:
        # 1. Yield initial heartbeat/ack
        yield f"data: {json.dumps({'type': 'status', 'content': 'Initializing session...'})}\n\n"

        # 2. Build the graph
        graph = build_graph()

        # 3. Prepare initial state
        thread_id = str(uuid.uuid4())
        repo_name = request_data.repo_url.split("/")[-1].replace(".git", "") if request_data.repo_url else "generic"
        
        trigger = TriggerContext(
            type="manual",
            repo_name=request_data.sources[0].url.split("/")[-1].replace(".git", "") if request_data.sources else "generic",
            payload={"query": request_data.query, "sources": [s.dict() for s in request_data.sources]}
        )

        initial_state = EngineeringState(
            messages=[HumanMessage(content=request_data.query)],
            trigger=trigger,
            is_lightweight=False,
            is_env_rework=False
        )

        # 4. Prepare Configuration Overrides for Nodes
        config = cast(RunnableConfig, {
            "configurable": {
                "thread_id": thread_id,
                "llm_provider": request_data.provider,
                "llm_model": request_data.model,
                "openai_api_key": request_data.openai_api_key,
                "aws_access_key_id": request_data.aws_access_key_id,
                "aws_secret_access_key": request_data.aws_secret_access_key,
                "aws_region": request_data.aws_region,
                "github_token": request_data.github_token,
                "google_service_account_json": request_data.google_service_account_json,
            },
            "metadata": {
                "ui_session_id": thread_id,
                "user_query": request_data.query
            }
        })

        # 5. Run the graph in a background task so we can stream logs simultaneously
        graph_task = asyncio.create_task(graph.ainvoke(initial_state, config=config))
        
        # 6. Stream logs from the queue while the task is running
        while not graph_task.done():
            try:
                # Wait for logs with a timeout to allow checking task status
                log_entry = await asyncio.wait_for(log_queue.get(), timeout=0.1)
                yield f"data: {json.dumps({'type': 'log', 'content': log_entry})}\n\n"
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error yielding log: {e}")
                break

        # 7. Check final result
        try:
            final_state = await graph_task
            yield f"data: {json.dumps({'type': 'complete', 'content': 'Task finished successfully.'})}\n\n"
            # Optionally yield the final summary from the state
            if final_state.get("messages"):
                last_msg = final_state["messages"][-1]
                content = getattr(last_msg, "content", str(last_msg))
                yield f"data: {json.dumps({'type': 'summary', 'content': content})}\n\n"
        except Exception as e:
            logger.exception("Graph execution failed")
            yield f"data: {json.dumps({'type': 'error', 'content': f'Execution failed: {str(e)}'})}\n\n"

    finally:
        # Cleanup context
        ui_log_queue.reset(token)
        yield "event: close\ndata: {}\n\n"

@router.post("/execute")
async def execute_task(request: ExecuteRequest):
    """
    Triggers a new engineering task and returns an SSE stream for real-time monitoring.
    """
    logger.info(f"Received execution request. Mode: {request.mode}, Query: {request.query[:50]}...")
    return StreamingResponse(
        event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        }
    )

async def ingestion_generator(request_data: IngestRequest) -> AsyncGenerator[str, None]:
    """Streams ingestion progress back to the UI."""
    log_queue = asyncio.Queue()
    token = ui_log_queue.set(log_queue)

    try:
        from src.core.workspace import WorkspaceManager
        wm = WorkspaceManager()
        
        yield f"data: {json.dumps({'type': 'log', 'content': '🚀 Initialization: Preparing ingestion pipeline...'})}\n\n"
        await asyncio.sleep(0.4)

        for source in request_data.sources:
            yield f"data: {json.dumps({'type': 'log', 'content': f'📥 [Source] {source.type.upper()}: Connecting to {source.url}'})}\n\n"
            await asyncio.sleep(0.3)
            
            if source.type == 'repo':
                yield f"data: {json.dumps({'type': 'log', 'content': '🔍 Analyzing repository structure and branch metadata...'})}\n\n"
                await asyncio.sleep(0.5)
                yield f"data: {json.dumps({'type': 'log', 'content': '🌳 Building semantic context graph for symbols and dependencies...'})}\n\n"
                await asyncio.sleep(0.7)
            else:
                yield f"data: {json.dumps({'type': 'log', 'content': '🧬 Parsing document content and extracting key entities...'})}\n\n"
                await asyncio.sleep(0.5)
                yield f"data: {json.dumps({'type': 'log', 'content': '🛰️ Generating embeddings for vector memory...'})}\n\n"
                await asyncio.sleep(0.6)

            # Actual work with credentials passthrough
            await wm.bulk_ingest(
                [source.dict()],
                github_token=request_data.github_token,
                google_service_account_json=request_data.google_service_account_json,
            )
            yield f"data: {json.dumps({'type': 'log', 'content': f'✅ Successfully indexed context from {source.url}'})}\n\n"
            await asyncio.sleep(0.2)

        yield f"data: {json.dumps({'type': 'log', 'content': '✨ Long-term memory synchronization complete.'})}\n\n"
        yield f"data: {json.dumps({'type': 'complete', 'content': 'Context ingestion finished.'})}\n\n"

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        yield f"data: {json.dumps({'type': 'error', 'content': f'Ingestion failed: {str(e)}'})}\n\n"
    finally:
        ui_log_queue.reset(token)
        yield "event: close\ndata: {}\n\n"

@router.post("/ingest")
async def ingest_sources(request: IngestRequest):
    """
    Triggers bulk ingestion of repositories and documents.
    """
    logger.info(f"Received ingestion request for {len(request.sources)} sources.")
    return StreamingResponse(
        ingestion_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        }
    )

@router.get("/sources")
async def get_ingested_sources():
    """Returns the list of repositories currently indexed in the GraphStore."""
    from src.core.workspace import WorkspaceManager
    wm = WorkspaceManager()
    
    # Query for repositories
    repos = wm.graph_store.execute_query("MATCH (r:Repository) RETURN r.name, r.remote_url")
    
    sources = []
    for r in repos:
        sources.append({
            "id": r[0],
            "url": r[1],
            "type": "repo"
        })
        
    return {"sources": sources, "count": len(sources)}

@router.get("/config/sources")
async def get_configured_sources():
    """Returns the list of repositories and docs defined in ingestion_sources.yaml."""
    # Robust path resolution relative to project root
    base_path = Path(__file__).parent.parent.parent
    sources_path = base_path / "ingestion_sources.yaml"
    
    if not sources_path.exists():
        logger.warning(f"⚠️ Configuration file not found at {sources_path}")
        return {"sources": [], "count": 0}
        
    try:
        with open(sources_path, "r") as f:
            config = yaml.safe_load(f)
            
        sources = []
        # Parse repositories
        for url in config.get("repositories", []):
            sources.append({
                "id": f"config-{url.split('/')[-1]}",
                "url": url,
                "type": "repo"
            })
        # Parse documents
        for url in config.get("google_docs", []):
            sources.append({
                "id": f"config-{url.split('/')[-1]}",
                "url": url,
                "type": "doc"
            })
            
        return {"sources": sources, "count": len(sources)}
    except Exception as e:
        logger.error(f"Failed to read configured sources: {e}")
        return {"sources": [], "count": 0}
