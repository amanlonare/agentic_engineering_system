import os
from typing import Any, Dict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig

from src.core.config_manager import app_config, config_manager
from src.core.resource_manager import ResourceManager
from src.core.state import EngineeringState
from src.schemas import StepExecutionRecord, StepStatus
from src.tools.codebase_tools import get_restricted_tools
from src.utils.config_loader import build_system_prompt, load_agent_persona
from src.utils.logger import configure_logging

logger = configure_logging("coder")

# Global resource manager
resource_manager = ResourceManager()


async def _get_remote_repo_summary(repo_uri: str) -> str:
    """Provides a summarized view of a remote repository's structure."""
    try:
        items = await resource_manager.list_resource(repo_uri)
        return "\n".join([f"- {i}" for i in items])
    except Exception as e:
        return f"Error listing remote resource: {e}"


async def _get_repo_tree(repo_name: str, max_depth: int = 3) -> str:
    """Get repo tree via ephemeral clone or remote listing."""
    from src.core.graph_store import GraphStore

    graph_store = GraphStore()

    # Try to find the MCP URI from the graph store
    results = graph_store.execute_query(
        "MATCH (r:Repository {name: $name}) RETURN r.mcp_uri", {"name": repo_name}
    )

    if results and results[0][0]:
        mcp_uri = results[0][0]
        # Try remote listing first
        try:
            return await _get_remote_repo_summary(mcp_uri)
        except Exception:
            pass
        # Fall back to ephemeral clone
        try:
            local_path = await resource_manager.ensure_local_context(mcp_uri)
            lines = [f"{repo_name}/"]
            _walk_tree(local_path, "", lines, current_depth=0, max_depth=max_depth)
            return (
                "\n".join(lines)
                if len(lines) > 1
                else f"{repo_name}/ (empty repository)"
            )
        except Exception as e:
            return f"Could not load repo tree for {repo_name}: {e}"

    return f"Repository '{repo_name}' not found in knowledge graph."


def _walk_tree(path: str, prefix: str, lines: list, current_depth: int, max_depth: int):
    """Helper to build an indented tree string for local paths."""
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


async def coder_node(state: EngineeringState, config: RunnableConfig) -> Dict[str, Any]:
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
    is_rework = state.is_rework

    # 1. Identify Target Step and Repo via active_step_id
    failed_ops_step_id = None
    if state.task_plan and state.active_step_id:
        for step in state.task_plan.steps:
            if step.id == state.active_step_id:
                current_step = step
                break

    # Fallback/Rework logic
    if not current_step and state.task_plan:
        # If it's a rework but we don't have an active_step_id, find the failed step
        if is_rework:
            for step in state.task_plan.steps:
                last_record = next(
                    (
                        rec
                        for rec in reversed(state.execution_history or [])
                        if rec.step_id == step.id
                    ),
                    None,
                )
                if last_record and last_record.status == StepStatus.FAILED:
                    failed_ops_step_id = step.id
                    # If failed step is coder, use it. If ops, use its first coder dependency.
                    if step.assigned_to == "coder":
                        current_step = step
                    elif step.assigned_to == "ops":
                        relevant_ids = [d for d in step.dependencies]
                        for s in state.task_plan.steps:
                            if s.id in relevant_ids and s.assigned_to == "coder":
                                current_step = s
                                break
                    if current_step:
                        rework_context = f"REWORK TRIGGERED BY {step.id} FAILURE: "
                        break

        # Final fallback: First uncompleted coder step
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
                    outcome=(
                        f"Applied fixes for verification failure in "
                        f"{failed_ops_step_id}."
                    ),
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

    # PRE-LOAD REPO TREE
    if repo.startswith(app_config.system.protocol_prefix):
        repo_tree = await _get_remote_repo_summary(repo)
    else:
        repo_tree = await _get_repo_tree(repo)
    logger.info("📂 Pre-loaded repo tree for '%s'", repo)

    # PRESERVE instructions and provide clear context
    full_instructions = (
        f"### REPOSITORY STRUCTURE (do NOT call list_directory for these)\n"
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

    # --- Integrated Remote Tools ---
    from src.tools.gdrive import list_gdrive_folder, search_gdrive
    from src.tools.github import (
        create_github_issue,
        create_pull_request,
        list_github_issues,
    )

    tools.extend(
        [
            list_github_issues,
            create_github_issue,
            create_pull_request,
            search_gdrive,
            list_gdrive_folder,
        ]
    )

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
        MAX_TOOL_CALLS = (
            agent_cfg.max_tool_calls
            if agent_cfg
            else app_config.workflow.default_max_tool_calls
        )
        MAX_DUP_ROUNDS = agent_cfg.max_duplicate_rounds if agent_cfg else 3

        while tool_call_count < MAX_TOOL_CALLS:
            response = await llm_with_tools.ainvoke(messages, config=config)
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
                                f"⚠️ SUCCESS: You already called this and it succeeded "
                                f"(Result: {prev_result[:80]}...).\n"
                                f"Do NOT repeat the same write_file. If you're done, "
                                f"summarize and finish."
                            ),
                        )
                    )
                    continue

                all_duplicates_this_round = False
                tool_instance = next(
                    (t for t in tools if t.name == tool_call["name"]), None
                )
                if tool_instance:
                    # Handle both sync and async tools
                    if hasattr(tool_instance, "ainvoke"):
                        result = await tool_instance.ainvoke(tool_call["args"])
                    else:
                        result = tool_instance.invoke(tool_call["args"])

                    result_str = str(result)
                    messages.append(
                        ToolMessage(
                            tool_call_id=tool_call["id"] or "",
                            content=result_str,
                        )
                    )

                    # Log a snippet of the result for visibility
                    snippet = result_str[:500].replace("\n", " ")
                    if len(result_str) > 500:
                        snippet += "..."
                    logger.info("🛠️ Tool '%s' returned: %s", tool_call["name"], snippet)

                    # Cache result for loop prevention
                    turn_tool_history[current_call] = result_str
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
                            content=(
                                "Exploration complete. I will now proceed to "
                                "implement the required code."
                            )
                        )
                    )
                    break
            else:
                consecutive_dup_rounds = 0

            tool_call_count += 1

        if tool_call_count >= MAX_TOOL_CALLS:
            error_msg = (
                f"⚠️ Coder Agent reached max tool calls "
                f"({MAX_TOOL_CALLS}). Forcing stop."
            )
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
                        if "/tests/" in path and (
                            path.endswith(".py") or path.endswith(".js")
                        ):
                            # Extract the test-relative path regardless of prefix
                            test_idx = path.index("/tests/")
                            clean_path = path[
                                test_idx + 1 :
                            ]  # e.g., "tests/test_feature.py"
                            if clean_path not in script_matches:
                                script_matches.append(clean_path)

        return {
            # Only return the FINAL summary message to shared state, not all internal tool calls.
            "messages": [messages[-1]],
            "completed_step_ids": completed_ids,
            "execution_history": history,  # Always return history
            "verification_scripts": script_matches,
        }

    except Exception as e:
        logger.exception(f"Coder Agent failed unexpectedly: {e}")
        return {
            "messages": [
                AIMessage(content="Coder Agent failed due to an internal error.")
            ],
            "completed_step_ids": [],
            "execution_history": [],
        }
