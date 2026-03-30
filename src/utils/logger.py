import asyncio
import logging
import sys
from contextvars import ContextVar
from typing import Optional

# Global ContextVar to store logs for the current request context (thread-safe for async)
ui_log_queue: ContextVar[Optional[asyncio.Queue]] = ContextVar(
    "ui_log_queue", default=None
)


class ColoredFormatter(logging.Formatter):
    """Custom formatter to add colors to logs based on the logger name."""

    # ANSI Color Codes
    GREY = "\x1b[38;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    BLUE = "\x1b[34;20m"
    MAGENTA = "\x1b[35;20m"
    GREEN = "\x1b[32;20m"
    RESET = "\x1b[0m"

    COLORS = {
        "supervisor": RED,
        "planning": MAGENTA,
        "coder": BLUE,
        "ops": GREEN,
        "growth": YELLOW,
        "system": GREY,
    }

    def format(self, record):
        log_name = record.name.split(".")[-1]
        color = self.COLORS.get(log_name, self.GREY)

        # Format: TIMESTAMP | LEVEL | NAME | MESSAGE
        format_str = (
            f"%(asctime)s | %(levelname)-8s | "
            f"{color}%(name)-12s{self.RESET} | %(message)s"
        )
        formatter = logging.Formatter(format_str, datefmt="%Y-%m-%d %H:%M:%S")
        formatted_msg = formatter.format(record)

        # Push to UI queue if active
        queue = ui_log_queue.get()
        if queue:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.call_soon_threadsafe(queue.put_nowait, formatted_msg)
            except Exception:
                pass

        return formatted_msg


def configure_logging(name: str = "system"):
    """
    Standardizes logging across the system with timestamps and colors.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(ColoredFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger
