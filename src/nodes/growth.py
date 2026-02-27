from typing import Any, Dict

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.core.config import settings
from src.core.state import EngineeringState
from src.schemas import GrowthRecommendation, GrowthRecommendationType
from src.utils.config_loader import build_system_prompt, load_agent_persona
from src.utils.logger import configure_logging

logger = configure_logging("growth")


def growth_node(state: EngineeringState) -> Dict[str, Any]:
    """
    Growth Agent: Analyzes user metrics and proposes strategies.
    Returns a structured GrowthRecommendation with a routing signal.
    """
    logger.info("📈 Growth Agent analyzing metrics...")

    persona = load_agent_persona("growth")
    system_prompt = build_system_prompt(persona)

    llm = ChatOpenAI(model=settings.OPENAI_MODEL_NAME)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                system_prompt
                + "\n\nAnalyze the request and provide your recommendation.",
            ),
            ("placeholder", "{messages}"),
        ]
    )

    chain = prompt | llm

    try:
        repo = (
            state.trigger.repo_name
            if state.trigger and state.trigger.repo_name
            else "main-app"
        )

        # Mock: simulate a data-driven recommendation
        analysis = (
            f"Analyzed user engagement metrics for `{repo}`. "
            f"Findings suggest improvements in retention could be achieved by "
            f"optimizing the current flow."
        )
        
        # Only suggest planning if we aren't already executing a plan
        rec_type = (
            GrowthRecommendationType.REQUIRES_PLANNING
            if not state.task_plan
            else GrowthRecommendationType.NO_ACTION
        )
        
        recommendation = GrowthRecommendation(
            analysis=analysis,
            recommendation_type=rec_type,
            suggested_repo=repo,
        )

        content = f"{analysis}\n\nrecommendation_type: {rec_type.value}"

        # Identify which step in the plan was just completed
        completed_ids = []
        if state.task_plan:
            for step in state.task_plan.steps:
                if step.assigned_to == "growth" and step.id not in (
                    state.completed_step_ids or []
                ):
                    completed_ids.append(step.id)
                    logger.info("✅ Growth completed step: %s", step.id)
                    break

        return {
            "messages": [AIMessage(content=content)],
            "growth_recommendation": recommendation,
            "completed_step_ids": completed_ids,
        }
    except Exception as e:
        error_msg = f"Growth Agent failed: {str(e)}"
        logger.error("❌ %s", error_msg)
        return {
            "messages": [AIMessage(content=error_msg)],
            "error_message": error_msg,
        }
