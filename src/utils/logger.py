import logging
import sys


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
        format_str = f"%(asctime)s | %(levelname)-8s | {color}%(name)-12s{self.RESET} | %(message)s"
        formatter = logging.Formatter(format_str, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


def configure_logging(name: str = "system"):
    """
    Standardizes logging across the system with timestamps and colors.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(ColoredFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger
