"""Logging configuration."""

import logging
import sys
from pathlib import Path


def setup_logging(debug: bool = False) -> None:
    """Set up logging.

    Args:
        debug: Whether to enable debug logging.
    """
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    level = logging.DEBUG if debug else logging.INFO
    
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    
    # File handler
    file_handler = logging.FileHandler(log_dir / "bot.log")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
