from typing import Optional

from langchain_core.tools import tool

from src.tools.codebase_tools import resource_manager
from src.utils.logger import configure_logging

logger = configure_logging()


@tool
async def create_github_issue(owner: str, repo: str, title: str, body: str) -> str:
    """Creates a new issue on a GitHub repository."""
    logger.info(f"🐙 Creating GitHub Issue: '{title}' in {owner}/{repo}")

    session = resource_manager.mcp_manager.sessions.get("github")
    if not session:
        return "Error: GitHub MCP server not connected."

    try:
        result = await session.call_tool(
            "create_issue", {"owner": owner, "repo": repo, "title": title, "body": body}
        )
        return f"Successfully created issue: {result}"
    except Exception as e:
        return f"Error creating issue: {str(e)}"


@tool
async def list_github_issues(owner: str, repo: str, state: str = "open") -> str:
    """Lists issues in a GitHub repository."""
    logger.info(f"🐙 Listing GitHub Issues in {owner}/{repo}")

    session = resource_manager.mcp_manager.sessions.get("github")
    if not session:
        return "Error: GitHub MCP server not connected."

    try:
        result = await session.call_tool(
            "list_issues", {"owner": owner, "repo": repo, "state": state}
        )
        return str(result)
    except Exception as e:
        return f"Error listing issues: {str(e)}"


@tool
async def create_pull_request(
    owner: str, repo: str, title: str, head: str, base: str, body: Optional[str] = None
) -> str:
    """Creates a new pull request on a GitHub repository."""
    logger.info(f"🐙 Creating PR: '{title}' from {head} into {base}")

    session = resource_manager.mcp_manager.sessions.get("github")
    if not session:
        return "Error: GitHub MCP server not connected."

    try:
        result = await session.call_tool(
            "create_pull_request",
            {
                "owner": owner,
                "repo": repo,
                "title": title,
                "head": head,
                "base": base,
                "body": body or "",
            },
        )
        return f"Successfully created PR: {result}"
    except Exception as e:
        return f"Error creating PR: {str(e)}"
