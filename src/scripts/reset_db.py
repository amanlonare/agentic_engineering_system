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


def reset_evaluation_stores():
    """Deletes the isolated evaluation directories (vector and graph)."""
    eval_dirs = [settings.EVAL_CHROMA_DB_PATH, settings.EVAL_KUZU_DB_PATH]
    for eval_dir in eval_dirs:
        if os.path.exists(eval_dir):
            try:
                if os.path.isdir(eval_dir):
                    shutil.rmtree(eval_dir)
                    logger.info(
                        "✅ Successfully deleted evaluation directory: %s", eval_dir
                    )
                else:
                    os.remove(eval_dir)
                    logger.info("✅ Successfully deleted evaluation file: %s", eval_dir)
            except OSError as e:
                logger.error(
                    "❌ Failed to delete evaluation storage %s: %s", eval_dir, e
                )
        else:
            logger.info("ℹ️ Evaluation storage '%s' does not exist.", eval_dir)

    logger.info(
        "✅ Evaluation stores (vector/graph) reset. Results and test sets preserved."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset the system state.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Reset everything including memory (except evaluation).",
    )
    parser.add_argument(
        "--eval", action="store_true", help="Reset evaluation stores and results."
    )
    args = parser.parse_args()

    logger.info("🗑️  Starting reset process...")
    reset_database()

    if args.all:
        reset_long_term_memory()
        reset_evaluation_stores()

    if args.eval:
        reset_evaluation_stores()

    logger.info("✨ Reset complete.")
