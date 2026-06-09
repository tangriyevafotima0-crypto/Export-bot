"""Structured logging setup for the Anti-Stalker Intelligence System.

Provides colored console output and file logging to data/logs/.
"""

import logging
import sys
from pathlib import Path


LOG_DIR = Path(__file__).parent.parent / "data" / "logs"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

COLORS = {
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[1;31m",
}
RESET = "\033[0m"


class ColoredFormatter(logging.Formatter):
    """Log formatter that adds ANSI color codes to console output."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with color codes.

        Args:
            record: The log record to format.

        Returns:
            Formatted log string with color codes.
        """
        color = COLORS.get(record.levelname, "")
        record.levelname = f"{color}{record.levelname}{RESET}"
        return super().format(record)


def get_logger(name: str) -> logging.Logger:
    """Create and return a configured logger instance.

    Creates a logger with both colored console output and file output.
    Log files are stored in data/logs/ directory.

    Args:
        name: Logger name, typically the module's __name__.

    Returns:
        Configured logging.Logger instance.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_formatter = ColoredFormatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    console_handler.setFormatter(console_formatter)

    file_handler = logging.FileHandler(
        LOG_DIR / "anti_stalker.log", encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    file_handler.setFormatter(file_formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
