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
from src.schemas import NodeName, RouteDecision
from src.utils.logger import configure_logging

logger = configure_logging("supervisor")


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
        next_step = None
        if state.task_plan:
            for step in state.task_plan.steps:
                if step.id not in completed_set:
                    # Check dependencies are satisfied
                    deps_met = all(d in completed_set for d in step.dependencies)
                    if deps_met:
                        next_step = step
                        break

        if next_step:
            # 🎯 SHORT-CIRCUIT: Route directly for planned steps.
            # This bypasses the LLM to ensure 100% deterministic adherence to the plan.
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

        return {"next_action": next_node}

    except Exception as e:
        logger.error(f"Failed to route using LLM: {e}")
        # Safe fallback in case of LLM parse failure
        return {"next_action": NodeName.FINISH}
