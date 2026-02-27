from typing import Any, Dict, List, cast

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
from src.schemas import StepExecutionRecord, StepStatus, TestReport
from src.tools.codebase_tools import get_ops_tools
from src.utils.config_loader import build_system_prompt, load_agent_persona
from src.utils.logger import configure_logging

logger = configure_logging("ops")

MAX_TOOL_CALLS = 10


def ops_node(state: EngineeringState) -> Dict[str, Any]:
    """
    Ops Agent: Verifies code changes and deployment.
    """
    logger.info("🛠️ Ops Agent starting verification...")

    # 1. Identify Target Step and Repo (Standard compliance)
    last_message = state.messages[-1].content if state.messages else ""
    instructions = str(last_message)
    current_step = None
    history = []
    completed_ids = []

    if state.task_plan:
        for step in state.task_plan.steps:
            if step.id in instructions and step.assigned_to == "ops":
                current_step = step
                break

        if not current_step:
            logger.warning(
                "⚠️ No explicit Step ID found. Falling back to first uncompleted ops step."
            )
            for step in state.task_plan.steps:
                if step.assigned_to == "ops" and step.id not in (
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
            "ℹ️ No specific step identified. Operating in general verification mode."
        )
    else:
        repo = current_step.target_repo or (
            state.trigger.repo_name
            if state.trigger and state.trigger.repo_name
            else "unknown"
        )
        if current_step.id in (state.completed_step_ids or []):
            logger.warning(
                "⚠️ Supervisor requested step %s which is already complete.",
                current_step.id,
            )
        else:
            completed_ids = [current_step.id]

        instructions = (
            f"Current Plan Step [{current_step.id}]: {current_step.description}"
        )

    logger.info(f"🔒 Locking tools to repository: {repo}")

    # 2. Setup Persona and Tools
    persona = load_agent_persona("ops")
    system_prompt = build_system_prompt(persona)
    tools = get_ops_tools(repo)

    llm = ChatOpenAI(model=settings.OPENAI_MODEL_NAME, temperature=0.0, max_retries=5)
    llm_with_tools = llm.bind_tools(tools)

    messages: List[BaseMessage] = [SystemMessage(content=system_prompt)]
    messages.extend(state.messages)
    messages.append(HumanMessage(content=instructions))

    try:
        # 3. Tool-Calling Loop
        tool_call_count = 0
        while tool_call_count < MAX_TOOL_CALLS:
            response = llm_with_tools.invoke(messages)
            messages.append(response)

            if not response.tool_calls:
                break

            for tool_call in response.tool_calls:
                tool_instance = next(
                    (t for t in tools if t.name == tool_call["name"]), None
                )
                if tool_instance:
                    result = tool_instance.invoke(tool_call["args"])
                    messages.append(
                        ToolMessage(tool_call_id=tool_call["id"], content=str(result))
                    )
                else:
                    messages.append(
                        ToolMessage(
                            tool_call_id=tool_call["id"],
                            content=f"Error: Tool {tool_call['name']} not found.",
                        )
                    )

            tool_call_count += 1

        # 4. Generate Structured TestReport (Phase 2)
        logger.info("📋 Finalizing structured TestReport...")
        structured_llm = ChatOpenAI(
            model=settings.OPENAI_MODEL_NAME, temperature=0.0, max_retries=5
        ).with_structured_output(TestReport)
        # Invoke returns TestReport as requested by with_structured_output
        report = cast(
            TestReport,
            structured_llm.invoke(
                messages
                + [
                    HumanMessage(
                        content="Finalize the TestReport based on your findings."
                    )
                ]
            ),
        )

        # 5. Populate Execution History
        if completed_ids and current_step:
            status = StepStatus.COMPLETED if report.success else StepStatus.FAILED
            outcome = f"Verification {'Passed' if report.success else 'Failed'}. {report.logs[:200] if report.logs else ''}"
            history = [
                StepExecutionRecord(
                    step_id=current_step.id,
                    status=status,
                    agent="ops",
                    outcome=outcome,
                )
            ]

        return {
            "messages": messages,
            "validation_report": report,
            "completed_step_ids": completed_ids if report.success else [],
            "execution_history": history,
        }
    except Exception:
        logger.exception("Ops Agent failed unexpectedly")
        return {
            "messages": [
                AIMessage(content="Ops Agent failed due to an internal error.")
            ],
            "completed_step_ids": [],
            "execution_history": [],
        }
