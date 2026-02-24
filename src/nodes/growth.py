from typing import Any, Dict

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.core.config import settings
from src.core.state import EngineeringState
from src.schemas import TestReport
from src.utils.config_loader import build_system_prompt, load_agent_persona
from src.utils.logger import configure_logging

logger = configure_logging()


def growth_node(state: EngineeringState) -> Dict[str, Any]:
    """
    Growth Agent: Analyzes user metrics and proposes strategies.
    """
    logger.info("📈 Growth Agent analyzing metrics...")

    persona = load_agent_persona("growth")
    system_prompt = build_system_prompt(persona)

    llm = ChatOpenAI(model=settings.OPENAI_MODEL_NAME).with_structured_output(
        TestReport
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                system_prompt
                + "\n\nAnalyze the user conversion and retention metrics. Generate a TestReport summarizing your findings.",
            ),
            ("placeholder", "{messages}"),
        ]
    )

    chain = prompt | llm

    try:
        # Simulate growth analysis identifying a repo
        repo = state.trigger.repo_name if state.trigger else "main-app"
        content = f"To implement this growth strategy, the `{repo}` repository should be updated."
        
        return {
            "messages": [AIMessage(content=content)],
        }
    except Exception as e:
        logger.error("❌ Growth Agent failed: %s", str(e))
        return {"messages": [AIMessage(content=f"Growth analysis failed: {str(e)}")]}
