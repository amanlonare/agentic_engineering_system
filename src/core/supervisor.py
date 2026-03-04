"""
The Chief Orchestrator routing logic. Determines the `next_action` in the workflow.
"""

from langchain_core.messages import AIMessage
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)

from src.core.state import EngineeringState
from src.prompts.supervisor import SUPERVISOR_SYSTEM_PROMPT
from src.providers.chat_models import get_chat_model
from src.schemas import GrowthRecommendationType, NodeName, RouteDecision, StepStatus
from src.utils.logger import configure_logging

logger = configure_logging("supervisor")

MAX_FOLLOW_UP_DEPTH = 2


def _build_follow_up_prompt(recommendations, depth: int = 1) -> str:
    """Build a context prompt summarizing Growth findings for the follow-up Planning agent."""
    lines = [
        "GROWTH AGENT FINDINGS — Create an ACTION plan to fix these issues.",
        f"IMPORTANT: Use step IDs with prefix 'FU{depth}-' (e.g., FU{depth}-STEP-1, FU{depth}-STEP-2) to avoid ID collisions.",
        "This is a follow-up plan. The analysis is already done — do NOT assign steps to `growth`.",
        "Assign steps to `coder` to fix code and `ops` to verify the fixes.",
        "MANDATORY: Instructions and verification scripts MUST use absolute imports (e.g., `from src.model.predictor import ...`).",
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
            lines.append(f"   ⚠️ Model drift detected (false positive rate: {r.false_positive_rate})")
    return "\n".join(lines)


def _check_growth_follow_up(state: EngineeringState, logger):
    """Check if accumulated growth recommendations warrant a follow-up plan.
    Returns a state update dict if follow-up is needed, None otherwise."""
    actionable = [
        r for r in (state.growth_recommendations or [])
        if r.recommendation_type != GrowthRecommendationType.NO_ACTION
    ]
    if actionable and state.follow_up_depth < MAX_FOLLOW_UP_DEPTH:
        logger.info(
            "📈 %d actionable growth recommendation(s) found. Creating follow-up plan (depth %d).",
            len(actionable),
            state.follow_up_depth + 1,
        )
        follow_up_prompt = _build_follow_up_prompt(actionable, state.follow_up_depth + 1)
        return {
            "next_action": NodeName.PLANNING,
            "task_plan": None,
            "follow_up_depth": state.follow_up_depth + 1,
            "follow_up_context": follow_up_prompt,
            "growth_recommendations": [],
            "verification_scripts": [],
            "messages": [AIMessage(content=follow_up_prompt)],
        }
    return None


def supervisor_node(state: EngineeringState) -> dict:
    """
    The LangGraph node function that acts as the Supervisor.
    It inspects the state, queries the LLM, and returns the 'next_action'.
    """
    logger.info(
        f"👨‍💼 Supervisor evaluating state triggered by: {state.trigger.type if state.trigger else 'unknown'}"
    )

    # If any agent has set an error_message, stop immediately
    if state.error_message:
        logger.error(
            f"🛑 Agent failure detected. Stopping execution. Reason: {state.error_message}"
        )
        return {"next_action": NodeName.FINISH}

    llm = get_chat_model()

    if not llm:
        # Mock logic to test routing: If no messages from agents yet, go to planning. Otherwise FINISH.
        worker_messages = [m for m in state.messages if getattr(m, "type", "") == "ai"]
        next_action = NodeName.PLANNING if not worker_messages else NodeName.FINISH
        logger.info(f"👨‍💼 Supervisor decided next action (MOCK): {next_action}")
        return {"next_action": next_action}

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
                "Based on the Plan vs the Completed Steps vs the Messages, who acts next?",
            ),
        ]
    )

    # We use LLM structured output to guarantee it maps strictly to our RouteDecision schema
    chain = prompt | llm.with_structured_output(RouteDecision)

    try:
        # 1. Format Plan Checklist for the LLM
        plan_checklist = "No Technical Plan exists."
        completed_set = set(state.completed_step_ids or [])
        if state.task_plan:
            checklist_items = []

            # Map step_id to latest execution record for display
            history_map = {rec.step_id: rec for rec in state.execution_history or []}

            for step in state.task_plan.steps:
                status = "[x]" if step.id in completed_set else "[ ]"
                record = history_map.get(step.id)
                outcome = f" | Outcome: {record.outcome[:100]}" if record else ""
                checklist_items.append(
                    f"{status} {step.id}: {step.description} (Assigned to: {step.assigned_to}){outcome}"
                )
            plan_checklist = "\n".join(checklist_items)

        # 2. Deterministic Next Step Resolver
        # We first check if ANY recently attempted step failed and needs rework.
        # This prevents "looping" if a step was mistakenly marked as complete but fails verification.
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
                    agent_map = {
                        "coder": NodeName.CODER,
                        "ops": NodeName.OPS,
                        "growth": NodeName.GROWTH,
                    }
                    # Count how many times this step has already been reworked
                    MAX_REWORK_ATTEMPTS = 3
                    rework_count = sum(
                        1
                        for rec in (state.execution_history or [])
                        if rec.step_id == step.id and rec.status == StepStatus.FAILED
                    )
                    if rework_count >= MAX_REWORK_ATTEMPTS:
                        logger.error(
                            "🛑 Step %s has failed %d times. Stopping to prevent infinite loop.",
                            step.id,
                            rework_count,
                        )
                        # Check if Growth has actionable recommendations before giving up
                        follow_up = _check_growth_follow_up(state, logger)
                        if follow_up:
                            return follow_up
                        return {"next_action": NodeName.FINISH}

                    if step.assigned_to.lower() == "ops":
                        next_node = NodeName.CODER
                    else:
                        next_node = agent_map.get(
                            step.assigned_to.lower(), NodeName.CODER
                        )
                    
                    logger.info(
                        "🔄 Rework detected! Verification for %s failed. Routing back to %s.",
                        step.id,
                        next_node,
                    )
                    rework_msg = (
                        f"CHIEF ORCHESTRATOR: Verification failed for {step.id}.\n\n"
                        f"FAILURE DETAILS FROM OPS AGENT:\n{last_record.outcome}\n\n"
                        f"{step.assigned_to.upper()}: Analyse the failure above carefully and fix the root cause. "
                        f"Do NOT repeat what failed — change the approach based on the error."
                    )
                    return {
                        "next_action": next_node,
                        "messages": [AIMessage(content=rework_msg)],
                    }

            # If no rework needed, find the first uncompleted step
            for step in state.task_plan.steps:
                if step.id not in completed_set:
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
                content=f"Chief Orchestrator: {next_step.assigned_to.upper()}, please execute {next_step.id}: {next_step.description}"
            )
            return {
                "next_action": next_node,
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
        next_step_directive = "ALL STEPS COMPLETE → route to FINISH (unless validation failed and you choose to retry)"
        if not state.task_plan:
            next_step_directive = "NO PLAN EXISTS → route to PLANNING for construction."

        # Explicitly invoke the chain
        result = chain.invoke(
            {
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
            }
        )

        if isinstance(result, RouteDecision):
            reasoning = result.reasoning
            next_node = NodeName(result.next_node)
        else:
            next_node = NodeName.FINISH
            reasoning = "Invalid model output, falling back to FINISH."

        logger.info("👨‍💼 Supervisor decided: %s", next_node)
        logger.info("🧐 Reasoning: %s", reasoning)

        # If finishing, check for pending growth recommendations
        if next_node == NodeName.FINISH:
            follow_up = _check_growth_follow_up(state, logger)
            if follow_up:
                return follow_up

        return {"next_action": next_node}

    except Exception as e:
        logger.error(f"Failed to route using LLM: {e}")
        # Safe fallback in case of LLM parse failure
        return {"next_action": NodeName.FINISH}
