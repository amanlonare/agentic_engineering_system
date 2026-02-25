import os
from src.core.config import settings
from src.utils.logger import configure_logging

logger = configure_logging("reset_db")


def reset_database():
    """Deletes the SQLite database file to allow for a fresh start."""
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")

    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            logger.info("✅ Successfully deleted database file: %s", db_path)
        except OSError as e:
            logger.error("❌ Failed to delete database: %s", e)
    else:
        logger.info("ℹ️ Database file '%s' does not exist. Nothing to reset.", db_path)


if __name__ == "__main__":
    logger.info("🗑️  Starting database reset...")
    reset_database()
    logger.info(
        "✨ Database reset complete. The next 'make run' will recreate it automatically."
    )
