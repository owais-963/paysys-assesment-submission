"""Logging goes to stderr only, so stdout stays clean for --json output."""
import logging
import sys


def configure_logging(level: str) -> logging.Logger:
    logger = logging.getLogger("support_tool")
    logger.setLevel(level.upper())
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.handlers = [handler]
    logger.propagate = False
    return logger
