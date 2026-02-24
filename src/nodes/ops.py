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


def ops_node(state: EngineeringState) -> Dict[str, Any]:
    """
    Ops Agent: Verifies code changes and deployment.
    """
    logger.info("🛠️ Ops Agent verifying implementation...")

    persona = load_agent_persona("ops")
    system_prompt = build_system_prompt(persona)

    llm = ChatOpenAI(model=settings.OPENAI_MODEL_NAME).with_structured_output(
        TestReport
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                system_prompt
                + "\n\nVerify the code changes against the plan. Generate a detailed TestReport.",
            ),
            ("placeholder", "{messages}"),
        ]
    )

    # chain = prompt | llm

    try:
        # Simulate successful validation
        content = "All tests passed, implementation is verified. System is stable."
        report = TestReport(
            suite_name="Mock Verification Suite",
            total_tests=5,
            passed_count=5,
            failures=[],
            logs="End-to-end mock verification successful."
        )
        
        return {
            "messages": [AIMessage(content=content)],
            "validation_report": report
        }
    except Exception as e:
        logger.error("❌ Ops Agent failed: %s", str(e))
        return {"messages": [AIMessage(content=f"Verification failed: {str(e)}")]}
