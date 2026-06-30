"""
Standard logging configuration for the Entertainment Intelligence Platform.
Supports console output and rotating file logging.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Global handler cache to prevent duplicate handler instances and file-lock issues
_console_handler: logging.Handler | None = None
_file_handler: logging.Handler | None = None

def setup_logger(name: str = "eip") -> logging.Logger:
    """
    Configures and returns a standard Python logger.
    
    Ensures console and rotating file handlers are configured without duplicates.
    """
    global _console_handler, _file_handler

    # Read log level from environment
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    log_level = log_levels.get(log_level_str, logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Establish data/logs directory path using pathlib relative to this file
    log_dir = Path(__file__).resolve().parent.parent.parent / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    # Define standard format: %(asctime)s | %(levelname)s | %(name)s | %(message)s
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Configure StreamHandler for console output
    if _console_handler is None:
        _console_handler = logging.StreamHandler(sys.stdout)
        _console_handler.setFormatter(formatter)

    # Configure RotatingFileHandler for file output
    if _file_handler is None:
        _file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        _file_handler.setFormatter(formatter)

    # Attach handlers to the logger if not already present
    if _console_handler not in logger.handlers:
        logger.addHandler(_console_handler)

    if _file_handler not in logger.handlers:
        logger.addHandler(_file_handler)

    # Prevent duplicate logging from parent propagation
    if name != "":
        logger.propagate = False

    return logger

def get_logger(name: str) -> logging.Logger:
    """
    Retrieves or creates a configured logger with the given name.
    """
    return setup_logger(name)
