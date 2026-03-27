from datetime import datetime
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langfuse import observe

from src.core.config_manager import app_config, config_manager
from src.core.prompts import prompt_manager
from src.core.state import EngineeringState
from src.core.workspace import WorkspaceManager
from src.schemas import ApprovalStatus, TechnicalPlan
from src.tools.codebase_tools import get_restricted_tools, search_codebase
from src.utils.logger import configure_logging

logger = configure_logging("planning")

# Core managers
workspace_manager = WorkspaceManager()


@observe(name="Agent: Planning & Strategy")
async def planning_node(
    state: EngineeringState, config: RunnableConfig, **kwargs
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

    # 2. Fetch Prompt from PromptManager (Langfuse vs Local fallback)
    lf_system_prompt = prompt_manager.get_prompt("planning-system")
    system_prompt = lf_system_prompt.compile(repo_name=str(repo))
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
            response = await llm_with_tools.ainvoke(
                messages,
                config={
                    **config,
                    "run_name": "Planner: Research Phase",
                    "metadata": {
                        **config.get("metadata", {}),
                        "langfuse_prompt": lf_system_prompt,
                    },
                },
            )
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
            lf_slug_prompt = prompt_manager.get_prompt("planning-slug-extractor")
            slug_resp = await slug_llm.ainvoke(
                [
                    HumanMessage(
                        content=lf_slug_prompt.compile(
                            task_description=task_description
                        )
                    )
                ],
                config={
                    **config,
                    "metadata": {
                        **config.get("metadata", {}),
                        "langfuse_prompt": lf_slug_prompt,
                    },
                },
            )
            raw_slug = str(getattr(slug_resp, "content", slug_resp)).strip().lower()
            slug = re.sub(r"[^a-z0-9]+", "-", raw_slug).strip("-")[:35] or "task"
            branch_name = f"{app_config.system.branch_prefix}{slug}-{datetime.now().strftime('%m%d%H%M')}"

        logger.info(
            "📋 Generating structured TechnicalPlan with branch: %s", branch_name
        )
        lf_plan_prompt = prompt_manager.get_prompt("planning-final-plan")
        final_plan: Any = await structured_llm.ainvoke(
            messages + [HumanMessage(content=lf_plan_prompt.compile(repo=repo))],
            config={
                **config,
                "run_name": "Planner: Strategic Formulation",
                "metadata": {
                    **config.get("metadata", {}),
                    "langfuse_prompt": lf_plan_prompt,
                },
            },
        )

        # Update the plan Markdown for the user
        plan_md = f"# Technical Plan: {final_plan.title}\n\n"
        plan_md += f"**Risk Assessment:** {final_plan.estimated_risk} | **Branch:** `{branch_name}`\n\n"
        plan_md += "## Summary\n"
        plan_md += f"{final_plan.summary}\n\n"
        plan_md += "## Execution Steps\n\n"
        for step in final_plan.steps:
            plan_md += f"### {step.id}: {step.description}\n"
            plan_md += f"**Assigned to:** {step.assigned_to}\n"
            if step.verification_criteria:
                plan_md += f"**Verification:** {step.verification_criteria}\n"
            plan_md += "\n"

        # 5. Persist the plan locally for debugging/reference (avoids repo clutter)
        from pathlib import Path

        thread_id = (
            state.trigger.payload.get("thread_id", "manual")
            if state.trigger and hasattr(state.trigger, "payload")
            else "manual-task"
        )
        storage_base = Path(app_config.system.plan_storage_base)
        plan_filename = f"task_{thread_id}.md"
        plan_path = storage_base / plan_filename

        try:
            storage_base.mkdir(parents=True, exist_ok=True)
            header = f"<!-- THREAD_ID: {thread_id} | REPO: {repo} | DATE: {datetime.now().isoformat()} -->\n\n"
            final_file_content = f"{header}{plan_md}"
            plan_path.write_text(final_file_content, encoding="utf-8")
            logger.info(f"✅ Technical Plan persisted to {plan_path}")

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

        # 6. Store in state and return
        return {
            "messages": [AIMessage(content=content)],
            "task_plan": final_plan,
            "branch_name": branch_name,
            "approval_status": ApprovalStatus.APPROVED,
            "active_step_id": final_plan.steps[0].id if final_plan.steps else None,
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
