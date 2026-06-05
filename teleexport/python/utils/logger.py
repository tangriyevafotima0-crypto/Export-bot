"""Logging configuration for TeleExport backend."""
import sys
import logging
from pathlib import Path

from ..core.config import TELEEXPORT_DIR


LOG_DIR = TELEEXPORT_DIR / "logs"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO, log_file: bool = True) -> logging.Logger:
    """Configure logging for the application.

    Logs to stderr (for Electron to capture) and optionally to a file.
    """
    logger = logging.getLogger("teleexport")
    logger.setLevel(level)

    # Clear existing handlers
    logger.handlers.clear()

    # Stderr handler (Electron captures this)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(level)
    stderr_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    logger.addHandler(stderr_handler)

    # File handler
    if log_file:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            LOG_DIR / "teleexport.log", encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger with the given name."""
    return logging.getLogger(f"teleexport.{name}")
