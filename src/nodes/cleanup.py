from pathlib import Path
from typing import Any, Dict

from src.core.config_manager import app_config
from src.core.state import EngineeringState
from src.utils.logger import configure_logging

logger = configure_logging("cleanup")


async def cleanup_node(state: EngineeringState) -> Dict[str, Any]:
    """
    Cleanup Node: Removes transient artifacts like task plans and temporary clones.
    """
    logger.info("🧹 Cleanup Agent tidying up...")

    # 1. Cleanup Task Plan
    thread_id = (
        state.trigger.payload.get("thread_id", "unknown")
        if state.trigger and hasattr(state.trigger, "payload")
        else "manual-task"
    )
    storage_base = Path(app_config.system.plan_storage_base)
    plan_filename = f"task_{thread_id}.md"
    plan_path = storage_base / plan_filename

    if plan_path.exists():
        try:
            plan_path.unlink()
            logger.info("🗑️ Deleted transient plan: %s", plan_path)
        except Exception as e:
            logger.warning("Failed to delete plan %s: %s", plan_path, e)
    else:
        logger.debug("No transient plan found at %s", plan_path)

    # 2. Cleanup Temporary Clones (via ResourceManager)
    from src.tools.codebase_tools import resource_manager

    try:
        await resource_manager.cleanup()
        logger.info("🧼 Cleaned up ephemeral workspaces.")
    except Exception as e:
        logger.warning("Failed to cleanup workspaces: %s", e)

    # 3. Cleanup E2B Sandbox
    if state.sandbox_id:
        try:
            from e2b import Sandbox
            from src.core.config import settings
            # We use Sandbox.connect to get a handle, then close/kill it
            with Sandbox.connect(state.sandbox_id, api_key=settings.E2B_API_KEY) as sb:
                sb.kill()
            logger.info("🔒 Closed E2B Sandbox: %s", state.sandbox_id)
        except Exception as e:
            logger.warning("Failed to close E2B sandbox %s: %s", state.sandbox_id, e)

    return {"sandbox_id": None}
