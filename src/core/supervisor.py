"""
The Chief Orchestrator routing logic. Determines the `next_action` in the workflow.
"""

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

logger = configure_logging()


def supervisor_node(state: EngineeringState) -> dict:
    """
    The LangGraph node function that acts as the Supervisor.
    It inspects the state, queries the LLM, and returns the 'next_action'.
    """
    logger.info(
        f"👨‍💼 Supervisor evaluating state triggered by: {state.trigger.type if state.trigger else 'unknown'}"
    )

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
        "Payload: {trigger_payload}\n"
        "Targeted Repository: {repo_name}\n"
        "Static Task Plan (The Goal): {task_plan}\n"
        "Approval Status: {approval_status}\n"
        "Validation Report: {validation_report}\n\n"
        "### RECENT MESSAGES (The Reality of what happened)\n"
        "Verify the messages below to see what the agents have ACTUALLY done so far. "
        "If a message says 'testing is required' or 'implementation complete', DO NOT repeat that step.\n"
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            system_prompt,
            human_prompt,
            MessagesPlaceholder(variable_name="messages"),
            ("system", "Based on the Reality (Messages) vs the Goal (Plan), who acts next?"),
        ]
    )

    # We use LLM structured output to guarantee it maps strictly to our RouteDecision schema
    chain = prompt | llm.with_structured_output(RouteDecision)

    try:
        # We explicitly type the result to avoid Pyright errors
        result = chain.invoke(
            {
                "trigger_type": state.trigger.type if state.trigger else "unknown",
                "trigger_payload": str(state.trigger.payload if state.trigger else {}),
                "task_plan": str(state.task_plan) if state.task_plan else "None",
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
            # Safely cast the string back to the NodeName enum
            try:
                next_node = NodeName(result.next_node)
            except ValueError:
                logger.warning(
                    f"Supervisor returned invalid node name: {result.next_node}. Routing to FINISH."
                )
                next_node = NodeName.FINISH
        elif isinstance(result, dict):
            reasoning = result.get("reasoning", "No explicit reasoning provided.")
            raw_node = result.get("next_node", "FINISH")
            try:
                next_node = NodeName(raw_node)
            except ValueError:
                next_node = NodeName.FINISH
        else:
            next_node = NodeName.FINISH
            reasoning = "Invalid model output, falling back to FINISH."

        logger.info(f"👨‍💼 Supervisor decided: {next_node}")
        logger.info(f"🧐 Reasoning: {reasoning}")

        # We return a dict that represents the updates to the State
        return {"next_action": next_node}

    except Exception as e:
        logger.error(f"Failed to route using LLM: {e}")
        # Safe fallback in case of LLM parse failure
        return {"next_action": NodeName.FINISH}
