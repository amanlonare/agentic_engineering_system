import uvicorn

from src.core.config import settings
from src.utils.logger import configure_logging

logger = configure_logging()

if __name__ == "__main__":
    logger.info(
        "🚀 Starting Agentic Engineering API Server on %s:%s",
        settings.API_HOST,
        settings.API_PORT,
    )
    uvicorn.run(
        "src.api.app:create_app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        factory=True,
        reload=True,  # Handy for local development
    )
