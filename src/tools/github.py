import json
import os
import urllib.request
from typing import Optional

from langchain_core.tools import tool

from src.core.config_manager import app_config
from src.tools.codebase_tools import resource_manager
from src.utils.logger import configure_logging

logger = configure_logging()


def _get_default_branch(owner: str, repo: str) -> str:
    """Dynamically fetches the default branch from the GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Agentic-Engineering-System")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data.get("default_branch", app_config.system.default_branch)
    except Exception as e:
        logger.warning(
            "Failed to fetch default branch for %s/%s: %s. Falling back to config.", owner, repo, e
        )

    return app_config.system.default_branch


@tool
async def create_branch(owner: str, repo: str, branch: str, from_branch: Optional[str] = None) -> str:
    """Creates a new branch on a GitHub repository."""
    target_from = from_branch or _get_default_branch(owner, repo)
    logger.info("🐙 Creating Branch: '%s' from '%s' in %s/%s", branch, target_from, owner, repo)

    await resource_manager._ensure_mcp_connection("github")
    session = resource_manager.mcp_manager.sessions.get("github")
    if not session:
        return "Error: GitHub MCP server not connected."

    try:
        await session.call_tool(
            "create_branch",
            {"owner": owner, "repo": repo, "branch": branch, "from_branch": target_from},
        )
        return f"SUCCESS: Branch '{branch}' created from '{target_from}'. You can now use 'branch=\"{branch}\"' in replace_in_file or write_file."
    except Exception as e:
        return f"Error creating branch: {str(e)}"


@tool
async def get_branch(owner: str, repo: str, branch: str) -> str:
    """Gets information about a branch on a GitHub repository."""
    logger.info("🐙 Getting Branch: '%s' in %s/%s", branch, owner, repo)

    await resource_manager._ensure_mcp_connection("github")
    session = resource_manager.mcp_manager.sessions.get("github")
    if not session:
        return "Error: GitHub MCP server not connected."

    try:
        result = await session.call_tool(
            "get_branch", {"owner": owner, "repo": repo, "branch": branch}
        )
        return str(result)
    except Exception as e:
        return f"Error getting branch: {str(e)}"


@tool
async def list_branches(owner: str, repo: str) -> str:
    """Lists all branches in a GitHub repository."""
    logger.info("🐙 Listing branches in %s/%s", owner, repo)

    await resource_manager._ensure_mcp_connection("github")
    session = resource_manager.mcp_manager.sessions.get("github")
    if not session:
        return "Error: GitHub MCP server not connected."

    try:
        result = await session.call_tool("list_branches", {"owner": owner, "repo": repo})
        return str(result)
    except Exception as e:
        return f"Error listing branches: {str(e)}"


async def get_restricted_github_tools(repo_path: str) -> list:
    """
    Returns a list of GitHub tools (create_branch, get_branch, list_branches)
    that are hard-locked to a specific repository owner and name.
    """
    # 1. Resolve full owner/repo from repository name (e.g. portfolio -> amanlonare/portfolio)
    # This uses the already-pushed resolve_resource_path in resource_manager.
    full_path = await resource_manager.resolve_resource_path(repo_path)

    # 2. Extract owner/repo
    if "/" in full_path:
        # If it's github/owner/repo or owner/repo
        parts = full_path.replace("mcp://github/", "").split("/")
        if len(parts) >= 2:
            owner = parts[0]
            repo = parts[1]
        else:
            owner = repo_path
            repo = repo_path
    else:
        owner = repo_path
        repo = repo_path

    logger.info("🐙 Locking GitHub tools to: %s/%s", owner, repo)

    from langchain_core.tools import StructuredTool

    async def _restricted_create_branch(branch: str, from_branch: Optional[str] = None) -> str:
        """Creates a new branch on the locked GitHub repository."""
        return await create_branch.ainvoke(
            {"owner": owner, "repo": repo, "branch": branch, "from_branch": from_branch}
        )

    async def _restricted_get_branch(branch: str) -> str:
        """Gets information about a branch on the locked GitHub repository."""
        return await get_branch.ainvoke({"owner": owner, "repo": repo, "branch": branch})

    async def _restricted_list_branches() -> str:
        """Lists all branches in the locked GitHub repository."""
        return await list_branches.ainvoke({"owner": owner, "repo": repo})

    return [
        StructuredTool.from_function(
            coroutine=_restricted_create_branch,
            name="create_branch",
            description="Creates a new branch on the locked GitHub repository.",
        ),
        StructuredTool.from_function(
            coroutine=_restricted_get_branch,
            name="get_branch",
            description="Gets information about a branch on the locked GitHub repository.",
        ),
        StructuredTool.from_function(
            coroutine=_restricted_list_branches,
            name="list_branches",
            description="Lists all branches in the locked GitHub repository.",
        ),
    ]

