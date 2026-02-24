"""
Centralized logging configuration.
"""

import logging


def configure_logging():
    logging.basicConfig(level=logging.INFO)
    return logging.getLogger("agentic-engineering-system")
