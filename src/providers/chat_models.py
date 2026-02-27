from langchain_openai import ChatOpenAI

from src.core.config import settings
from src.utils.logger import configure_logging

logger = configure_logging()


def get_chat_model():
    """
    Initializes and returns the configured ChatModel.
    Initially configured for OpenAI.
    """
    provider = settings.PRIMARY_MODEL_PROVIDER.lower()

    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            logger.warning(
                "OPENAI_API_KEY is missing. Using mock/placeholder fallback."
            )
            return None
        return ChatOpenAI(
            model=settings.OPENAI_MODEL_NAME,
            temperature=0,
            max_retries=5,
            api_key=settings.OPENAI_API_KEY,  # type: ignore
        )

    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
