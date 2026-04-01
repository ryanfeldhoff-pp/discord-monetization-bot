"""Bot configuration settings."""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """Bot configuration settings."""

    token: str = os.getenv("DISCORD_TOKEN", "")
    prefix: str = os.getenv("BOT_PREFIX", "!")
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    database_path: str = os.getenv("DATABASE_PATH", "data/bot.db")
    
    def __post_init__(self) -> None:
        """Validate settings after initialization."""
        if not self.token:
            raise ValueError("DISCORD_TOKEN environment variable is required")
