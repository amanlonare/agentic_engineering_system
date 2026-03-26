from datetime import datetime
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from src.core.config_manager import app_config, config_manager
from src.core.state import EngineeringState
from src.core.workspace import WorkspaceManager
from src.schemas import ApprovalStatus, TechnicalPlan
from src.tools.codebase_tools import get_restricted_tools, search_codebase
from src.utils.config_loader import build_system_prompt, load_agent_persona
from src.utils.logger import configure_logging

logger = configure_logging("planning")

# Core managers
workspace_manager = WorkspaceManager()


async def planning_node(
    state: EngineeringState, config: RunnableConfig
) -> Dict[str, Any]:
    """
    Planning Agent: Designs technical implementation plans.
    """
    logger.info("🧠 Planning Agent designing plan...")

    # 1. Dynamic Repository Discovery
    repo = state.trigger.repo_name if state.trigger else "General"
    if repo == "General" or not repo:
        # Attempt to find the most relevant repository based on the task description
        task_desc = state.messages[0].content if state.messages else ""
        identified_repo = await workspace_manager.identify_repository(str(task_desc))
        if identified_repo:
            logger.info(
                "🎯 Dynamic Discovery: Identified repository '%s' for task.",
                identified_repo,
            )
            repo = identified_repo
        else:
            logger.info(
                "ℹ️ Dynamic Discovery: No specific repository identified for general task."
            )

    # 2. Load Persona
    persona = load_agent_persona("planning")
    system_prompt = build_system_prompt(persona).replace("{repo_name}", str(repo))
    if state.is_lightweight:
        system_prompt = (
            "THIS IS A LIGHTWEIGHT task. Follow the Lightweight Task Protocol.\n\n"
            + system_prompt
        )

    # 3. Setup LLM and tools
    llm = config_manager.get_agent_llm("planner")

    # Use repo-scoped tools, filter out write_file since planner doesn't write code
    restricted_tools = get_restricted_tools(str(repo))
    tools = [
        t for t in restricted_tools if t.name not in ("write_file", "replace_in_file")
    ]
    tools.append(search_codebase)

    llm_with_tools = llm.bind_tools(tools)
    structured_llm = llm.with_structured_output(TechnicalPlan)

    # 4. Build messages
    task_description = (
        state.follow_up_context
        if state.follow_up_context
        else (state.messages[0].content if state.messages else "No task description")
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Task: {task_description}"),
    ]

    try:
        # Step 1: Multi-turn Tool-Calling Phase (Exploration)
        tool_call_count = 0
        MAX_TOOL_CALLS = 10

        while tool_call_count < MAX_TOOL_CALLS:
            response = await llm_with_tools.ainvoke(messages, config=config)
            messages.append(response)

            if not getattr(response, "tool_calls", None):
                logger.info("✅ Planning Agent has completed exploration.")
                break

            logger.info(
                "🛠️ Planning Agent calling tools: %s",
                [tc["name"] for tc in response.tool_calls],
            )

            for tool_call in response.tool_calls:
                tool_instance = next(
                    (t for t in tools if t.name == tool_call["name"]), None
                )
                if tool_instance:
                    if hasattr(tool_instance, "ainvoke"):
                        result = await tool_instance.ainvoke(tool_call["args"])
                    else:
                        result = tool_instance.invoke(tool_call["args"])
                    result_str = str(result)
                    messages.append(
                        ToolMessage(content=result_str, tool_call_id=tool_call["id"])
                    )

                    # Log a snippet of the result for visibility
                    snippet = result_str[:500].replace("\n", " ")
                    if len(result_str) > 500:
                        snippet += "..."
                    logger.info("🛠️ Tool '%s' returned: %s", tool_call["name"], snippet)
                else:
                    logger.warning(
                        "Planning Agent tried unauthorized tool: %s", tool_call["name"]
                    )
                    messages.append(
                        ToolMessage(
                            content=f"Error: Tool {tool_call['name']} not available.",
                            tool_call_id=tool_call["id"],
                        )
                    )

            tool_call_count += 1

        if tool_call_count >= MAX_TOOL_CALLS:
            logger.warning(
                "⚠️ Planning Agent reached max tool calls (%d). Forcing stop.",
                MAX_TOOL_CALLS,
            )

        # Step 2: Ask LLM to produce a clean semantic slug for the branch name.
        # We do NOT use a hardcoded noise word list — the LLM understands the intent.
        import re

        if state.branch_name:
            branch_name = state.branch_name
        else:
            slug_llm = config_manager.get_agent_llm("planning")
            slug_resp = await slug_llm.ainvoke(
                [
                    HumanMessage(
                        content=(
                            f"Extract a concise 2-4 word kebab-case slug from the following task description "
                            f"that captures the core technical action. Output ONLY the slug, nothing else. "
                            f"Example: 'implement fibonacci' → 'fibonacci-series'. "
                            f"Example: 'add user authentication to the backend api' → 'user-auth-api'. "
                            f"Task: {task_description}"
                        )
                    )
                ],
                config=config,
            )
            raw_slug = str(getattr(slug_resp, "content", slug_resp)).strip().lower()
            slug = re.sub(r"[^a-z0-9]+", "-", raw_slug).strip("-")[:35] or "task"
            branch_name = f"{app_config.system.branch_prefix}{slug}-{datetime.now().strftime('%m%d%H%M')}"

        # Inject branch name and repo requirement into the final prompt
        messages.append(
            HumanMessage(
                content=(
                    f"Please generate the TechnicalPlan now.\n"
                    f"IMPORTANT: Do NOT create steps for git branch creation, git commit, or git push — these are handled automatically.\n"
                    f"IMPORTANT: For 'target_repo', use the full identifier '{repo}' (owner/repo) for all steps."
                )
            )
        )

        logger.info(
            "📋 Generating structured TechnicalPlan with branch: %s", branch_name
        )
        plan: Any = await structured_llm.ainvoke(messages, config=config)

        # Update the plan Markdown for the user
        plan_md = f"# Technical Plan: {plan.title}\n\n"
        plan_md += f"**Risk Assessment:** {plan.estimated_risk} | **Branch:** `{branch_name}`\n\n"
        plan_md += "## Summary\n"
        plan_md += f"{plan.summary}\n\n"
        plan_md += "## Execution Steps\n\n"
        for step in plan.steps:
            plan_md += f"### {step.id}: {step.description}\n"
            plan_md += f"- **Assignee:** {step.assigned_to}\n"
            if step.dependencies:
                plan_md += f"- **Dependencies:** {', '.join(step.dependencies)}\n"
            plan_md += f"- **Verification:** `{step.verification_criteria}`\n\n"

        # Step 4: Persist the plan locally for debugging/reference (avoids repo clutter)
        from pathlib import Path

        # Get thread_id from state if available, or generate a fallback
        thread_id = (
            state.trigger.payload.get("thread_id", "unknown")
            if state.trigger and hasattr(state.trigger, "payload")
            else "manual-task"
        )

        storage_base = Path(app_config.system.plan_storage_base)
        plan_filename = f"task_{thread_id}.md"
        plan_path = storage_base / plan_filename

        try:
            # Ensure the storage directory exists
            storage_base.mkdir(parents=True, exist_ok=True)

            # Add a header with metadata
            header = f"<!-- THREAD_ID: {thread_id} | REPO: {repo} | DATE: {datetime.now().isoformat()} -->\n\n"
            final_file_content = f"{header}{plan_md}"

            plan_path.write_text(final_file_content, encoding="utf-8")
            logger.info(f"✅ Technical Plan persisted to {plan_path} (AES Local)")

            content = (
                f"### 📋 Technical Plan Generated\n"
                f"The execution strategy has been saved to `{plan_path}` for reference.\n\n"
                f"{plan_md}"
            )
        except Exception as write_err:
            logger.warning(f"Failed to persist PLAN.md locally: {write_err}")
            content = (
                f"### 📋 Technical Plan Generated (Persistence Failed)\n\n{plan_md}"
            )

        return {
            "messages": [AIMessage(content=content)],
            "task_plan": plan,
            "branch_name": branch_name,
            "approval_status": ApprovalStatus.APPROVED,
            "trigger": (
                state.trigger.model_copy(update={"repo_name": repo})
                if state.trigger
                else None
            ),
        }

    except Exception as e:
        error_msg = f"Planning Agent failed: {str(e)}"
        logger.error("❌ %s", error_msg)
        return {"messages": [AIMessage(content=error_msg)], "error_message": error_msg}
