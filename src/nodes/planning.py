import os
from typing import Any, Dict

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from src.core.config import settings
from src.core.state import EngineeringState
from src.schemas import ApprovalStatus, TechnicalPlan
from src.utils.config_loader import build_system_prompt, load_agent_persona
from src.utils.logger import configure_logging

logger = configure_logging("planning")

# Pre-load the architecture map once at import time
_ARCHITECTURE_MAP_PATH = os.path.join(".context", "architecture_map.md")


def _load_architecture_map() -> str:
    """Read the architecture map file and return its content."""
    try:
        with open(_ARCHITECTURE_MAP_PATH, "r") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning("⚠️ architecture_map.md not found at %s", _ARCHITECTURE_MAP_PATH)
        return "(Architecture map not available)"


def planning_node(state: EngineeringState) -> Dict[str, Any]:
    """
    Planning Agent: Designs technical implementation plans.

    This agent has NO tools. It receives the architecture map as injected
    context and produces a TechnicalPlan using a single structured LLM call.
    This prevents unnecessary file reading loops.
    """
    logger.info("🧠 Planning Agent designing plan...")

    # 1. Load Persona
    persona = load_agent_persona("planning")
    system_prompt = build_system_prompt(persona)

    # 2. Inject the architecture map directly into the prompt (Filtered by Repo)
    repo = (
        state.trigger.repo_name if state.trigger and state.trigger.repo_name else None
    )
    raw_map = _load_architecture_map()

    if repo:
        # Simple extraction: find the header for the repo and take everything until the next header
        import re

        # Find ## [Num]. [repo]
        pattern = rf"(## \d+\. {re.escape(repo)}.*?)(?=\n## \d+\. |\Z)"
        match = re.search(pattern, raw_map, re.DOTALL | re.IGNORECASE)
        if match:
            architecture_map = match.group(1).strip()
            logger.info("🎯 Filtered architecture map for repo: %s", repo)
        else:
            architecture_map = f"(No specific map entry found for repo '{repo}')\n\nFull Map:\n{raw_map}"
            logger.warning(
                "⚠️ Could not find repo '%s' in architecture map, falling back to full map.",
                repo,
            )
    else:
        architecture_map = raw_map

    full_prompt = (
        f"{system_prompt}\n\n"
        f"## Filtered Architecture Map for `{repo or 'General'}`:\n"
        f"```\n{architecture_map}\n```"
    )

    # 3. Single structured LLM call — no agent loop, no tools
    llm = ChatOpenAI(model=settings.OPENAI_MODEL_NAME, temperature=0)
    structured_llm = llm.with_structured_output(TechnicalPlan)

    try:
        # Build the user message from the state
        user_messages = [
            m.content for m in state.messages if hasattr(m, "content") and m.content
        ]
        task_description = (
            user_messages[-1] if user_messages else "No task description provided."
        )

        plan = structured_llm.invoke(
            [
                {"role": "system", "content": full_prompt},
                {"role": "user", "content": task_description},
            ]
        )

        logger.info("✅ Planning Agent complete (single LLM call, zero tool calls)")
        if plan:
            logger.info("📋 Plan Title: %s", plan.title)  # type: ignore[union-attr]
            logger.info("📝 Plan Summary: %s", plan.summary)  # type: ignore[union-attr]
            for i, step in enumerate(plan.steps, 1):  # type: ignore[union-attr]
                logger.info(
                    "   🔹 Step %s: %s (assigned to: %s)",
                    step.id,
                    step.description,
                    step.assigned_to,
                )
            if plan.definition_of_done:  # type: ignore[union-attr]
                for item in plan.definition_of_done:  # type: ignore[union-attr]
                    logger.info("   🏁 DoD: %s", item)
            logger.info("⚠️  Risk: %s", plan.estimated_risk)  # type: ignore[union-attr]

        repo = (
            state.trigger.repo_name
            if state.trigger and state.trigger.repo_name
            else "unknown"
        )
        content = f"Planning is complete for the `{repo}` repository. The technical plan is ready for implementation by the Coder."

        return {
            "messages": [AIMessage(content=content)],
            "task_plan": plan,
            "approval_status": ApprovalStatus.APPROVED,
        }
    except Exception as e:
        error_msg = f"Planning Agent failed: {str(e)}"
        logger.error("❌ %s", error_msg)
        return {
            "messages": [AIMessage(content=error_msg)],
            "error_message": error_msg,
        }
