import os

from langchain_core.tools import StructuredTool, tool
from pydantic import BaseModel, Field

from src.core.memory import LongTermMemory
from src.core.resource_manager import ResourceManager
from src.utils.logger import configure_logging

logger = configure_logging()

# Core Resource Management
resource_manager = ResourceManager()

# Use the same collection as WorkspaceManager for consistency
memory = LongTermMemory(collection_name="workspace_context")


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
async def read_file(path: str) -> str:
    """
    Read the contents of a specific file from the repository context.
    The path can be a local path or an mcp:// URI.
    """
    logger.info(f"📂 Tool: Reading resource '{path}'...")

    try:
        content = await resource_manager.read_resource(path)
        if len(content) > 20000:
            return content[:20000] + "\n\n...[RESOURCE TRUNCATED TO 20,000 CHARACTERS]"
        return content
    except Exception as e:
        return f"Error reading resource: {str(e)}"


@tool
async def list_directory(path: str = "") -> str:
    """
    Explore the codebase structure by listing contents of a directory or repository.
    The path can be a local directory or an mcp:// URI.
    """
    logger.info(f"📁 Tool: Listing resource '{path}'...")

    try:
        items = await resource_manager.list_resource(path)
        if not items:
            return f"The resource at '{path}' is empty or not found."
        return "\n".join(sorted(items))
    except Exception as e:
        return f"Error listing resource: {str(e)}"


@tool
async def write_file(path: str, content: str) -> str:
    """
    Write or overwrite a file with new content.
    The path can be a local path or an mcp:// URI.
    """
    logger.info(f"📝 Tool: Writing to resource '{path}'...")

    try:
        success = await resource_manager.write_resource(path, content)
        if success:
            return f"Successfully wrote to {path}"
        return f"Failed to write to {path}"
    except Exception as e:
        return f"Error writing resource: {str(e)}"


# ── Restricted Tools (Per-Repo Scoping) ────────────────────────────


class FilePathArgs(BaseModel):
    path: str = Field(description="The path to the file (local or mcp://)")


class ListDirectoryArgs(BaseModel):
    path: str = Field(
        default="", description="The path to the directory. Leave empty for root."
    )


class WriteFileArgs(BaseModel):
    path: str = Field(description="Path to the file to modify")
    content: str = Field(description="The new content to write to the file")


class ReplaceInFileArgs(BaseModel):
    path: str = Field(description="Path to the file to modify")
    diff: str = Field(description="One or more SEARCH/REPLACE blocks")


async def _enforce_scope(path: str, restriction_scope: str) -> str:
    """
    Ensures the path/URI belongs to the allowed restriction scope.
    Returns a safe, absolute local path OR a properly formatted mcp:// URI.
    """
    # 1. Resolve the intended base for this repo
    # This might return a local path (if repo exists locally) or an mcp:// URI
    base_resource = await resource_manager.resolve_resource_path(restriction_scope)

    # 2. Case A: Intent is an MCP resource
    if base_resource.startswith("mcp://"):
        # If the input path is already an absolute MCP URI, just verify the repo name is in it
        if path.startswith("mcp://"):
            if restriction_scope not in path:
                raise PermissionError(
                    f"Permission Denied: MCP resource '{path}' is outside locked repo '{restriction_scope}'"
                )
            return path

        # Otherwise, treat input as a relative path and join it to the mcp base
        # Normalize: remove repo name from start if LLM included it
        path = path.strip("/")
        if path == restriction_scope:
            path = ""
        elif path.startswith(restriction_scope + "/"):
            path = path[len(restriction_scope) + 1 :]

        clean_base = base_resource.rstrip("/")
        clean_path = path
        return f"{clean_base}/{clean_path}" if clean_path else clean_base + "/"

    # 3. Case B: Intent is a local filesystem resource
    # At this point, base_resource is an absolute local path
    base_dir = os.path.abspath(base_resource)

    # If LLM passed an mcp:// URI to a local-only tool, we should probably fail or resolve it
    if path.startswith("mcp://"):
        # This shouldn't really happen if resolve_resource_path returned a local path,
        # but if it does, we strip the mcp prefix and try to resolve relative to base_dir
        # for maximum resilience.
        path = path.split("/")[-1]  # Fallback: last segment

    if not os.path.isabs(path):
        # Handle the case where path starts with the repo name (LLM often does this)
        if path.startswith(restriction_scope + "/"):
            path = path[len(restriction_scope) + 1 :]
        elif path == restriction_scope:
            path = ""
        path = os.path.join(base_dir, path)

    abs_target = os.path.abspath(path)
    if not abs_target.startswith(base_dir):
        raise PermissionError(
            f"Permission Denied: Path '{path}' resolves outside locked repo '{base_dir}'"
        )

    return abs_target


def get_restricted_tools(restriction_scope: str) -> list:
    """
    Returns a list of tools (read_file, write_file, list_directory) that are
    hard-locked to a specific restriction_scope.
    """

    async def restricted_read_file(path: str) -> str:
        """Read the contents of a specific file from the locked repository."""
        try:
            safe_path = await _enforce_scope(path, restriction_scope)
            logger.info(f"📂 Restricted Tool: Reading resource '{safe_path}'...")
            content = await resource_manager.read_resource(safe_path)
            if len(content) > 20000:
                return (
                    content[:20000] + "\n\n...[RESOURCE TRUNCATED TO 20,000 CHARACTERS]"
                )
            return content
        except Exception as e:
            return str(e)

    async def restricted_write_file(path: str, content: str) -> str:
        """Write or overwrite a file with new content in the locked repository."""
        try:
            safe_path = await _enforce_scope(path, restriction_scope)
            logger.info(f"📝 Restricted Tool: Writing resource '{safe_path}'...")
            success = await resource_manager.write_resource(safe_path, content)
            return f"Successfully wrote to {safe_path}" if success else "Write failed"
        except Exception as e:
            return str(e)

    async def restricted_replace_in_file(path: str, diff: str) -> str:
        """Apply targeted SEARCH/REPLACE edits to a file in the locked repository."""
        try:
            safe_path = await _enforce_scope(path, restriction_scope)
            logger.info(f"🩹 Restricted Tool: Patching resource '{safe_path}'...")

            content = await resource_manager.read_resource(safe_path)

            import re

            pattern = re.compile(
                r"<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE", re.DOTALL
            )

            blocks = pattern.findall(diff)
            if not blocks:
                return "Error: No valid SEARCH/REPLACE blocks found in diff."

            new_content = content
            for search_text, replace_text in blocks:
                if search_text not in new_content:
                    # Provide helpful context on mismatch
                    return f"Error: SEARCH block not found in file '{path}'. Please ensure exact match including whitespace."

                # Replace only the first occurrence as per Cline rules
                new_content = new_content.replace(search_text, replace_text, 1)

            success = await resource_manager.write_resource(safe_path, new_content)
            return (
                f"Successfully applied {len(blocks)} changes to {safe_path}"
                if success
                else "Write failed during patch"
            )
        except Exception as e:
            return str(e)

    async def restricted_list_directory(path: str = "") -> str:
        """List the contents of a directory within your locked repository."""
        if not path:
            path = restriction_scope

        try:
            safe_path = await _enforce_scope(path, restriction_scope)
            logger.info(f"📁 Restricted Tool: Listing resource '{safe_path}'...")
            items = await resource_manager.list_resource(safe_path)
            return "\n".join(sorted(items))
        except Exception as e:
            return str(e)

    return [
        StructuredTool.from_function(
            coroutine=restricted_read_file,
            name="read_file",
            description="Read file contents from repository context.",
            args_schema=FilePathArgs,
        ),
        StructuredTool.from_function(
            coroutine=restricted_write_file,
            name="write_file",
            description=f"Write or overwrite a file in '{restriction_scope}'.",
            args_schema=WriteFileArgs,
        ),
        StructuredTool.from_function(
            coroutine=restricted_replace_in_file,
            name="replace_in_file",
            description=f"Apply targeted SEARCH/REPLACE edits to a file in '{restriction_scope}'.",
            args_schema=ReplaceInFileArgs,
        ),
        StructuredTool.from_function(
            coroutine=restricted_list_directory,
            name="list_directory",
            description="List directory contents to explore repository structure.",
            args_schema=ListDirectoryArgs,
        ),
    ]


def get_ops_tools(restriction_scope: str) -> list:
    """
    Returns a list of read-only tools and execute_command locked to a repository.
    """
    # Reuse restricted tools for read/list
    base_tools = get_restricted_tools(restriction_scope)
    # Remove write_file
    ops_tools = [t for t in base_tools if t.name != "write_file"]

    class ExecuteCommandArgs(BaseModel):
        command: str = Field(description="Shell command (e.g., 'pytest', 'flake8')")

    async def restricted_execute_command(command: str) -> str:
        """Execute a shell command within the locked repository directory."""
        import subprocess

        # Resolve the actual local path for this repo (might be in /tmp or already local)
        try:
            base_dir = await resource_manager.resolve_resource_path(restriction_scope)
        except Exception as e:
            return f"Error resolving repository path: {e}"

        logger.info(f"⚙️ Ops Tool: Executing command '{command}' in '{base_dir}'...")

        if not base_dir or not os.path.exists(base_dir):
            return f"Error: Local directory for '{restriction_scope}' not found. Ensure it is cloned/ingested."

        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = base_dir + (
                os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else ""
            )

            result = subprocess.run(
                command,
                shell=True,
                cwd=base_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )

            output = f"STDOUT:\n{result.stdout}\n" if result.stdout else ""
            output += f"STDERR:\n{result.stderr}\n" if result.stderr else ""
            output += f"Exit Code: {result.returncode}"

            return output[:2000] + ("\n...[TRUNCATED]" if len(output) > 2000 else "")

        except Exception as e:
            return f"Error executing command: {str(e)}"

    ops_tools.append(
        StructuredTool.from_function(
            coroutine=restricted_execute_command,
            name="execute_command",
            description="Execute shell commands in the isolated repository.",
            args_schema=ExecuteCommandArgs,
        )
    )
    return ops_tools
