import argparse
import os
import shutil

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


def reset_long_term_memory():
    """Deletes the ChromaDB directory."""
    memory_path = "./long_term_memory"
    if os.path.exists(memory_path):
        try:
            shutil.rmtree(memory_path)
            logger.info(
                "✅ Successfully deleted long-term memory directory: %s", memory_path
            )
        except OSError as e:
            logger.error("❌ Failed to delete long-term memory: %s", e)
    else:
        logger.info("ℹ️ Long-term memory directory does not exist.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset the system state.")
    parser.add_argument(
        "--all", action="store_true", help="Reset everything including memory."
    )
    args = parser.parse_args()

    logger.info("🗑️  Starting reset process...")
    reset_database()

    if args.all:
        reset_long_term_memory()

    logger.info("✨ Reset complete.")
