import logging
from typing import Any

from src.core.config import settings
from src.prompts.subtasks import (
    OPS_DIAGNOSTIC_REPORT,
    PLANNING_FINAL_PLAN,
    PLANNING_SLUG_EXTRACTOR,
)
from src.prompts.supervisor import SUPERVISOR_SYSTEM_PROMPT
from src.utils.config_loader import build_system_prompt, load_agent_persona

logger = logging.getLogger("prompt_manager")


class LocalPrompt:
    """Mock Langfuse Prompt object for local fallback."""

    def __init__(self, name: str, content: str):
        self.name = name
        self.prompt = content
        self.config = {"description": "Local fallback version"}

    def compile(self, **kwargs) -> str:
        """Simple string replacement for variable injection."""
        res = self.prompt
        for k, v in kwargs.items():
            res = res.replace(f"{{{k}}}", str(v))
        return res

    def get_langchain_prompt(self):
        """Simulates Langfuse get_langchain_prompt by returning a ChatPromptTemplate."""
        from langchain_core.prompts import ChatPromptTemplate

        return ChatPromptTemplate.from_template(self.prompt)


class PromptManager:
    """Handles fetching prompts from Langfuse or falling back to local files."""

    def __init__(self):
        self._lf_client = None

    @property
    def lf_client(self):
        if not self._lf_client:
            from src.core.tracing import get_langfuse_client

            self._lf_client = get_langfuse_client()
        return self._lf_client

    def get_prompt(self, name: str) -> Any:
        """
        Retrieves a prompt. If USE_LANGFUSE_PROMPTS is True, tries Langfuse first.
        Otherwise (or on failure), falls back to local definitions.
        """
        if settings.USE_LANGFUSE_PROMPTS:
            try:
                prompt = self.lf_client.get_prompt(name)
                # Success: return remote prompt
                return prompt
            except Exception as e:
                logger.warning(
                    f"⚠️ Failed to fetch prompt '{name}' from Langfuse: {e}. Falling back to local."
                )

        # Local Fallback Registry
        if name == "supervisor-system":
            return LocalPrompt(name, SUPERVISOR_SYSTEM_PROMPT)
        elif name == "planning-system":
            persona = load_agent_persona("planning")
            return LocalPrompt(name, build_system_prompt(persona))
        elif name == "planning-slug-extractor":
            return LocalPrompt(name, PLANNING_SLUG_EXTRACTOR)
        elif name == "planning-final-plan":
            return LocalPrompt(name, PLANNING_FINAL_PLAN)
        elif name == "coder-system":
            persona = load_agent_persona("coder")
            return LocalPrompt(name, build_system_prompt(persona))
        elif name == "ops-system":
            persona = load_agent_persona("ops")
            return LocalPrompt(name, build_system_prompt(persona))
        elif name == "ops-diagnostic-report":
            return LocalPrompt(name, OPS_DIAGNOSTIC_REPORT)

        raise ValueError(f"Prompt '{name}' not found in local fallback registry.")


# Singleton instance
prompt_manager = PromptManager()
