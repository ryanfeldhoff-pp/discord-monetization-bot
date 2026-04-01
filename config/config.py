"""
Configuration management for Discord monetization bot.

Loads settings from environment variables and config files.
"""

import os
from typing import Dict, Optional
import json


class Config:
    """Configuration container."""

    # Discord
    DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
    DISCORD_GUILD_ID: int = int(os.getenv("DISCORD_GUILD_ID", "0"))

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./discord_bot.db"
    )

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_ENABLED: bool = os.getenv("REDIS_ENABLED", "true").lower() == "true"

    # PrizePicks API
    PRIZEPICKS_API_BASE: str = os.getenv(
        "PRIZEPICKS_API_BASE",
        "https://api.prizepicks.com"
    )
    PRIZEPICKS_API_KEY: str = os.getenv("PRIZEPICKS_API_KEY", "")

    # XP System
    XP_VALUES: Dict[str, int] = {
        "message": 5,
        "entry_shared": 25,
        "entry_tailed": 10,
        "poll_participation": 15,
        "tournament_participation": 50,
        "tournament_win": 200,
        "helping_member": 30,
    }

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE", None)

    @classmethod
    def from_file(cls, config_file: str) -> "Config":
        """
        Load config from JSON file.

        Args:
            config_file: Path to config JSON file

        Returns:
            Config instance
        """
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                data = json.load(f)

                # Update class attributes
                for key, value in data.items():
                    if hasattr(cls, key.upper()):
                        setattr(cls, key.upper(), value)

        return cls

    @classmethod
    def validate(cls) -> bool:
        """
        Validate required configuration.

        Returns:
            True if valid, raises exception otherwise
        """
        required = ["DISCORD_TOKEN", "DISCORD_GUILD_ID", "PRIZEPICKS_API_KEY"]

        for field in required:
            if not getattr(cls, field, None):
                raise ValueError(f"Missing required config: {field}")

        return True

    @classmethod
    def to_dict(cls) -> Dict:
        """
        Convert config to dictionary.

        Returns:
            Dict of all config values
        """
        return {
            key: getattr(cls, key)
            for key in dir(cls)
            if key.isupper() and not key.startswith("_")
        }
