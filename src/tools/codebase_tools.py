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


def get_restricted_tools(restriction_scope: str, branch: Optional[str] = None) -> list:
    """
    Returns a list of tools (read_file, write_file, list_directory) that are
    hard-locked to a specific restriction_scope and optionally a branch.
    """
    outer_branch = branch

    async def restricted_read_file(path: str) -> str:
        """Read the contents of a specific file from the locked repository."""
        try:
            safe_path = await _enforce_scope(path, restriction_scope)
            logger.info("📖 Restricted Tool: Reading file: %s", safe_path)
            content = await resource_manager.read_resource(safe_path, branch=outer_branch)
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
        # Safety check 1: prevent accidentally overwriting a file with a diff block
        if "<<<<<<< SEARCH" in content and "=======" in content and ">>>>>>> REPLACE" in content:
            return "Error: You are trying to use write_file with a SEARCH/REPLACE block. You MUST use 'replace_in_file' for partial updates. 'write_file' will overwrite the ENTIRE file."
            
        try:
            safe_path = await _enforce_scope(path, restriction_scope)
            
            # Safety check 2: Prevent massive accidental deletions (e.g. shrinking entire file to a snippet)
            try:
                # We read it to see if it exists and what size it is
                existing_content = await resource_manager.read_resource(safe_path, branch=branch)
                num_existing_lines = len(existing_content.splitlines())
                num_new_lines = len(content.splitlines())
                
                # If shrinking the file by more than 70% and the new file is > 0 lines (not a deliberate clear), block it.
                if num_existing_lines > 50 and num_new_lines > 0 and num_new_lines < (num_existing_lines * 0.3):
                     return (
                         f"SAFETY TRIGGER: You are trying to overwrite a file of {num_existing_lines} lines "
                         f"with only {num_new_lines} lines. This looks like a mistake where you are replacing "
                         f"the entire file with a small snippet. IF you need to modify the file, use "
                         f"'replace_in_file'. IF you genuinely intend to delete 70%+ of the file, "
                         f"please add '# I INTEND TO CLEAR THIS FILE' as the first line of your content."
                     )
                     
                # Allow override
                if num_existing_lines > 50 and num_new_lines > 0 and num_new_lines < (num_existing_lines * 0.3) and "# I INTEND TO CLEAR THIS FILE" in content[:100]:
                     pass # Authorized
                     
            except Exception:
                # File probably doesn't exist yet, which is fine for writing.
                pass

            logger.info("📝 Restricted Tool: Writing to file: %s", safe_path)
            success = await resource_manager.write_resource(
                safe_path, content, branch=branch or outer_branch
            )
            return f"Successfully wrote to {safe_path}" if success else "Write failed"
        except Exception as e:
            return str(e)

    async def restricted_replace_in_file(
        path: str, diff: str, replace_all: bool = False, branch: Optional[str] = None
    ) -> str:
        """Apply targeted SEARCH/REPLACE edits to a file in the locked repository."""
        try:
            safe_path = await _enforce_scope(path, restriction_scope)
            target_branch = branch or outer_branch
            logger.info("🩹 Restricted Tool: Patching resource '%s' (branch: %s)...", safe_path, target_branch)

            content = await resource_manager.read_resource(safe_path, branch=target_branch)

            import re
            import difflib

            # ── Flexible Multi-Pass Matcher ────────────────────────────────
            def normalize_lines(text: str) -> str:
                return "\n".join(line.strip() for line in text.splitlines() if line.strip())

            def build_whitespace_tolerant_regex(text: str) -> str:
                # 1. Split text into whitespace chunks and non-whitespace tokens
                parts = re.split(r"([ \n\t\r]+)", text)
                # 2. Escape non-whitespace tokens and replace whitespace chunks with \s*
                # Filter out empty strings from split
                return "".join(
                    re.escape(p) if not re.fullmatch(r"[ \n\t\r]+", p) else r"\s*"
                    for p in parts if p
                )

            # 1. Block Detection Pattern (Supports hallucinations like Updated, Done, etc.)
            block_pattern = re.compile(
                r"<<<<<<< (?:SEARCH|ORIGINAL|HEAD|UPDATE)\n(.*?)\n=======\n(.*?)\n>>>>>>> (?:REPLACE|UPDATED|REPLACEMENT|DONE)",
                re.DOTALL | re.MULTILINE,
            )

            blocks = block_pattern.findall(diff)
            if not blocks:
                return "Error: No valid SEARCH/REPLACE blocks found. Ensure format:\n<<<<<<< SEARCH\n[old code]\n=======\n[new code]\n>>>>>>> REPLACE"

            new_content = content
            for search_text, replace_text in blocks:
                match_indices = []

                # Tier 1: Exact Match
                start_idx = 0
                while True:
                    idx = new_content.find(search_text, start_idx)
                    if idx == -1: break
                    match_indices.append((idx, idx + len(search_text)))
                    start_idx = idx + len(search_text)

                # Tier 2: Whitespace-Tolerant Match
                if not match_indices:
                    try:
                        regex_pattern = build_whitespace_tolerant_regex(search_text)
                        for m in re.finditer(regex_pattern, new_content, re.DOTALL):
                            match_indices.append((m.start(), m.end()))
                    except Exception:
                        pass

                # Tier 3: Token-Sequence Match (Absolute Fallback)
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

                # --- Safety Verification ---
                if not match_indices:
                    # Closest match error reporting logic
                    search_lines = search_text.splitlines()
                    content_lines = new_content.splitlines()
                    anchor_line = next((l.strip() for l in search_lines if len(l.strip()) > 10), search_lines[0].strip())
                    
                    found_context = False
                    for idx, line in enumerate(content_lines):
                        if anchor_line in line:
                            start = max(0, idx - 5)
                            end = min(len(content_lines), idx + 10)
                            context = "\n".join(f"{i+1}: {content_lines[i]}" for i in range(start, end))
                            return f"Error: SEARCH block mismatch in '{path}'. Found similar text at line {start+1}:\n\n{context}\n\nTip: Copy the EXACT text from the snippet above into your SEARCH block."
                    
                    return f"Error: No match found for the SEARCH block in {path}. Ensure you are copying the code EXACTLY as it appears in the file."

                if not replace_all and len(match_indices) > 1:
                    return f"Error: Multiple matches ({len(match_indices)}) found for this SEARCH block in {path}. Please include more surrounding code in your SEARCH block to make it unique, or set 'replace_all=True' if you intend to modify all occurrences."

                # --- Apply Edits (Reverse order to preserve indices) ---
                if replace_all:
                    # Apply all in reverse
                    for start, end in reversed(match_indices):
                        new_content = new_content[:start] + replace_text + new_content[end:]
                else:
                    # Apply only the first
                    start, end = match_indices[0]
                    new_content = new_content[:start] + replace_text + new_content[end:]

            success = await resource_manager.write_resource(
                safe_path, new_content, branch=target_branch
            )
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
            logger.info("📁 Restricted Tool: Listing directory: %s", safe_path)
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


def get_ops_tools(restriction_scope: str, branch: Optional[str] = None) -> list:
    """
    Returns a list of read-only tools and execute_command locked to a repository.
    """
    # Reuse restricted tools for read/list
    base_tools = get_restricted_tools(restriction_scope, branch=branch)
    # Remove write_file
    ops_tools = [t for t in base_tools if t.name not in ("write_file", "replace_in_file")]

    class ExecuteCommandArgs(BaseModel):
        command: str = Field(description="Shell command (e.g., 'pytest', 'flake8')")

    async def restricted_execute_command(command: str) -> str:
        """Execute a shell command within the locked repository directory."""
        import subprocess

        # Resolve the actual local path for this repo
        try:
            base_resource = await resource_manager.resolve_resource_path(restriction_scope)
            if base_resource.startswith("mcp://"):
                base_dir = await resource_manager.ensure_local_context(base_resource)
            else:
                base_dir = base_resource
        except Exception as e:
            return f"Error resolving repository path: {e}"

        logger.info("🐚 Restricted Tool: Executing command '%s' in '%s' (branch: %s)...", command, base_dir, branch)

        if not base_dir or not os.path.exists(base_dir):
            return f"Error: Local directory for '{restriction_scope}' not found. Ensure it is cloned/ingested."

        # If operating in an ephemeral clone and a branch is specified, check it out first
        if branch and "temp_repos" in base_dir:
            try:
                subprocess.run(
                    ["git", "fetch", "origin", branch],
                    cwd=base_dir,
                    check=True,
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "checkout", branch],
                    cwd=base_dir,
                    check=False,
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "pull", "origin", branch],
                    cwd=base_dir,
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError as e:
                err_msg = e.stderr.decode().strip() if e.stderr else str(e)
                logger.warning("Failed to checkout branch %s in ephemeral clone: %s", branch, err_msg)
                # We do not hard-fail here to allow execution if the branch was already set or doesn't strictly exist remotely yet

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
