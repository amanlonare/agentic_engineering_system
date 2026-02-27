from typing import Any, Dict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI

from src.core.config import settings
from src.core.state import EngineeringState
from src.schemas import StepExecutionRecord, StepStatus
from src.tools.codebase_tools import get_restricted_tools
from src.utils.config_loader import build_system_prompt, load_agent_persona
from src.utils.logger import configure_logging

logger = configure_logging("coder")

MAX_TOOL_CALLS = 10


def coder_node(state: EngineeringState) -> Dict[str, Any]:
    """
    Coder Agent: Executes code changes using restricted tools.
    """
    logger.info("💻 Coder Agent starting execution...")

    # 0. Extract raw instructions from messages
    last_message = state.messages[-1].content if state.messages else ""
    instructions = str(last_message)
    history = []

    # 1. Identify Target Step and Repo
    current_step = None
    if state.task_plan:
        # Check if instructions contain a specific step ID (e.g., "Current Plan Step [STEP-1]")
        for step in state.task_plan.steps:
            if step.id in instructions and step.assigned_to == "coder":
                current_step = step
                break

        if not current_step:
            logger.warning(
                "⚠️ No explicit Step ID found in instructions. Falling back to first uncompleted coder step."
            )
            for step in state.task_plan.steps:
                if step.assigned_to == "coder" and step.id not in (
                    state.completed_step_ids or []
                ):
                    current_step = step
                    break

    if not current_step:
        repo = (
            state.trigger.repo_name
            if state.trigger and state.trigger.repo_name
            else "unknown"
        )
        logger.info(
            "ℹ️ No specific step identified. Operating in general assistance mode."
        )
        completed_ids = []
    else:
        repo = current_step.target_repo or (
            state.trigger.repo_name
            if state.trigger and state.trigger.repo_name
            else "unknown"
        )
        # Ensure we don't return an ID that's already in the completed list
        if current_step.id in (state.completed_step_ids or []):
            logger.warning(
                "⚠️ Supervisor requested step %s which is already complete. Skipping marking it again.",
                current_step.id,
            )
            completed_ids = []
            history = []
        else:
            completed_ids = [current_step.id]
            history = [
                StepExecutionRecord(
                    step_id=current_step.id,
                    status=StepStatus.COMPLETED,
                    agent="coder",
                    outcome="Successfully completed coding tasks for this step.",
                )
            ]

        instructions = (
            f"Current Plan Step [{current_step.id}]: {current_step.description}"
        )

    logger.info(f"🔒 Locking tools to repository: {repo}")

    # 2. Setup Persona and Tools
    persona = load_agent_persona("coder")
    system_prompt = build_system_prompt(persona).replace("{repo_name}", repo)

    tools = get_restricted_tools(repo)
    llm = ChatOpenAI(model=settings.OPENAI_MODEL_NAME, temperature=0.2, max_retries=5)
    llm_with_tools = llm.bind_tools(tools)

    # 3. Build Messages
    messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]
    messages.extend(state.messages)
    messages.append(HumanMessage(content=instructions))

    try:
        # 4. Tool-Calling Loop with Hard Cap
        tool_call_count = 0

        while tool_call_count < MAX_TOOL_CALLS:
            response = llm_with_tools.invoke(messages)
            messages.append(response)

            if not response.tool_calls:
                logger.info("✅ Coder Agent has completed its tool calls.")
                break  # Agent is done

            logger.info(
                "🛠️ Coder Agent calling tools: %s",
                [tc["name"] for tc in response.tool_calls],
            )
            for tool_call in response.tool_calls:
                tool_instance = next(
                    (t for t in tools if t.name == tool_call["name"]), None
                )
                if tool_instance:
                    result = tool_instance.invoke(tool_call["args"])
                    messages.append(
                        ToolMessage(
                            tool_call_id=tool_call["id"] or "",
                            content=str(result),
                        )
                    )
                else:
                    error_msg = f"Error: Tool {tool_call['name']} not available."
                    logger.warning(error_msg)
                    messages.append(
                        ToolMessage(
                            tool_call_id=tool_call["id"] or "",
                            content=error_msg,
                        )
                    )

            tool_call_count += 1

        if tool_call_count >= MAX_TOOL_CALLS:
            error_msg = f"⚠️ Coder Agent reached max tool calls ({MAX_TOOL_CALLS}). Forcing stop."
            logger.warning(error_msg)
            messages.append(AIMessage(content=error_msg))
            # Do not complete the step if forced to stop

        return {
            "messages": messages,
            "completed_step_ids": completed_ids,
            "execution_history": history,
        }

    except Exception:
        logger.exception("Coder Agent failed unexpectedly")
        return {
            "messages": [
                AIMessage(content="Coder Agent failed due to an internal error.")
            ],
            "completed_step_ids": [],
            "execution_history": [],
        }
