from typing import Any, Dict

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.core.config import settings
from src.core.state import EngineeringState
from src.schemas import ApprovalStatus, TechnicalPlan
from src.utils.config_loader import build_system_prompt, load_agent_persona
from src.utils.logger import configure_logging

logger = configure_logging()


def planning_node(state: EngineeringState) -> Dict[str, Any]:
    """
    Planning Agent: Researches and designs technical implementation plans.
    """
    logger.info("🧠 Planning Agent researching task...")

    # Load Persona from YAML
    persona = load_agent_persona("planning")
    system_prompt = build_system_prompt(persona)

    # Initialize LLM with structured output
    llm = ChatOpenAI(model=settings.OPENAI_MODEL_NAME).with_structured_output(
        TechnicalPlan
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                system_prompt
                + "\n\nCreate a detailed TechnicalPlan to address the user trigger.",
            ),
            ("placeholder", "{messages}"),
        ]
    )

    chain = prompt | llm

    try:
        plan: TechnicalPlan = chain.invoke({"messages": state.messages})  # type: ignore[assignment]
        logger.info("✅ Planning Agent generated plan")
        
        repo = state.trigger.repo_name if state.trigger else "unknown"
        content = f"Planning is complete for the `{repo}` repository. The technical plan is ready for implementation by the Coder."
        
        return {
            "messages": [
                AIMessage(content=content)
            ],
            "task_plan": plan,
            "approval_status": ApprovalStatus.APPROVED
        }
    except Exception as e:
        logger.error("❌ Planning Agent failed: %s", str(e))
        return {"messages": [AIMessage(content=f"Planning failed: {str(e)}")]}
