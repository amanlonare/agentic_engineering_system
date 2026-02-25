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
            f"Based on user engagement metrics, the `{repo}` repository "
            f"should implement a new promotion strategy to improve retention. "
            f"This requires adding a rewards module and updating the notification system."
        )
        rec_type = GrowthRecommendationType.REQUIRES_PLANNING
        recommendation = GrowthRecommendation(
            analysis=analysis,
            recommendation_type=rec_type,
            suggested_repo=repo,
        )

        content = f"{analysis}\n\nrecommendation_type: {rec_type.value}"

        return {
            "messages": [AIMessage(content=content)],
            "growth_recommendation": recommendation,
        }
    except Exception as e:
        error_msg = f"Growth Agent failed: {str(e)}"
        logger.error("❌ %s", error_msg)
        return {
            "messages": [AIMessage(content=error_msg)],
            "error_message": error_msg,
        }
