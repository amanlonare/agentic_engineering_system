from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage

from src.core.config_manager import config_manager
from src.core.state import EngineeringState
from src.schemas import ApprovalStatus, ExecutionStep, TechnicalPlan
from src.tools import read_file
from src.utils.config_loader import build_system_prompt, load_agent_persona
from src.utils.logger import configure_logging

logger = configure_logging("planning")


def planning_node(state: EngineeringState) -> Dict[str, Any]:
    """
    Planning Agent: Designs technical implementation plans.

    This agent can now use the `read_file` tool to read the architecture map.
    It produces a TechnicalPlan using structured LLM outputs.
    """
    logger.info("🧠 Planning Agent designing plan...")

    # 1. Load Persona
    persona = load_agent_persona("planning")
    system_prompt = build_system_prompt(persona)
    if state.is_lightweight:
        system_prompt = (
            "THIS IS A LIGHTWEIGHT task. Follow the Lightweight Task Protocol.\n\n"
            + system_prompt
        )

    # 2. Setup LLM and tools
    llm = config_manager.get_agent_llm("planner")
    llm_with_tools = llm.bind_tools([read_file])
    structured_llm = llm.with_structured_output(TechnicalPlan)

    # 3. Build messages — ONLY use HumanMessage content for task description
    #    to avoid picking up Supervisor instruction messages (AIMessage).

    task_description = (
        state.follow_up_context
        if state.follow_up_context
        else state.messages[0].content
    )
    messages = [
        AIMessage(content=system_prompt),
        HumanMessage(content=f"Task: {task_description}"),
    ]

    try:
        # Step 1: Allow the agent to call tools
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if response.tool_calls:
            for tool_call in response.tool_calls:
                if tool_call["name"] == "read_file":
                    result = read_file.invoke(tool_call["args"])
                    messages.append(
                        {
                            "role": "tool",
                            "content": str(result),
                            "tool_call_id": tool_call["id"],
                        }
                    )
                    logger.info("📁 Tool: Read %s", tool_call["args"]["path"])
                else:
                    logger.warning(
                        "Planning Agent tried to use unauthorized tool: %s",
                        tool_call["name"],
                    )

        # Step 2: Final structured output call
        logger.info("📋 Generating structured TechnicalPlan...")
        plan: Any = structured_llm.invoke(messages)

        # 🚨 STRUCTURAL ENFORCEMENT: Force a final Git push step for repo tasks
        repo_name = (
            state.trigger.repo_name
            if state.trigger and state.trigger.repo_name
            else None
        )
        if plan and repo_name and repo_name != "General" and len(plan.steps) > 0:
            last_step = plan.steps[-1]
            has_git_step = last_step.assigned_to == "ops" and any(
                kw in last_step.description.lower()
                for kw in ["git", "push", "commit", "branch"]
            )

            if not has_git_step:
                import re
                from datetime import datetime

                # Create a safe branch slug from the title
                slug = re.sub(r"[^a-z0-9]+", "-", plan.title.lower()).strip("-")[:30]
                # Fallback if slug is empty
                if not slug:
                    slug = "task-update"
                branch_name = f"feature/{slug}-{datetime.now().strftime('%m%d%H%M')}"

                git_step = ExecutionStep(
                    id=f"STEP-{len(plan.steps) + 1}",
                    description=f"Create/resume branch '{branch_name}', stage all changes, commit, and push to origin.",
                    assigned_to="ops",
                    target_repo=repo_name,
                    dependencies=[last_step.id],
                    verification_criteria=(
                        f"git checkout {branch_name} 2>/dev/null || git checkout -b {branch_name}; "
                        f"git add -A && git commit -m 'feat: {plan.title}' && "
                        f"git push -u origin {branch_name}"
                    ),
                )
                plan.steps.append(git_step)
                logger.info(
                    "🚨 Post-processed plan: Added mandatory Git push step for branch: %s",
                    branch_name,
                )

        if plan and repo_name:
            # 🚨 PATH SANITIZER: Strip .context/{repo}/ from ops verification_criteria
            # Ops runs inside the repo root, so these prefixes cause double-pathing.
            prefix = f".context/{repo_name}/"
            for step in plan.steps:
                if step.assigned_to == "ops" and step.verification_criteria:
                    if prefix in step.verification_criteria:
                        step.verification_criteria = step.verification_criteria.replace(
                            prefix, ""
                        )
                        logger.info(
                            "🧹 Path Sanitizer: Stripped '%s' from %s verification criteria",
                            prefix,
                            step.id,
                        )

        logger.info("✅ Planning Agent complete")
        if plan:
            logger.info("📋 Plan Title: %s", plan.title)
            logger.info("📝 Plan Summary: %s", plan.summary)
            for i, step in enumerate(plan.steps, 1):
                logger.info(
                    "   🔹 Step %s: %s (assigned to: %s)",
                    step.id,
                    step.description,
                    step.assigned_to,
                )
            if plan.definition_of_done:
                for item in plan.definition_of_done:
                    logger.info("   🏁 DoD: %s", item)
            logger.info("⚠️  Risk: %s", plan.estimated_risk)

        repo = (
            state.trigger.repo_name
            if state.trigger and state.trigger.repo_name
            else "unknown"
        )
        content = f"Planning is complete for the `{repo}` repository. The technical plan is ready for implementation."

        return {
            "messages": [AIMessage(content=content)],
            "task_plan": plan,
            "approval_status": ApprovalStatus.APPROVED,
        }
    except Exception as e:
        error_msg = f"Planning Agent failed: {str(e)}"
        logger.error("❌ %s", error_msg)
        return {
            "messages": [AIMessage(content=error_msg)],
            "error_message": error_msg,
        }
