import os
from typing import Any, Dict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from src.core.config_manager import app_config, config_manager
from src.core.state import EngineeringState
from src.schemas import StepExecutionRecord, StepStatus
from src.tools.codebase_tools import get_restricted_tools
from src.utils.config_loader import build_system_prompt, load_agent_persona
from src.utils.logger import configure_logging

logger = configure_logging("coder")


def _get_repo_tree(repo_name: str, max_depth: int = 3) -> str:
    """Recursively list the repo directory tree to pre-load for the LLM."""
    base_path = os.path.join(".context", repo_name)
    if not os.path.isdir(base_path):
        return f"Repository directory '.context/{repo_name}' not found."

    lines = [f".context/{repo_name}/"]
    _walk_tree(base_path, "", lines, current_depth=0, max_depth=max_depth)
    return (
        "\n".join(lines)
        if len(lines) > 1
        else f".context/{repo_name}/ (empty repository)"
    )


def _walk_tree(path: str, prefix: str, lines: list, current_depth: int, max_depth: int):
    """Helper to build an indented tree string."""
    if current_depth >= max_depth:
        return
    try:
        entries = sorted(os.listdir(path))
        entries = [
            e for e in entries if e != "__pycache__" and not e.startswith(".git")
        ]
        for i, entry in enumerate(entries):
            connector = "└── " if i == len(entries) - 1 else "├── "
            full_path = os.path.join(path, entry)
            if os.path.isdir(full_path):
                lines.append(f"{prefix}{connector}{entry}/")
                extension = "    " if i == len(entries) - 1 else "│   "
                _walk_tree(
                    full_path, prefix + extension, lines, current_depth + 1, max_depth
                )
            else:
                lines.append(f"{prefix}{connector}{entry}")
    except OSError:
        pass


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
    rework_context = ""

    # Check if this is a REWORK triggered by Ops failure
    is_rework = (
        "Verification failed" in instructions
        or "CHIEF ORCHESTRATOR: Verification failed" in instructions
    )

    failed_ops_step_id = None
    if state.task_plan:
        # Check if instructions contain a specific step ID
        for step in state.task_plan.steps:
            if step.id in instructions:
                # If it's a coder step, this is our target
                if step.assigned_to == "coder":
                    current_step = step
                    break
                # If it's an OPs step, find its coder dependency
                elif step.assigned_to == "ops":
                    failed_ops_step_id = step.id
                    rework_context = f"REWORK TRIGGERED BY {step.id} FAILURE: "
                    # Find a relevant coder step (e.g. the first one it depends on)
                    relevant_ids = [d for d in step.dependencies]
                    for s in state.task_plan.steps:
                        if s.id in relevant_ids and s.assigned_to == "coder":
                            current_step = s
                            break
                    if current_step:
                        break

        # Fallback 1: First uncompleted coder step
        if not current_step:
            for step in state.task_plan.steps:
                if step.assigned_to == "coder" and step.id not in (
                    state.completed_step_ids or []
                ):
                    current_step = step
                    break

        # Fallback 2: During rework, if still no step, target the MOST RECENT coder step
        if not current_step and is_rework:
            for step in reversed(state.task_plan.steps):
                if step.assigned_to == "coder":
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
        task_info = "General assistance required."
    else:
        repo = current_step.target_repo or (
            state.trigger.repo_name
            if state.trigger and state.trigger.repo_name
            else "unknown"
        )
        task_info = f"Current Step: {current_step.id}\nGoal: {current_step.description}"

        # Determine history record
        if is_rework and failed_ops_step_id:
            # IMPORTANT: We add a record for the FAILED OPS step to "clear" it in the Supervisor
            history = [
                StepExecutionRecord(
                    step_id=failed_ops_step_id,
                    status=StepStatus.COMPLETED,  # Marked as 'completed' by coder fix
                    agent="coder",
                    outcome=f"Applied fixes for verification failure in {failed_ops_step_id}.",
                )
            ]
            completed_ids = []  # Ops step status is enough to move forward
        elif current_step.id in (state.completed_step_ids or []):
            logger.info("🔄 Reworking completed step: %s", current_step.id)
            completed_ids = []
            history = [
                StepExecutionRecord(
                    step_id=current_step.id,
                    status=StepStatus.COMPLETED,
                    agent="coder",
                    outcome=f"Performed rework for step {current_step.id}.",
                )
            ]
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

    # PRE-LOAD REPO TREE so the LLM never needs to call list_directory
    repo_tree = _get_repo_tree(repo)
    logger.info("📂 Pre-loaded repo tree for '%s'", repo)

    # PRESERVE instructions and provide clear context
    full_instructions = (
        f"### REPOSITORY STRUCTURE (pre-loaded — do NOT call list_directory for these)\n"
        f"```\n{repo_tree}\n```\n\n"
        f"### WORKFLOW CONTEXT\n"
        f"{rework_context}{task_info}\n\n"
        f"### ORCHESTRATOR FEEDBACK (IMPORTANT)\n"
        f"{instructions}\n"
    )
    instructions = full_instructions

    logger.info(f"🔒 Locking tools to repository: {repo}")

    # 2. Setup Persona and Tools
    persona = load_agent_persona("coder")
    system_prompt = build_system_prompt(persona).replace("{repo_name}", repo)
    if state.is_lightweight:
        system_prompt = (
            "THIS IS A LIGHTWEIGHT task. Follow the Lightweight Task Protocol.\n\n"
            + system_prompt
        )

    tools = get_restricted_tools(repo)
    llm = config_manager.get_agent_llm("coder")
    llm_with_tools = llm.bind_tools(tools)

    # 3. Build Messages
    messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]
    messages.extend(
        state.messages
    )  # Full history — nodes only return final summary to state
    messages.append(HumanMessage(content=instructions))

    try:
        # 4. Tool-Calling Loop with Hard Cap
        tool_call_count = 0
        turn_tool_history: Dict[
            str, str
        ] = {}  # Track ALL calls: "tool(args)" -> result
        consecutive_dup_rounds = 0  # Force-break after N all-duplicate rounds
        # Configurable limits
        agent_cfg = app_config.agents.get("coder")
        MAX_TOOL_CALLS = agent_cfg.max_tool_calls if agent_cfg else 20
        MAX_DUP_ROUNDS = agent_cfg.max_duplicate_rounds if agent_cfg else 3

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

            all_duplicates_this_round = True

            for tool_call in response.tool_calls:
                current_call = f"{tool_call['name']}({str(tool_call['args'])})"

                # DETERMINISTIC LOOP PREVENTION: Intercept ANY repeat call in this turn
                if current_call in turn_tool_history:
                    prev_result = turn_tool_history[current_call]
                    logger.warning("🚫 Duplicate tool call detected: %s", current_call)
                    messages.append(
                        ToolMessage(
                            tool_call_id=tool_call["id"] or "",
                            content=(
                                f"⚠️ SUCCESS: You already called this and it succeeded (Result: {prev_result[:100]}...).\n"
                                f"Do NOT repeat the same write_file. If you're done, summarize and finish."
                            ),
                        )
                    )
                    continue

                all_duplicates_this_round = False
                tool_instance = next(
                    (t for t in tools if t.name == tool_call["name"]), None
                )
                if tool_instance:
                    result = str(tool_instance.invoke(tool_call["args"]))
                    messages.append(
                        ToolMessage(
                            tool_call_id=tool_call["id"] or "",
                            content=result,
                        )
                    )
                    # Cache result for loop prevention
                    turn_tool_history[current_call] = result
                else:
                    error_msg = f"Error: Tool {tool_call['name']} not available."
                    logger.warning(error_msg)
                    messages.append(
                        ToolMessage(
                            tool_call_id=tool_call["id"] or "",
                            content=error_msg,
                        )
                    )

            # FORCE-BREAK: If all calls in this round were duplicates, count it
            if all_duplicates_this_round:
                consecutive_dup_rounds += 1
                if (
                    MAX_DUP_ROUNDS is not None
                    and consecutive_dup_rounds >= MAX_DUP_ROUNDS
                ):
                    logger.warning(
                        "🛑 Force-breaking loop: %d consecutive all-duplicate rounds.",
                        MAX_DUP_ROUNDS,
                    )
                    messages.append(
                        AIMessage(
                            content="Exploration complete. I will now proceed to implement the required code."
                        )
                    )
                    break
            else:
                consecutive_dup_rounds = 0

            tool_call_count += 1

        if tool_call_count >= MAX_TOOL_CALLS:
            error_msg = f"⚠️ Coder Agent reached max tool calls ({MAX_TOOL_CALLS}). Forcing stop."
            logger.warning(error_msg)
            messages.append(AIMessage(content=error_msg))
            # NOTE: We still return history so the Supervisor can see the Coder "attempted" rework.
            # This prevents the supervisor from re-routing here infinitely.

        # 5. Extract Verification Scripts from final message (Manual tags + Automatic detection)
        import re

        final_content = str(messages[-1].content)
        script_matches = re.findall(
            r"\[VERIFICATION_SCRIPT:\s*([a-zA-Z0-9_\-\./]+)\]", final_content
        )

        # Fallback: Scan ToolMessages for any 'write_file' to tests/ directory
        for msg in messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc["name"] == "write_file":
                        path = tc["args"].get("path", "")
                        if "/tests/" in path and path.endswith(".py"):
                            # Clean the path to be relative to .context/{repo}/ for Ops
                            clean_path = path.replace(f".context/{repo}/", "")
                            if clean_path not in script_matches:
                                script_matches.append(clean_path)

        return {
            # Only return the FINAL summary message to shared state, not all internal tool calls.
            "messages": [messages[-1]],
            "completed_step_ids": completed_ids,
            "execution_history": history,  # Always return history, even if truncated by tool cap
            "verification_scripts": script_matches,
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
