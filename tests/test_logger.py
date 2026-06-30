"""
Tests for checking logger robustness, handlers configuration, and file output.
"""

import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from src.utils.logger import setup_logger, get_logger

def test_logger_file_creation_and_writing() -> None:
    """Verifies that app.log is created and written to when log messages are dispatched."""
    # Ensure logging configuration gets executed
    logger = get_logger("test_file_logger")
    
    # Retrieve path to app.log
    project_root = Path(__file__).resolve().parent.parent
    log_file = project_root / "data" / "logs" / "app.log"
    
    # Assert log directory and file were created
    assert log_file.parent.exists()
    assert log_file.exists()
    
    # Log a message and check it is output to app.log
    test_message = "UNIT_TEST_MARKER_MESSAGE_LOG_FILE"
    logger.info(test_message)
    
    with open(log_file, "r", encoding="utf-8") as f:
        logs = f.read()
        
    assert test_message in logs
    assert " | INFO | test_file_logger | " in logs

def test_rotating_handler_configuration() -> None:
    """Verifies RotatingFileHandler configuration parameters match requirements."""
    logger = get_logger("test_rotation_logger")
    
    # Filter for RotatingFileHandlers
    file_handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
    assert len(file_handlers) == 1
    
    handler = file_handlers[0]
    # Check maxBytes, backupCount, and encoding
    assert handler.maxBytes == 5 * 1024 * 1024
    assert handler.backupCount == 5
    assert handler.encoding == "utf-8"

def test_prevent_duplicate_handlers() -> None:
    """Verifies setup_logger doesn't duplicate handlers if invoked repeatedly."""
    logger = get_logger("test_duplicate_logger")
    
    # Ensure initial state has exactly 2 handlers (console, file)
    assert len(logger.handlers) == 2
    
    # Call setup_logger and get_logger repeatedly
    setup_logger("test_duplicate_logger")
    get_logger("test_duplicate_logger")
    
    # Assert handler count remains exactly 2
    assert len(logger.handlers) == 2
