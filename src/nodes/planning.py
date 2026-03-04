from typing import Any, Dict

from langchain_core.messages import AIMessage

from src.core.config_manager import config_manager
from src.core.state import EngineeringState
from src.schemas import ApprovalStatus, TechnicalPlan
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
    from langchain_core.messages import HumanMessage

    user_messages = [
        m.content for m in state.messages if isinstance(m, HumanMessage) and m.content
    ]

    if state.follow_up_context:
        task_description = state.follow_up_context
        logger.info(
            "📈 Using follow-up context from Growth recommendations as task description."
        )
    elif user_messages:
        task_description = user_messages[
            0
        ]  # Use the FIRST human message (original request)
    elif state.trigger and "description" in state.trigger.payload:
        task_description = state.trigger.payload.get(
            "description", "No task description provided."
        )
        logger.info("ℹ️ Using task description from trigger payload fallback.")
    else:
        task_description = "No task description provided."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task_description},
    ]

    try:
        # Step 1: Allow the agent to call tools
        response = llm_with_tools.invoke(messages)

        if response.tool_calls:
            logger.info("🛠️ Planning Agent calling tools: %s", response.tool_calls)
            messages.append(response)  # Add assistant message with tool calls

            for tool_call in response.tool_calls:
                if tool_call["name"] == "read_file":
                    # Execute tool call
                    result = read_file.invoke(tool_call["args"])
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": str(result),
                        }
                    )
                else:
                    logger.warning(
                        "⚠️ Planning Agent tried to call unknown tool: %s",
                        tool_call["name"],
                    )

        # Step 2: Final structured output call
        logger.info("📋 Generating structured TechnicalPlan...")
        plan: Any = structured_llm.invoke(messages)

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
