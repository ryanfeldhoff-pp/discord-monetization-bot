"""Logging middleware."""

import logging
import sys
from typing import Optional


def setup_logging(debug: bool = False) -> None:
    """Set up logging configuration.

    Args:
        debug: Whether to enable debug logging.
    """
    level = logging.DEBUG if debug else logging.INFO
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(level)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(handler)
