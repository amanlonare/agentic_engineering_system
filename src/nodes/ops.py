from typing import Any, Dict, List, cast

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from src.core.config_manager import app_config, config_manager
from src.core.state import EngineeringState
from src.schemas import StepExecutionRecord, StepStatus, TestReport
from src.tools.codebase_tools import get_ops_tools
from src.utils.config_loader import build_system_prompt, load_agent_persona
from src.utils.logger import configure_logging

logger = configure_logging("ops")


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
        if state.verification_scripts:
            instructions += f"\nVerification Scripts to run: {', '.join(state.verification_scripts)}"

        if current_step.verification_criteria:
            instructions += (
                f"\nVerification Criteria: {current_step.verification_criteria}"
            )

    logger.info(f"🔒 Locking tools to repository: {repo}")

    # 2. Setup Persona and Tools
    persona = load_agent_persona("ops")
    system_prompt = build_system_prompt(persona)
    tools = get_ops_tools(repo)

    llm = config_manager.get_agent_llm("ops")
    llm_with_tools = llm.bind_tools(tools)

    messages: List[BaseMessage] = [SystemMessage(content=system_prompt)]
    messages.extend(
        state.messages
    )  # Full history — nodes only return final summary to state
    messages.append(HumanMessage(content=instructions))

    try:
        # 3. Tool-Calling Loop
        tool_call_count = 0
        turn_tool_history: Dict[str, str] = {}  # Track ALL calls in this turn

        # Configurable limits
        agent_cfg = app_config.agents.get("ops")
        MAX_TOOL_CALLS = agent_cfg.max_tool_calls if agent_cfg else 10

        while tool_call_count < MAX_TOOL_CALLS:
            response = llm_with_tools.invoke(messages)
            messages.append(response)

            if not response.tool_calls:
                break

            for tool_call in response.tool_calls:
                current_call = f"{tool_call['name']}({str(tool_call['args'])})"

                # DETERMINISTIC LOOP PREVENTION: Intercept repeat calls
                if current_call in turn_tool_history:
                    prev_result = turn_tool_history[current_call]
                    logger.warning(
                        f"🚫 Duplicate tool call detected in OPs: {current_call}"
                    )
                    messages.append(
                        ToolMessage(
                            tool_call_id=tool_call["id"],
                            content=(
                                f"⚠️ DETERMINISTIC STOP: You already called {current_call} in this turn.\n"
                                f"RESULT: {prev_result}\n"
                                f"Do NOT repeat this call. Verification must proceed."
                            ),
                        )
                    )
                    continue

                tool_instance = next(
                    (t for t in tools if t.name == tool_call["name"]), None
                )
                if tool_instance:
                    result = tool_instance.invoke(tool_call["args"])
                    messages.append(
                        ToolMessage(tool_call_id=tool_call["id"], content=str(result))
                    )
                    # Cache result
                    turn_tool_history[current_call] = str(result)
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
        structured_llm = config_manager.get_agent_llm("ops").with_structured_output(
            TestReport
        )

        # Invoke returns TestReport as requested by with_structured_output
        report = cast(
            TestReport,
            structured_llm.invoke(
                messages
                + [
                    HumanMessage(
                        content="Finalize the TestReport based on your findings. Be honest about failures."
                    )
                ]
            ),
        )

        # CRITICAL FIX: Override LLM "hallucination" of success if we saw a non-fatal command failure
        actual_command_failure = False
        failure_details = ""
        for msg in messages:
            if isinstance(msg, ToolMessage) and "Exit Code:" in msg.content:
                content = str(msg.content)
                # Ignore Exit Code 128 (branch already exists)
                if "Exit Code: 128" in content and "fatal: a branch named" in content:
                    continue
                # Ignore Exit Code 1 (nothing to commit)
                if (
                    "Exit Code: 1" in content
                    and "nothing to commit, working tree clean" in content
                ):
                    continue

                # Basic check for non-zero exit code
                if "Exit Code: 0" not in content:
                    actual_command_failure = True
                    failure_details = content  # Capture the full STDERR + exit code
                    logger.warning(
                        "🚨 Detected actual command failure in tool outputs. Overriding report.success to False."
                    )
                    break

        if actual_command_failure:
            report.success = False

        # 5. Extract Branch Name (if a git push occurred)
        branch_name = None
        for msg in messages:
            if isinstance(msg, ToolMessage) and "git push" in str(msg.content):
                pass

        # Look for the final git branch name in the LLM's final response
        last_content = str(getattr(messages[-1], "content", ""))
        if report.success and "feature/issue-" in last_content:
            import re

            match = re.search(r"feature/issue-[\w\-]+", last_content)
            if match:
                branch_name = match.group(0)

        # 6. Populate Execution History
        if completed_ids and current_step:
            status = StepStatus.COMPLETED if report.success else StepStatus.FAILED
            # Include the full command failure output so the Supervisor can relay it to the Coder
            if failure_details:
                outcome = f"Verification Failed.\n\nCOMMAND OUTPUT:\n{failure_details}"
            else:
                outcome = f"Verification {'Passed' if report.success else 'Failed'}. {report.logs or ''}"
            history = [
                StepExecutionRecord(
                    step_id=current_step.id,
                    status=status,
                    agent="ops",
                    outcome=outcome,
                )
            ]

        response_payload: Dict[str, Any] = {
            # Only return the FINAL summary message to shared state, not all internal tool calls.
            # This prevents state.messages from growing unboundedly with every tool call made.
            "messages": [messages[-1]],
            "validation_report": report,
            "completed_step_ids": completed_ids if report.success else [],
            "execution_history": history,
        }

        if branch_name:
            # We use a state update for branch_name if the global state schema supports it,
            # or append it to the outcome history. Since EngineeringState currently has no
            # explicit `branch_name` field, we will inject it into the final message instead.
            last_msg_content = str(getattr(messages[-1], "content", ""))
            if isinstance(last_msg_content, str):
                messages[-1].content = (
                    last_msg_content + f"\n\n[STATE_INJECT:BRANCH:{branch_name}]"
                )

        return response_payload
    except Exception:
        logger.exception("Ops Agent failed unexpectedly")
        return {
            "messages": [
                AIMessage(content="Ops Agent failed due to an internal error.")
            ],
            "completed_step_ids": [],
            "execution_history": [],
        }
