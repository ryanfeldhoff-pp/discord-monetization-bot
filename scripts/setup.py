"""Setup script for the bot."""

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def setup_directories() -> None:
    """Create necessary directories."""
    directories = ["data", "logs", "config"]

    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        logger.info(f"Created directory: {directory}")


def setup_environment() -> None:
    """Set up environment variables."""
    env_file = Path(".env")
    if not env_file.exists():
        logger.warning(".env file not found")
        logger.info("Copy .env.example to .env and fill in your settings")
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    setup_directories()
    setup_environment()
    logger.info("Setup complete!")
