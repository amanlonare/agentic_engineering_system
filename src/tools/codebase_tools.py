import os
from typing import Optional

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
    logger.info("🔍 Restricted Tool: Searching codebase for '%s'...", query)
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
    logger.info("📂 Tool: Reading resource '%s'...", path)

    try:
        content = await resource_manager.read_resource(path)
        if len(content) > 20000:
            return content[:20000] + "\n\n...[RESOURCE TRUNCATED TO 20,000 CHARACTERS]"
        return content
    except Exception as e:
        return f"Error reading resource: {e}"


@tool
async def list_directory(path: str = "") -> str:
    """
    Explore the codebase structure by listing contents of a directory or repository.
    The path can be a local directory or an mcp:// URI.
    """
    logger.info("📁 Tool: Listing resource '%s'...", path)

    try:
        items = await resource_manager.list_resource(path)
        if not items:
            return f"The resource at '{path}' is empty or not found."
        return "\n".join(sorted(items))
    except Exception as e:
        return f"Error listing resource: {e}"


@tool
async def write_file(path: str, content: str) -> str:
    """
    Write or overwrite a file with new content.
    The path can be a local path or an mcp:// URI.
    """
    logger.info("📝 Tool: Writing to resource '%s'...", path)

    try:
        success = await resource_manager.write_resource(path, content)
        if success:
            return f"Successfully wrote to {path}"
        return f"Failed to write to {path}"
    except Exception as e:
        return f"Error writing resource: {e}"


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
    branch: Optional[str] = Field(
        default=None, description="The GitHub branch to write to (if applicable)."
    )


class ReplaceInFileArgs(BaseModel):
    path: str = Field(description="Path to the file to modify")
    diff: str = Field(description="One or more SEARCH/REPLACE blocks")
    replace_all: bool = Field(
        default=False,
        description="If True, replaces ALL occurrences of the SEARCH block. If False (default), only replaces the first occurrence and errors if multiple matches are found unless the block is unique enough.",
    )
    branch: Optional[str] = Field(
        default=None, description="The GitHub branch to patch (if applicable)."
    )


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


def get_restricted_tools(
    restriction_scope: str, 
    branch: Optional[str] = None,
    sandbox_id: Optional[str] = None
) -> list:
    """
    Returns a list of tools (read_file, write_file, list_directory) that are
    hard-locked to a specific restriction_scope and optionally a branch.
    """
    outer_branch = branch

    async def restricted_read_file(path: str) -> str:
        """Read the contents of a specific file from the locked repository."""
        try:
            # For sandbox, we prefer the path as provided (usually relative to repo root)
            # but we still want to enforce scope for local safety.
            safe_path = await _enforce_scope(path, restriction_scope)
            
            # If in sandbox, we need the RELATIVE path from the repo root
            inner_path = path
            if sandbox_id:
                # Basic relative path resolution for sandbox
                inner_path = os.path.relpath(safe_path, await resource_manager.resolve_resource_path(restriction_scope))
                if inner_path.startswith("../"):
                     return f"Permission Denied: Path '{path}' resolves outside sandbox repo"

            logger.info("📖 Restricted Tool: Reading file: %s (Sandbox: %s)", inner_path, sandbox_id)
            content = await resource_manager.read_resource(safe_path if not sandbox_id else inner_path, branch=outer_branch, sandbox_id=sandbox_id)
            if len(content) > 20000:
                return (
                    content[:20000] + "\n\n...[RESOURCE TRUNCATED TO 20,000 CHARACTERS]"
                )
            return content
        except Exception as e:
            return str(e)

    async def restricted_write_file(
        path: str, content: str, branch: Optional[str] = None
    ) -> str:
        """Write or overwrite a file with new content in the locked repository."""
        if "<<<<<<< SEARCH" in content and "=======" in content and ">>>>>>> REPLACE" in content:
            return "Error: You are trying to use write_file with a SEARCH/REPLACE block. You MUST use 'replace_in_file' for partial updates."
            
        try:
            safe_path = await _enforce_scope(path, restriction_scope)
            inner_path = path
            if sandbox_id:
                base_dir = await resource_manager.resolve_resource_path(restriction_scope)
                if not base_dir.startswith("/"): # it's a URI
                     base_dir = await resource_manager.ensure_local_context(base_dir)
                inner_path = os.path.relpath(safe_path, base_dir)

            logger.info("📝 Restricted Tool: Writing to file: %s (Sandbox: %s)", inner_path, sandbox_id)
            success = await resource_manager.write_resource(
                safe_path if not sandbox_id else inner_path, content, branch=branch or outer_branch, sandbox_id=sandbox_id
            )
            return f"Successfully wrote to {path}" if success else "Write failed"
        except Exception as e:
            return str(e)

    async def restricted_replace_in_file(
        path: str, diff: str, replace_all: bool = False, branch: Optional[str] = None
    ) -> str:
        """Apply targeted SEARCH/REPLACE edits to a file in the locked repository."""
        try:
            safe_path = await _enforce_scope(path, restriction_scope)
            target_branch = branch or outer_branch
            
            inner_path = path
            if sandbox_id:
                base_dir = await resource_manager.resolve_resource_path(restriction_scope)
                if not base_dir.startswith("/"):
                     base_dir = await resource_manager.ensure_local_context(base_dir)
                inner_path = os.path.relpath(safe_path, base_dir)

            logger.info("🩹 Restricted Tool: Patching resource '%s' (Sandbox: %s)...", inner_path, sandbox_id)

            content = await resource_manager.read_resource(
                safe_path if not sandbox_id else inner_path, 
                branch=target_branch, 
                sandbox_id=sandbox_id
            )

            import re
            block_pattern = re.compile(
                r"<<<<<<< (?:SEARCH|ORIGINAL|HEAD|UPDATE)\n(.*?)\n=======\n(.*?)\n>>>>>>> (?:REPLACE|UPDATED|REPLACEMENT|DONE)",
                re.DOTALL | re.MULTILINE,
            )

            blocks = block_pattern.findall(diff)
            if not blocks:
                return "Error: No valid SEARCH/REPLACE blocks found. Ensure format:\n<<<<<<< SEARCH\n[old code]\n=======\n[new code]\n>>>>>>> REPLACE"

            new_content = content
            # [Logic for normalization and matching...]
            def normalize_lines(text: str) -> str:
                return "\n".join(line.strip() for line in text.splitlines() if line.strip())

            def build_whitespace_tolerant_regex(text: str) -> str:
                parts = re.split(r"([ \n\t\r]+)", text)
                return "".join(
                    re.escape(p) if not re.fullmatch(r"[ \n\t\r]+", p) else r"\s*"
                    for p in parts if p
                )

            for search_text, replace_text in blocks:
                match_indices = []
                # Tier 1: Exact
                start_idx = 0
                while True:
                    idx = new_content.find(search_text, start_idx)
                    if idx == -1: break
                    match_indices.append((idx, idx + len(search_text)))
                    start_idx = idx + len(search_text)
                # Tier 2: Whitespace
                if not match_indices:
                    try:
                        regex_pattern = build_whitespace_tolerant_regex(search_text)
                        for m in re.finditer(regex_pattern, new_content, re.DOTALL):
                            match_indices.append((m.start(), m.end()))
                    except Exception: pass
                # Tier 3: Tokens
                if not match_indices:
                    search_norm = normalize_lines(search_text)
                    lines = new_content.splitlines()
                    for i in range(len(lines)):
                        for j in range(i + 1, min(i + 200, len(lines) + 1)):
                            candidate = "\n".join(lines[i:j])
                            if normalize_lines(candidate) == search_norm:
                                match_start = new_content.find(candidate)
                                if match_start != -1:
                                    match_indices.append((match_start, match_start + len(candidate)))
                                break
                        if match_indices: break

                if not match_indices:
                    return f"Error: No match found for the SEARCH block in {path}."

                if not replace_all and len(match_indices) > 1:
                    return f"Error: Multiple matches found for this SEARCH block in {path}."

                for start, end in reversed(match_indices if replace_all else match_indices[:1]):
                    new_content = new_content[:start] + replace_text + new_content[end:]

            success = await resource_manager.write_resource(
                safe_path if not sandbox_id else inner_path, 
                new_content, 
                branch=target_branch, 
                sandbox_id=sandbox_id
            )
            return f"Successfully applied changes to {path}" if success else "Patch write failed"
        except Exception as e:
            return str(e)

    async def restricted_list_directory(path: str = "") -> str:
        """List the contents of a directory within your locked repository."""
        if not path:
            path = restriction_scope

        try:
            safe_path = await _enforce_scope(path, restriction_scope)
            inner_path = path
            if sandbox_id:
                base_dir = await resource_manager.resolve_resource_path(restriction_scope)
                if not base_dir.startswith("/"):
                     base_dir = await resource_manager.ensure_local_context(base_dir)
                inner_path = os.path.relpath(safe_path, base_dir)

            logger.info("📁 Restricted Tool: Listing directory: %s (Sandbox: %s)", inner_path, sandbox_id)
            items = await resource_manager.list_resource(
                safe_path if not sandbox_id else inner_path, 
                branch=outer_branch, 
                sandbox_id=sandbox_id
            )
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


def get_ops_tools(
    restriction_scope: str, 
    branch: Optional[str] = None,
    sandbox_id: Optional[str] = None
) -> list:
    """
    Returns a list of read-only tools and execute_command locked to a repository.
    """
    # Reuse restricted tools for read/list
    base_tools = get_restricted_tools(restriction_scope, branch=branch, sandbox_id=sandbox_id)
    # Remove write_file
    ops_tools = [t for t in base_tools if t.name not in ("write_file", "replace_in_file")]

    class ExecuteCommandArgs(BaseModel):
        command: str = Field(description="Shell command (e.g., 'pytest', 'flake8')")

    async def restricted_execute_command(command: str) -> str:
        """Execute a shell command within the locked repository directory."""
        from src.tools.e2b_aider_tool import run_command_in_e2b
        
        # If sandbox_id is provided, execute remotely in E2B
        if sandbox_id:
            logger.info("📡 Routing command '%s' to E2B Sandbox: %s", command, sandbox_id)
            # Resolve repo URL if possible for cloning in sandbox
            from src.core.graph_store import GraphStore
            gs = GraphStore()
            results = gs.execute_query(
                "MATCH (r:Repository) WHERE r.name ENDS WITH $name RETURN r.remote_url LIMIT 1",
                {"name": f"/{restriction_scope}"},
            )
            repo_url = results[0][0] if results and results[0] else None
            
            e2b_res = await run_command_in_e2b(
                command=command,
                repo_url=repo_url,
                sandbox_id=sandbox_id,
                env={"PYTHONPATH": "/home/user/repo"}
            )
            
            if e2b_res.get("success"):
                output = f"STDOUT:\n{e2b_res.get('stdout', '')}\n"
                output += f"STDERR:\n{e2b_res.get('stderr', '')}\n"
                output += f"Exit Code: {e2b_res.get('exit_code')}"
                return output[:2000] + ("\n...[TRUNCATED]" if len(output) > 2000 else "")
            else:
                return f"Error executing in E2B: {e2b_res.get('error')}"

        # Local Fallback Execution
        import subprocess
        try:
            base_resource = await resource_manager.resolve_resource_path(restriction_scope)
            base_dir = await resource_manager.ensure_local_context(base_resource) if base_resource.startswith("mcp://") else base_resource
        except Exception as e:
            return f"Error resolving repository path: {e}"

        logger.info("🐚 Restricted Tool: Executing Localy: '%s' in '%s'", command, base_dir)

        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = base_dir + (os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else "")
            result = subprocess.run(command, shell=True, cwd=base_dir, env=env, capture_output=True, text=True, timeout=30)
            output = f"STDOUT:\n{result.stdout}\n" + (f"STDERR:\n{result.stderr}\n" if result.stderr else "") + f"Exit Code: {result.returncode}"
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
