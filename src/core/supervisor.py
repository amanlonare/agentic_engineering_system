"""
The Chief Orchestrator routing logic. Determines the `next_action` in the workflow.
"""

import warnings

from langchain_core.messages import AIMessage
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)
from langchain_core.runnables import RunnableConfig
from langfuse import observe

from src.core.config_manager import app_config, config_manager
from src.core.state import EngineeringState, NodeName
from src.core.workspace import WorkspaceManager
from src.prompts.supervisor import SUPERVISOR_SYSTEM_PROMPT
from src.schemas import GrowthRecommendationType, RouteDecision, StepStatus
from src.utils.logger import configure_logging

logger = configure_logging("supervisor")

# Heuristic for environmental errors that shouldn't immediately blame the Coder's logic
ENVIRONMENT_ERROR_PATTERNS = [
    r"ModuleNotFoundError",
    r"ImportError",
    r"pytest: command not found",
    r"unittest: command not found",
    r"No such file or directory: '.*requirements\.txt'",
    r"No such file or directory",
    r"Connection refused",
    r"Access denied",
    r"missing dependencies",
    r"dependencies",
]


def _build_follow_up_prompt(recommendations, depth: int = 1) -> str:
    """Build a context prompt summarizing Growth findings for Planning agent."""
    lines = [
        "GROWTH AGENT FINDINGS — Create an ACTION plan to fix these issues.",
        f"IMPORTANT: Use step IDs with prefix 'FU{depth}-' "
        f"(e.g., FU{depth}-STEP-1, FU{depth}-STEP-2) to avoid ID collisions.",
        "This is a follow-up plan. The analysis is already done — "
        "do NOT assign steps to `growth`.",
        "Assign steps to `coder` to fix code and `ops` to verify the fixes.",
        "MANDATORY: Instructions and verification scripts MUST use absolute imports "
        "(e.g., `from src.model.predictor import ...`).",
        "",
    ]
    for i, r in enumerate(recommendations, 1):
        lines.append(f"{i}. [{r.recommendation_type.value}] {r.analysis[:300]}")
        if r.affected_segments:
            lines.append(f"   Affected: {', '.join(r.affected_segments)}")
        if r.suggested_action:
            lines.append(f"   Action: {r.suggested_action}")
        if r.suggested_repo:
            lines.append(f"   Target Repo: {r.suggested_repo}")
        if r.drift_detected:
            lines.append(
                f"   ⚠️ Model drift detected (FP rate: {r.false_positive_rate})"
            )
    return "\n".join(lines)


def _check_growth_follow_up(state: EngineeringState, logger):
    """Check if accumulated growth recommendations warrant a follow-up plan.
    Returns a state update dict if follow-up is needed, None otherwise."""
    actionable = [
        r
        for r in (state.growth_recommendations or [])
        if r.recommendation_type != GrowthRecommendationType.NO_ACTION
    ]
    if actionable and state.follow_up_depth < app_config.workflow.max_follow_up_depth:
        logger.info(
            "📈 %d actionable growth recommendation(s) found. "
            "Creating follow-up plan (depth %d).",
            len(actionable),
            state.follow_up_depth + 1,
        )
        follow_up_prompt = _build_follow_up_prompt(
            actionable, state.follow_up_depth + 1
        )

        # Accumulate recommendations before clearing them so Ops can use them later
        new_notes = "\n".join(
            [
                (
                    f"- {r.analysis} (Action: {r.suggested_action})"
                    if r.suggested_action
                    else f"- {r.analysis}"
                )
                for r in actionable
            ]
        )
        accumulated = state.accumulated_growth_notes
        if accumulated:
            accumulated += "\n" + new_notes
        else:
            accumulated = new_notes

        return {
            "next_action": NodeName.PLANNING,
            "task_plan": None,
            "follow_up_depth": state.follow_up_depth + 1,
            "follow_up_context": follow_up_prompt,
            "growth_recommendations": [],
            "accumulated_growth_notes": accumulated,
            "verification_scripts": [],
            "messages": [AIMessage(content=follow_up_prompt)],
        }
    return None


@observe(name="Agent: Supervisor")
async def supervisor_node(
    state: EngineeringState, config: RunnableConfig, **kwargs
) -> dict:
    """
    The LangGraph node function that acts as the Supervisor.
    It inspects the state, queries the LLM, and returns the 'next_action'.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", category=UserWarning, message=".*Pydantic serializer warnings.*"
        )
        return await _supervisor_node_impl(state, config, **kwargs)


async def _supervisor_node_impl(
    state: EngineeringState, config: RunnableConfig, **kwargs
) -> dict:
    """
    The LangGraph node function that acts as the Supervisor.
    It inspects the state, queries the LLM, and returns the 'next_action'.
    """
    msg_type = state.trigger.type if state.trigger else "unknown"
    logger.info("👨‍💼 Supervisor evaluating state triggered by: %s", msg_type)

    # 0. Lightweight Detection (Heuristic)
    # If it's a new task (no messages yet or just the system/human trigger)
    human_messages = [m for m in state.messages if m.type == "human"]
    if human_messages and not state.task_plan:
        last_msg = human_messages[-1].content
        query = last_msg.lower() if isinstance(last_msg, str) else ""
        # Heuristic: No repo identifier AND (short query OR simple keywords)

        simple_keywords = [
            "print",
            "even numbers",
            "odd numbers",
            "hello world",
            "algorithm",
            "simple",
        ]
        has_simple_kw = any(kw in query for kw in simple_keywords)
        no_repo = state.trigger.repo_name == "General" if state.trigger else True

        if no_repo or has_simple_kw:
            logger.info("🚀 Routing to Planner for new task: %s", NodeName.PLANNING)
            return {"is_lightweight": True, "next_action": NodeName.PLANNING}

    # If any agent has set an error_message, stop immediately

    if state.error_message:
        logger.error(
            "🛑 Agent failure detected. Stopping. Reason: %s", state.error_message
        )
        return {"next_action": NodeName.FINISH}

    llm = config_manager.get_agent_llm("supervisor")

    if not llm:
        # Mock logic to test routing: If no messages from agents yet, go to planning.
        worker_messages = [m for m in state.messages if getattr(m, "type", "") == "ai"]
        next_action = NodeName.PLANNING if not worker_messages else NodeName.FINISH
        logger.info("👨‍💼 Supervisor decided next action (MOCK): %s", next_action)
        return {"next_action": next_action}

    # Retrieve real-time org summary from Graph DB
    workspace_manager = WorkspaceManager()
    org_summary = workspace_manager.get_org_summary()

    # Get GraphStore summary
    try:
        wm = WorkspaceManager()
        _ = wm.get_org_summary()  # Call to ensure connectivity/warm-up
    except Exception as e:
        logger.warning("Could not retrieve graph summary: %s", e)

    system_prompt = SystemMessagePromptTemplate.from_template(SUPERVISOR_SYSTEM_PROMPT)
    # We pass the full state context to help the supervisor route correctly
    human_prompt = HumanMessagePromptTemplate.from_template(
        "### WORKFLOW CONTEXT\n"
        "Current Trigger: {trigger_type}\n"
        "Targeted Repository: {repo_name}\n"
        "Static Task Plan:\n{task_plan}\n"
        "NEXT STEP TO EXECUTE: {next_step_directive}\n"
        "Completed Step IDs: {completed_step_ids}\n"
        "Approval Status: {approval_status}\n"
        "Validation Report: {validation_report}\n\n"
        "### RECENT MESSAGES\n"
        "Verify the messages below to see what the agents have ACTUALLY done.\n"
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            system_prompt,
            human_prompt,
            MessagesPlaceholder(variable_name="messages"),
            (
                "system",
                "Based on the Plan vs the Completed Steps vs the Messages, "
                "who acts next?",
            ),
        ]
    )

    # Structured output guarantees mapping strictly to RouteDecision schema
    chain = (prompt | llm.with_structured_output(RouteDecision)).with_config(
        {"run_name": "Supervisor: Decision"}
    )

    try:
        # 1. Format Plan Checklist for the LLM
        plan_checklist = "No Technical Plan exists."
        completed_set = set(state.completed_step_ids or [])
        if state.task_plan:
            checklist_items = []

            # Map step_id to latest execution record for display
            history_map = {rec.step_id: rec for rec in state.execution_history or []}

            for step in state.task_plan.steps:
                is_completed = step.id in completed_set

                # RE-VERIFICATION GATE:
                # If assigned to ops, check if it was actually ops who finished it last.
                if is_completed and step.assigned_to.lower() == "ops":
                    last_success = next(
                        (
                            rec
                            for rec in reversed(state.execution_history or [])
                            if rec.step_id == step.id
                            and rec.status == StepStatus.COMPLETED
                        ),
                        None,
                    )
                    # If last execution was NOT by ops, it's pending re-verification
                    if last_success and last_success.agent.lower() != "ops":
                        is_completed = False

                status = "[x]" if is_completed else "[ ]"
                record = history_map.get(step.id)
                outcome = f" | Outcome: {record.outcome[:100]}" if record else ""
                checklist_items.append(
                    f"{status} {step.id}: {step.description} "
                    f"(Assigned to: {step.assigned_to}){outcome}"
                )
            plan_checklist = "\n".join(checklist_items)

        # 2. Deterministic Next Step Resolver
        next_step = None
        if state.task_plan:
            # Check all steps in the plan that have execution history
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
                    # Rework needed!
                    is_env_rework = False
                    agent_map = {
                        "coder": NodeName.CODER,
                        "ops": NodeName.OPS,
                        "growth": NodeName.GROWTH,
                    }
                    # Count how many times this step has already been reworked
                    rework_count = sum(
                        1
                        for rec in (state.execution_history or [])
                        if rec.step_id == step.id and rec.status == StepStatus.FAILED
                    )
                    if rework_count >= app_config.workflow.max_rework_attempts:
                        logger.error(
                            "🛑 Step %s has failed %d times. Stopping loop.",
                            step.id,
                            rework_count,
                        )
                        # Check if Growth has actionable recommendations...
                        follow_up = _check_growth_follow_up(state, logger)
                        if follow_up:
                            return follow_up
                        return {
                            "next_action": NodeName.FINISH,
                            "is_rework_failure": True,
                            "rework_failure_reason": "Max rework attempts reached",
                        }

                    import re

                    is_env_error = any(
                        re.search(pattern, last_record.outcome, re.IGNORECASE)
                        for pattern in ENVIRONMENT_ERROR_PATTERNS
                    )

                    if is_env_error:
                        # If it's an environment error, attempt self-healing first (OPS)
                        # but fallback to CODER if it fails once.
                        if rework_count > 0:
                            next_node = NodeName.CODER
                            rework_msg = (
                                f"CHIEF ORCHESTRATOR: {step.id} failed due to a PERSISTENT ENVIRONMENT error.\n\n"
                                f"FAILURE DETAILS:\n{last_record.outcome}\n\n"
                                f"CODER: The environment remains broken after a self-healing attempt. "
                                f"Check manifest files (requirements.txt, package.json, etc.) for typos, placeholders, or missing packages and fix them."
                            )
                        else:
                            next_node = agent_map.get(
                                step.assigned_to.lower(), NodeName.CODER
                            )
                            rework_msg = (
                                f"CHIEF ORCHESTRATOR: {step.id} failed due to an ENVIRONMENT or DEPENDENCY error.\n\n"
                                f"FAILURE DETAILS:\n{last_record.outcome}\n\n"
                                f"{step.assigned_to.upper()}: This looks like an environment/setup issue. "
                                f"Follow the Three-Strike Loop to ensure all required packages are installed and configured."
                            )
                        is_env_rework = True
                    elif step.assigned_to.lower() == "ops":
                        next_node = NodeName.CODER
                        rework_msg = (
                            f"CHIEF ORCHESTRATOR: Verification failed for {step.id}.\n\n"
                            f"FAILURE DETAILS FROM OPS AGENT:\n{last_record.outcome}\n\n"
                            f"CODER: Analyse the failure above carefully and fix the root cause. "
                            f"Do NOT repeat what failed — change the approach."
                        )
                    else:
                        next_node = agent_map.get(
                            step.assigned_to.lower(), NodeName.CODER
                        )
                        rework_msg = (
                            f"CHIEF ORCHESTRATOR: {step.id} failed.\n\n"
                            f"FAILURE DETAILS:\n{last_record.outcome}\n\n"
                            f"{step.assigned_to.upper()}: Analyse the failure above "
                            "carefully and fix the root cause."
                        )

                    logger.info(
                        "🔄 Rework detected! Mode: %s. Routing %s to %s.",
                        "Environment" if is_env_error else "Logic",
                        step.id,
                        next_node,
                    )
                    return {
                        "next_action": next_node,
                        "is_rework": True,
                        "is_env_rework": is_env_rework,
                        "active_step_id": step.id,
                        "rework_count": rework_count,
                        "messages": [AIMessage(content=rework_msg)],
                    }

            # If no rework needed, find the first uncompleted step
            for step in state.task_plan.steps:
                is_completed = step.id in completed_set

                # RE-VERIFICATION GATE:
                if is_completed and step.assigned_to.lower() == "ops":
                    last_success = next(
                        (
                            rec
                            for rec in reversed(state.execution_history or [])
                            if rec.step_id == step.id
                            and rec.status == StepStatus.COMPLETED
                        ),
                        None,
                    )
                    if last_success and last_success.agent.lower() != "ops":
                        logger.info(
                            "🔄 Step %s (Ops) was last touched by %s. Forcing re-verification.",
                            step.id,
                            last_success.agent,
                        )
                        is_completed = False

                if not is_completed:
                    # Check dependencies are satisfied
                    deps_met = all(d in completed_set for d in step.dependencies)
                    if deps_met:
                        next_step = step
                        break

        if next_step:
            agent_map = {
                "coder": NodeName.CODER,
                "ops": NodeName.OPS,
                "growth": NodeName.GROWTH,
            }
            next_node = agent_map.get(next_step.assigned_to.lower(), NodeName.FINISH)

            logger.info("🎯 Deterministic route: %s → %s", next_step.id, next_node)
            instruction_msg = AIMessage(
                content=(
                    f"Chief Orchestrator: {next_step.assigned_to.upper()}, "
                    f"please execute {next_step.id}: {next_step.description}"
                )
            )
            return {
                "next_action": next_node,
                "active_step_id": next_step.id,
                "is_rework": False,
                "is_env_rework": False,
                "rework_count": 0,
                "messages": [instruction_msg],
            }

        # 3. Consult LLM for non-plan transitions (Planning, Finishing, Analysis)
        # De-duplicate and sort completed steps for the prompt
        clean_completed_ids = sorted(list(set(state.completed_step_ids or [])))

        logger.info("🔍 Supervisor evaluating state (LLM judgment required)...")
        if clean_completed_ids:
            logger.info("✅ Completed steps so far: %s", clean_completed_ids)
        else:
            logger.info("🆕 No steps completed yet.")

        # If we reach here, either next_step is None (plan done) or task_plan is None
        next_step_directive = (
            "ALL STEPS COMPLETE → route to FINISH "
            "(unless validation failed and you choose to retry)"
        )
        if not state.task_plan:
            next_step_directive = "NO PLAN EXISTS → route to PLANNING for construction."

        # Explicitly invoke the chain
        result = await chain.ainvoke(
            {
                "org_summary": org_summary,
                "trigger_type": state.trigger.type if state.trigger else "unknown",
                "task_plan": plan_checklist if state.task_plan else "None",
                "next_step_directive": next_step_directive,
                "completed_step_ids": str(clean_completed_ids),
                "execution_history": str(
                    [h.model_dump() for h in (state.execution_history or [])]
                ),
                "validation_report": (
                    str(state.validation_report) if state.validation_report else "None"
                ),
                "approval_status": (
                    str(state.approval_status) if state.approval_status else "None"
                ),
                "repo_name": state.trigger.repo_name if state.trigger else "General",
                "messages": state.messages,
            },
            config=config,
        )

        state_update = {}

        if isinstance(result, RouteDecision):
            reasoning = result.reasoning
            next_node = NodeName(result.next_node)

            if result.rejection_message:
                logger.warning(
                    "🚫 Supervisor rejected query: %s", result.rejection_message
                )
                state_update["messages"] = [AIMessage(content=result.rejection_message)]

            if result.target_repo and state.trigger:
                logger.info(
                    "🎯 Supervisor identified target repo: %s", result.target_repo
                )
                state.trigger.repo_name = result.target_repo
                state_update["trigger"] = state.trigger

        else:
            next_node = NodeName.FINISH
            reasoning = "Invalid model output, falling back to FINISH."

        logger.info("👨‍💼 Supervisor decided: %s", next_node)
        logger.info("🧐 Reasoning: %s", reasoning)

        # If finishing, check for pending growth recommendations
        if next_node == NodeName.FINISH:
            follow_up = _check_growth_follow_up(state, logger)
            if follow_up:
                state_update.update(follow_up)
                return state_update

        state_update["next_action"] = next_node
        return state_update

    except Exception as e:
        logger.error("Error in supervisor node: %s", e)
        # Safe fallback in case of LLM parse failure
        return {"next_action": NodeName.FINISH}
