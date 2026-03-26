import datetime
from typing import Any, Dict

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from src.core.config_manager import app_config
from src.core.graph_store import GraphStore
from src.core.resource_manager import ResourceManager
from src.core.state import EngineeringState
from src.schemas import StepExecutionRecord, StepStatus
from src.tools.e2b_aider_tool import run_aider_in_e2b
from src.utils.config_loader import build_system_prompt, load_agent_persona
from src.utils.logger import configure_logging

logger = configure_logging("coder")

# Global resource manager
resource_manager = ResourceManager()


async def _get_repo_url(repo_name: str) -> str:
    """Resolves a repository name to its remote URL via GraphStore."""
    gs = GraphStore()
    results = gs.execute_query(
        "MATCH (r:Repository) WHERE r.name ENDS WITH $name RETURN r.remote_url LIMIT 1",
        {"name": repo_name if repo_name.startswith("/") else f"/{repo_name}"},
    )
    if results and results[0] and results[0][0]:
        return results[0][0]

    # Fallback logic: if it looks like a full repo name (owner/repo), use it.
    # Otherwise, log a warning and use the base github URL.
    candidate = repo_name
    if "/" not in candidate:
        logger.warning(
            "⚠️ Partial repo name '%s' passed. No owner found. Guessing...", repo_name
        )

    return f"https://github.com/{candidate}"  # Guessing the full path


async def coder_node(state: EngineeringState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Coder Agent: Executes code changes using E2B + Aider.
    """
    logger.info("💻 Coder Agent starting execution via E2B + Aider...")

    # 1. Identify Target Step and Repo
    current_step = None
    if state.task_plan and state.active_step_id:
        current_step = next(
            (s for s in state.task_plan.steps if s.id == state.active_step_id), None
        )

    if not current_step and state.task_plan:
        # Fallback to first uncompleted coder step
        current_step = next(
            (
                s
                for s in state.task_plan.steps
                if s.assigned_to == "coder"
                and s.id not in (state.completed_step_ids or [])
            ),
            None,
        )

    if not current_step:
        logger.warning("⚠️ No specific step identified for coder.")
        return {
            "messages": [AIMessage(content="No coding step identified.")],
            "completed_step_ids": [],
            "execution_history": [],
        }

    repo_name = current_step.target_repo or (
        state.trigger.repo_name
        if state.trigger and state.trigger.repo_name
        else "unknown"
    )
    repo_url = await _get_repo_url(repo_name)

    # 2. Prepare Aider Instructions
    # Combine the step description with orchestrator feedback
    last_msg = state.messages[-1].content if state.messages else ""
    instructions = (
        f"Goal: {current_step.description}\n\nAdditional Context/Feedback: {last_msg}"
    )

    # 3. Handle Branching
    if not state.branch_name:
        plan_title = state.task_plan.title if state.task_plan else "task"
        # Slugify and truncate
        slug = "".join(c if c.isalnum() else "-" for c in plan_title.lower()).strip("-")
        slug = "-".join(filter(None, slug.split("-")))[:30]
        # Use a timestamp once for the session to ensure uniqueness
        state.branch_name = (
            f"feat/{slug}-{datetime.datetime.now().strftime('%m%d%H%M')}"
        )
        logger.info(
            "🌿 Generated unified branch name for this plan: %s", state.branch_name
        )

    branch_name = state.branch_name

    # 4. Run Aider in E2B
    action = "Connecting to" if state.sandbox_id else "Initializing"
    logger.info(
        "\U0001f9ea %s E2B sandbox to implement %s in %s",
        action,
        current_step.id,
        repo_name,
    )

    # Resolve persona
    persona = load_agent_persona("coder")
    system_prompt = build_system_prompt(persona)

    # Resolve model from config with multiple fallbacks
    coder_cfg = app_config.llm.agents.get("coder")
    coder_model = getattr(coder_cfg, "model", None) if coder_cfg else None
    coder_model = coder_model or getattr(app_config.llm, "default_model", "gpt-4o-mini")

    result = await run_aider_in_e2b(
        repo_url=repo_url,
        instructions=instructions,
        fnames=[],  # Aider will discover files automatically
        branch=branch_name,
        base_branch=app_config.system.default_branch or "main",
        model=coder_model or "gpt-4o",
        sandbox_id=state.sandbox_id,
        system_prompt=system_prompt,
    )

    # Update sandbox ID in state if it's new
    new_sandbox_id = result.get("sandbox_id") or state.sandbox_id

    if result.get("success"):
        logger.info("✅ Coder fix successful. Commit: %s", result.get("commit_sha"))
        outcome = f"Successfully completed coding tasks for {current_step.id}. Commit: {result.get('commit_sha')}"
        history = [
            StepExecutionRecord(
                step_id=current_step.id,
                status=StepStatus.COMPLETED,
                agent="coder",
                outcome=outcome,
            )
        ]

        return {
            "messages": [AIMessage(content=outcome)],
            "completed_step_ids": [current_step.id],
            "execution_history": history,
            "branch_name": branch_name,
            "sandbox_id": new_sandbox_id,
            "is_rework": False,
        }
    else:
        error_msg = f"❌ Coder failed: {result.get('error')}"
        logger.error(error_msg)
        return {
            "messages": [AIMessage(content=error_msg)],
            "completed_step_ids": [],
            "execution_history": [
                StepExecutionRecord(
                    step_id=current_step.id,
                    status=StepStatus.FAILED,
                    agent="coder",
                    outcome=error_msg,
                )
            ],
        }
