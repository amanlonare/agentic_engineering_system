import os
from langchain_core.tools import tool
from src.core.memory import LongTermMemory
from src.utils.logger import configure_logging

logger = configure_logging()

# Use the same collection as WorkspaceManager for consistency
memory = LongTermMemory(collection_name="workspace_context")


def _normalize_path(path: str) -> str:
    """Ensures paths are relative to .context if not specified."""
    if not path.startswith(".context") and not os.path.isabs(path):
        potential_path = os.path.join(".context", path)
        if os.path.exists(potential_path):
            return potential_path
    return path


@tool
def search_codebase(query: str) -> str:
    """
    Search the indexed codebase/repositories for relevant files and snippets.
    This effectively searches the document database (ChromaDB) for context.
    """
    logger.info(f"🔍 Tool: Searching codebase for '{query}'...")
    docs = memory.retrieve_relevant_memories(query, k=2)
    if not docs:
        return f"No relevant context found for '{query}' in the vector database."

    results = []
    for i, doc in enumerate(docs):
        results.append(f"Source {i + 1}:\n{doc.page_content}\nMetadata: {doc.metadata}")

    return "\n\n".join(results)


@tool
def read_file(path: str) -> str:
    """
    Read the contents of a specific file from the repository context.
    The path is usually discovered via search_codebase or list_directory.
    """
    safe_path = _normalize_path(path)
    logger.info(f"📂 Tool: Reading file '{safe_path}'...")

    if not os.path.exists(safe_path):
        return f"Error: File '{safe_path}' not found."

    if os.path.isdir(safe_path):
        return f"Error: '{safe_path}' is a directory. Use list_directory instead."

    try:
        with open(safe_path, "r") as f:
            content = f.read()
            if len(content) > 1500:
                return content[:1500] + "\n\n...[FILE TRUNCATED TO SAVE CONTEXT SIZE]"
            return content
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool
def list_directory(path: str = ".context") -> str:
    """
    List the contents of a directory to explore the repository structure.
    By default, it lists the .context directory where repositories are located.
    """
    safe_path = _normalize_path(path)
    logger.info(f"📁 Tool: Listing directory '{safe_path}'...")

    if not os.path.exists(safe_path):
        return f"Error: Directory '{safe_path}' not found."

    if not os.path.isdir(safe_path):
        return f"Error: '{safe_path}' is not a directory."

    try:
        items = os.listdir(safe_path)
        # We allow .context but block internal config dirs like .git/
        items = [i for i in items if i != "__pycache__" and not i.startswith(".git")]
        return "\n".join(sorted(items))
    except Exception as e:
        return f"Error listing directory: {str(e)}"
