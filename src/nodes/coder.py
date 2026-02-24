from typing import Any, Dict

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.core.config import settings
from src.core.state import EngineeringState
from src.utils.config_loader import build_system_prompt, load_agent_persona
from src.utils.logger import configure_logging

logger = configure_logging()


def coder_node(state: EngineeringState) -> Dict[str, Any]:
    """
    Coder Agent: Executes code changes and runs tests.
    """
    logger.info("💻 Coder Agent executing code changes...")

    persona = load_agent_persona("coder")
    system_prompt = build_system_prompt(persona)

    llm = ChatOpenAI(model=settings.OPENAI_MODEL_NAME)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                system_prompt
                + "\n\nExecute the assigned steps in the TechnicalPlan. Return the code changes.",
            ),
            ("placeholder", "{messages}"),
        ]
    )

    chain = prompt | llm

    try:
        # In a mock scenario, we identify the repo from the trigger
        repo = state.trigger.repo_name if state.trigger else "unknown"
        
        # Simulate LLM response or tool call outcomes
        content = f"Successfully updated `{repo}` repository. Now testing is required for these changes."
        
        return {
            "messages": [AIMessage(content=content)],
            "code_diffs": f"Mock implementation for {repo}."
        }
    except Exception as e:
        logger.error("❌ Coder Agent failed: %s", str(e))
        return {"messages": [AIMessage(content=f"Coding failed: {str(e)}")]}
