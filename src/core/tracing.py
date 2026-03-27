import os
from contextlib import contextmanager
from typing import Optional

from langfuse import Langfuse, propagate_attributes
from langfuse.langchain import CallbackHandler

from src.core.config import settings


@contextmanager
def langfuse_session(
    session_id: str, user_id: str = "default", trace_name: Optional[str] = None
):
    """
    A wrapper context manager for Langfuse session grouping.
    Calls __enter__/__exit__ explicitly to satisfy static type checkers
    that flag `propagate_attributes` as a generator.
    """
    ctx = propagate_attributes(
        session_id=session_id, user_id=user_id, trace_name=trace_name
    )
    ctx.__enter__()
    try:
        yield
    finally:
        ctx.__exit__(None, None, None)


def get_langfuse_handler(
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[CallbackHandler]:
    """
    Initializes and returns a Langfuse CallbackHandler for LangChain/LangGraph.

    Note: LangChain metadata 'langfuse_session_id' and 'langfuse_user_id' will be
    automatically picked up for trace attribution if passed in the RunnableConfig.
    """
    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        return None

    # Langfuse CallbackHandler picks up secret key and host from environment variables
    # if not provided. We ensure they are set here from our settings.
    os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
    os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_BASE_URL

    # Metadata 'langfuse_session_id' in RunnableConfig is automatically
    # picked up by the handler root if available.
    return CallbackHandler(public_key=settings.LANGFUSE_PUBLIC_KEY)


def auth_check() -> bool:
    """Verifies Langfuse credentials and connectivity."""
    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        return False
    try:
        langfuse = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_BASE_URL,
        )
        return langfuse.auth_check()
    except Exception:
        return False


def get_langfuse_client() -> Langfuse:
    """Returns a Langfuse client instance for prompt management."""
    return Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_BASE_URL,
    )


def flush():
    """Flushes any pending traces to Langfuse."""
    get_langfuse_client().flush()
