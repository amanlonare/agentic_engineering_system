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


@tool
def write_file(path: str, content: str) -> str:
    """
    Write or overwrite a file with new content.
    """
    safe_path = _normalize_path(path)
    logger.info(f"📝 Tool: Writing file '{safe_path}'...")

    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, "w") as f:
            f.write(content)
        return f"Successfully wrote to {safe_path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


def get_restricted_tools(restriction_scope: str) -> list:
    """
    Returns a list of tools (read_file, write_file, list_directory) that are
    hard-locked to a specific restriction_scope (e.g., a specific repository).
    """
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    # Calculate absolute allowed prefix to ensure no path traversal escapes it
    base_dir = os.path.abspath(os.path.join(".context", restriction_scope))

    def enforce_scope(path: str) -> str:
        safe_path = _normalize_path(path)
        abs_target = os.path.abspath(safe_path)
        if not abs_target.startswith(base_dir):
            raise PermissionError(
                f"Permission Denied: Path '{path}' is outside your locked repository '{restriction_scope}'"
            )
        return safe_path

    class FilePathArgs(BaseModel):
        path: str = Field(description="The path to the file or directory")

    class WriteFileArgs(BaseModel):
        path: str = Field(description="Path to the file to modify")
        content: str = Field(description="The new content to write to the file")

    def restricted_read_file(path: str) -> str:
        """Read the contents of a specific file from the locked repository."""
        try:
            safe_path = enforce_scope(path)
        except PermissionError as e:
            return str(e)

        logger.info(f"📂 Restricted Tool: Reading file '{safe_path}'...")
        if not os.path.exists(safe_path):
            return f"Error: File '{safe_path}' not found."
        if os.path.isdir(safe_path):
            return f"Error: '{safe_path}' is a directory. Use list_directory instead."
        try:
            with open(safe_path, "r") as f:
                content = f.read()
                if len(content) > 1500:
                    return (
                        content[:1500] + "\n\n...[FILE TRUNCATED TO SAVE CONTEXT SIZE]"
                    )
                return content
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def restricted_write_file(path: str, content: str) -> str:
        """Write or overwrite a file with new content in the locked repository."""
        try:
            safe_path = enforce_scope(path)
        except PermissionError as e:
            return str(e)

        logger.info(f"📝 Restricted Tool: Writing file '{safe_path}'...")
        try:
            os.makedirs(os.path.dirname(safe_path), exist_ok=True)
            with open(safe_path, "w") as f:
                f.write(content)
            return f"Successfully wrote to {safe_path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"

    def restricted_list_directory(path: str = f".context/{restriction_scope}") -> str:
        """List the contents of a directory within your locked repository."""
        try:
            safe_path = enforce_scope(path)
        except PermissionError as e:
            return str(e)

        logger.info(f"📁 Restricted Tool: Listing directory '{safe_path}'...")
        if not os.path.exists(safe_path):
            return f"Error: Directory '{safe_path}' not found."
        if not os.path.isdir(safe_path):
            return f"Error: '{safe_path}' is not a directory."
        try:
            items = os.listdir(safe_path)
            items = [
                i for i in items if i != "__pycache__" and not i.startswith(".git")
            ]
            return "\n".join(sorted(items))
        except Exception as e:
            return f"Error listing directory: {str(e)}"

    return [
        StructuredTool.from_function(
            func=restricted_read_file,
            name="read_file",
            description="Read the contents of a specific file from the repository context. Use to understand existing code.",
            args_schema=FilePathArgs,
        ),
        StructuredTool.from_function(
            func=restricted_write_file,
            name="write_file",
            description="Write or overwrite a file with new content. Use for feature code and unit tests.",
            args_schema=WriteFileArgs,
        ),
        StructuredTool.from_function(
            func=restricted_list_directory,
            name="list_directory",
            description="List the contents of a directory to explore the repository structure.",
            args_schema=FilePathArgs,
        ),
    ]


def get_ops_tools(restriction_scope: str) -> list:
    """
    Returns a list of read-only tools (read_file, list_directory)
    locked to a specific repository scope for the Ops agent.
    """
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    # Calculate absolute allowed prefix
    base_dir = os.path.abspath(os.path.join(".context", restriction_scope))

    def enforce_scope(path: str) -> str:
        safe_path = _normalize_path(path)
        abs_target = os.path.abspath(safe_path)
        if not abs_target.startswith(base_dir):
            raise PermissionError(
                f"Permission Denied: Path '{path}' is outside your locked repository '{restriction_scope}'"
            )
        return safe_path

    class FilePathArgs(BaseModel):
        path: str = Field(description="The path to the file or directory")

    def restricted_read_file(path: str) -> str:
        """Read the contents of a specific file from the locked repository."""
        try:
            safe_path = enforce_scope(path)
        except PermissionError as e:
            return str(e)
        if not os.path.exists(safe_path):
            return f"Error: File '{safe_path}' not found."
        try:
            with open(safe_path, "r") as f:
                content = f.read()
                return content[:1500] if len(content) > 1500 else content
        except Exception as e:
            return f"Error: {e}"

    def restricted_list_directory(path: str = f".context/{restriction_scope}") -> str:
        """List the contents of a directory within your locked repository."""
        try:
            safe_path = enforce_scope(path)
        except PermissionError as e:
            return str(e)
        try:
            items = os.listdir(safe_path)
            items = [
                i for i in items if i != "__pycache__" and not i.startswith(".git")
            ]
            return "\n".join(sorted(items))
        except Exception as e:
            return f"Error: {e}"

    return [
        StructuredTool.from_function(
            func=restricted_read_file,
            name="read_file",
            description="Read the contents of a specific file. Use to inspect the Coder's implementation.",
            args_schema=FilePathArgs,
        ),
        StructuredTool.from_function(
            func=restricted_list_directory,
            name="list_directory",
            description="List the contents of a directory to explore the repository structure.",
            args_schema=FilePathArgs,
        ),
    ]
