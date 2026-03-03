import httpx

from src.core.config import settings
from src.utils.logger import configure_logging

logger = configure_logging()

# Base URL for GitHub API
GITHUB_API_URL = "https://api.github.com"


async def post_issue_comment(repo: str, issue_number: int, body: str) -> bool:
    """
    Posts a comment on a specific GitHub issue.

    Args:
        repo: Repository full name (e.g. "owner/repo")
        issue_number: Issue number
        body: Markdown body of the comment

    Returns:
        bool: True if successful, False otherwise.
    """
    if not settings.GITHUB_TOKEN:
        logger.warning(
            "GITHUB_TOKEN is not set. Skipping posting comment to %s#%s.",
            repo,
            issue_number,
        )
        return False

    url = f"{GITHUB_API_URL}/repos/{repo}/issues/{issue_number}/comments"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {settings.GITHUB_TOKEN}",
    }
    payload = {"body": body}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, headers=headers, json=payload, timeout=10.0
            )
            response.raise_for_status()
            logger.info("✅ Successfully posted comment to %s#%s", repo, issue_number)
            return True
    except httpx.HTTPStatusError as e:
        logger.error(
            "Failed to post comment to %s#%s: %s (Status: %s)",
            repo,
            issue_number,
            e.response.text,
            e.response.status_code,
        )
        return False
    except Exception as e:
        logger.error(
            "Exception while posting comment to %s#%s: %s", repo, issue_number, str(e)
        )
        return False
