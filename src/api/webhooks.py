import hashlib
import hmac
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from langchain_core.messages import HumanMessage
from langchain_core.runnables.config import RunnableConfig

from src.api.dependencies import get_graph, get_workspace_manager
from src.api.github_client import post_issue_comment
from src.core.config import settings
from src.core.state import EngineeringState
from src.core.workspace import WorkspaceManager
from src.schemas import TriggerContext, TriggerType
from src.utils.logger import configure_logging

logger = configure_logging()
router = APIRouter()


def verify_signature(payload_body: bytes, signature_header: str | None) -> bool:
    """Verifies the HMAC-SHA256 signature from GitHub."""
    secret = settings.GITHUB_WEBHOOK_SECRET
    if not secret:
        # If no secret is configured, we can't secure the endpoint. Decline.
        return False

    if not signature_header:
        # Missing signature
        return False

    # The signature looks like "sha256=abc123def456..."
    if not signature_header.startswith("sha256="):
        return False

    # Compute expected signature
    expected_hash = hmac.new(
        secret.encode("utf-8"), payload_body, hashlib.sha256
    ).hexdigest()
    expected_signature = f"sha256={expected_hash}"

    return hmac.compare_digest(expected_signature, signature_header)


@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
    workspace_manager: WorkspaceManager = Depends(get_workspace_manager),
    graph=Depends(get_graph),
):
    """
    Webhook receiver for GitHub events.
    Synchronously processes Issue creation/labeling events and runs the Engineering Graph.
    """
    # 1. Read raw body for validation
    body = await request.body()

    # 2. Validate HMAC Signature
    if not verify_signature(body, x_hub_signature_256):
        logger.error("❌ Webhook signature validation failed.")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # 3. Filter Event Type
    if x_github_event != "issues":
        logger.info(f"Ignoring non-issue event: {x_github_event}")
        return {"status": "ignored", "reason": "Not an issue event"}

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    action = payload.get("action")
    if action not in ["opened", "labeled", "edited"]:
        logger.info(f"Ignoring issue action: {action}")
        return {"status": "ignored", "reason": f"Unhandled action {action}"}

    # Extract core issue details
    issue = payload.get("issue", {})
    repo = payload.get("repository", {})

    title = issue.get("title", "")
    issue_body = issue.get("body", "")
    issue_number = issue.get("number")
    repo_full_name = repo.get("full_name", "")
    sender = payload.get("sender", {}).get("login", "unknown")
    labels = [label["name"] for label in issue.get("labels", [])]

    logger.info("📥 Received Webhook: Issue #%s (%s)", issue_number, action)

    # 4. Identify Target Repository using Semantic Search
    search_context = f"{title}\n\n{issue_body}"
    target_repo = workspace_manager.identify_repository(search_context)

    # 5. Build Initial State
    thread_id = f"github_{repo_full_name.replace('/', '_')}_{issue_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:4]}"
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    # The trigger explicitly names the issue context
    trigger = TriggerContext(
        type=TriggerType.GITHUB_ISSUE,
        payload={
            "repository": repo_full_name,
            "issue_number": issue_number,
            "title": title,
            "body": issue_body,
            "labels": labels,
            "action": action,
            "sender": sender,
        },
        repo_name=target_repo,
    )

    # Human message contains the actual task specification
    initial_message = (
        f"GitHub Issue #{issue_number}: {title}\n\n{issue_body}\n\n"
        f"Action requested by @{sender}."
    )

    state = EngineeringState(
        messages=[HumanMessage(content=initial_message)],
        trigger=trigger,
    )

    logger.info("🚀 Triggering Engineering Graph synchronously...")

    # 6. Run the Graph synchronously
    # We use stream to observe, but we only really care about the final state locally
    final_state_data = None
    try:
        # Iterate to completion
        for event in graph.stream(state, config):
            for node_name, node_state in event.items():
                logger.info(f"Graph running / Finished node: {node_name}")
                final_state_data = node_state
    except Exception as e:
        logger.error("❌ Graph execution failed: %s", str(e))
        return {"status": "error", "error": str(e)}

    # 7. Format result and Post Comment
    if final_state_data:
        success = True
        error_msg = final_state_data.get("error_message")

        # Determine status
        if error_msg:
            status_emoji = "❌"
            status_title = "Agentic Execution Failed"
            body_content = f"**Error encountered:**\n```\n{error_msg}\n```"
            success = False
        else:
            status_emoji = "✅"
            status_title = "Agentic Execution Completed"
            body_content = ""
            if (
                "validation_report" in final_state_data
                and final_state_data["validation_report"]
            ):
                report = final_state_data["validation_report"]
                # Validation Report is an object (or dict depending on Pydantic serialization context)
                # handle both safely
                r_success = (
                    getattr(report, "success", report.get("success", False))
                    if hasattr(report, "success")
                    else report.get("success", False)
                )
                if r_success:
                    body_content += "\n**Verification:** Passed ✅\n"
                else:
                    body_content += "\n**Verification:** Failed ❌\n"

            # Check for injected branch name
            if "messages" in final_state_data and final_state_data["messages"]:
                last_msg = final_state_data["messages"][-1]
                content = getattr(last_msg, "content", "")
                if "[STATE_INJECT:BRANCH:" in content:
                    import re

                    match = re.search(r"\[STATE_INJECT:BRANCH:(.*?)\]", content)
                    if match:
                        branch_name = match.group(1)
                        body_content += (
                            f"\n**Branch:** `{branch_name}` — ready for PR 🚀\n"
                        )
                        # Clean up the message content
                        last_msg.content = content.replace(match.group(0), "").strip()

            body_content += f"\nProcessed by internal system. Target scope was identified as `{target_repo}`."

        comment_body = f"### {status_emoji} {status_title}\n\n{body_content}\n\n*Thread ID: `{thread_id}`*"

        # Async HTTP post
        await post_issue_comment(repo_full_name, issue_number, comment_body)

        return {"status": "success" if success else "failed", "thread_id": thread_id}
    else:
        return {"status": "error", "reason": "No final state yielded from graph"}
