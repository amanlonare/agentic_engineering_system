from fastapi import Request

from src.core.graph import build_graph
from src.core.workspace import WorkspaceManager


def get_workspace_manager(request: Request) -> WorkspaceManager:
    """Dependency to inject the WorkspaceManager from the application state."""
    return request.app.state.workspace_manager


def get_graph(request: Request):
    """
    Dependency to get the compiled LangGraph instance.
    Uses a generator to safely manage the SQLite checkpointer context.
    """
    from langgraph.checkpoint.sqlite import SqliteSaver
    from src.core.config import settings

    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    
    with SqliteSaver.from_conn_string(db_path) as memory:
        yield build_graph(memory)
