from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from langchain_aws import ChatBedrockConverse
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, SecretStr

from src.utils.logger import configure_logging

logger = configure_logging()


class LLMAgentConfig(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    region: Optional[str] = None
    thinking: bool = False
    thinking_budget: int = 32000


class LLMConfig(BaseModel):
    provider: str = "openai"
    default_model: str = "gpt-4o-mini"
    default_temperature: float = 0.0
    max_retries: int = 5
    region: str = "us-east-1"
    thinking: bool = False
    thinking_budget: int = 32000
    agents: Dict[str, LLMAgentConfig] = {}


class AgentLimits(BaseModel):
    max_tool_calls: int = 10
    max_duplicate_rounds: Optional[int] = None


class SystemConfig(BaseModel):
    plan_filename: str = "PLAN.md"
    plan_storage_base: str = "/tmp/agentic_plans"
    protocol_prefix: str = "mcp://"
    log_snippet_size: int = 500
    branch_prefix: str = "feature/"
    default_branch: str = "master"
    test_dir: str = "tests"


class WorkflowConfig(BaseModel):
    max_rework_attempts: int = 3
    max_follow_up_depth: int = 2
    default_max_tool_calls: int = 15


class AppConfig(BaseModel):
    llm: LLMConfig = LLMConfig()
    agents: Dict[str, AgentLimits] = {}
    workflow: WorkflowConfig = WorkflowConfig()
    system: SystemConfig = SystemConfig()


def merge_dicts(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge two dictionaries."""
    for key, value in overrides.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            merge_dicts(base[key], value)
        else:
            base[key] = value
    return base


class ConfigManager:
    _instance: Optional["ConfigManager"] = None
    config: AppConfig

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        from src.core.config import settings

        env = settings.APP_ENV.lower()
        root_dir = Path(__file__).parent.parent.parent
        config_dir = root_dir / "config"

        # Load default
        default_path = config_dir / "default.yaml"
        with open(default_path, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f) or {}

        # Load environment-specific override
        env_path = config_dir / f"{env}.yaml"
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                overrides = yaml.safe_load(f) or {}
                config_dict = merge_dicts(config_dict, overrides)
                logger.info("💾 Loaded configuration overrides from %s", env_path)
        else:
            logger.warning(
                "⚠️ No configuration overrides found for environment: %s", env
            )

        self.config = AppConfig(**config_dict)

    def get_agent_llm(self, agent_name: str) -> BaseChatModel:
        """Get a configured LangChain ChatModel (OpenAI or Bedrock) for an agent."""
        from src.core.config import settings

        app_cfg: AppConfig = self.config
        llm_cfg: LLMConfig = app_cfg.llm

        agent_cfg = llm_cfg.agents.get(agent_name)

        # Resolve provider
        provider = (
            agent_cfg.provider if agent_cfg and agent_cfg.provider else llm_cfg.provider
        )

        # Resolve model
        model = (
            agent_cfg.model if agent_cfg and agent_cfg.model else llm_cfg.default_model
        )

        # Resolve temperature
        temp = (
            agent_cfg.temperature
            if agent_cfg and agent_cfg.temperature is not None
            else llm_cfg.default_temperature
        )

        # Provider-specific initialization
        if provider == "bedrock":
            region = (
                agent_cfg.region if agent_cfg and agent_cfg.region else llm_cfg.region
            )
            logger.info(
                f"🤖 [Agent: {agent_name}] -> [Provider: bedrock] | "
                f"[Model: {model}] | [Region: {region}]"
            )
            return ChatBedrockConverse(
                model=model,
                temperature=temp,
                region_name=region,
                # Bedrock handles retries via botocore, parameter not supported here
            )

        # Default to OpenAI
        logger.info(
            f"🤖 [Agent: {agent_name}] -> [Provider: openai] | [Model: {model}]"
        )
        api_key = (
            SecretStr(settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        )

        return ChatOpenAI(
            model=model,
            temperature=temp,
            max_retries=llm_cfg.max_retries,
            api_key=api_key,
        )

    def get_aider_model_id(self, agent_name: str) -> str:
        """Get a model ID specifically formatted for Aider usage (e.g. bedrock/ prefix)."""
        app_cfg: AppConfig = self.config
        llm_cfg: LLMConfig = app_cfg.llm

        agent_cfg = llm_cfg.agents.get(agent_name)
        provider = (
            agent_cfg.provider if agent_cfg and agent_cfg.provider else llm_cfg.provider
        )
        model = (
            agent_cfg.model if agent_cfg and agent_cfg.model else llm_cfg.default_model
        )

        if provider == "bedrock":
            # For Bedrock models, Aider expects the raw model ID.
            # We allow regional prefixes (us., global., apac., jp.) to pass through
            # as they are required for cross-region and regional inference profiles.
            return f"bedrock/{model}"

        return model

    def get_agent_region(self, agent_name: str) -> str:
        """Resolve the AWS region for a specific agent, falling back to global defaults."""
        app_cfg: AppConfig = self.config
        llm_cfg: LLMConfig = app_cfg.llm
        return llm_cfg.region or "us-east-1"

    def get_agent_thinking(self, agent_name: str) -> bool:
        """Resolve if thinking mode is enabled for a specific agent."""
        app_cfg: AppConfig = self.config
        llm_cfg: LLMConfig = app_cfg.llm
        agent_cfg = llm_cfg.agents.get(agent_name)
        return agent_cfg.thinking if agent_cfg else llm_cfg.thinking

    def get_agent_thinking_budget(self, agent_name: str) -> int:
        """Resolve the thinking budget for a specific agent."""
        app_cfg: AppConfig = self.config
        llm_cfg: LLMConfig = app_cfg.llm
        agent_cfg = llm_cfg.agents.get(agent_name)
        return agent_cfg.thinking_budget if agent_cfg else llm_cfg.thinking_budget


# Global configuration object
app_config = ConfigManager().config
config_manager = ConfigManager()
