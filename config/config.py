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

    # Pillar 3: Community Events
    TACO_TUESDAY_CHANNEL_ID: int = int(os.getenv("TACO_TUESDAY_CHANNEL_ID", "0"))
    TOURNAMENT_CHANNEL_ID: int = int(os.getenv("TOURNAMENT_CHANNEL_ID", "0"))
    GAMEDAY_CATEGORY_ID: int = int(os.getenv("GAMEDAY_CATEGORY_ID", "0"))
    ARCHIVE_CATEGORY_ID: int = int(os.getenv("ARCHIVE_CATEGORY_ID", "0"))
    SPORTS_SCHEDULE_API_URL: str = os.getenv("SPORTS_SCHEDULE_API_URL", "")
    SPORTS_SCHEDULE_API_KEY: str = os.getenv("SPORTS_SCHEDULE_API_KEY", "")

    # Pillar 4: Referral Amplifier
    REFERRAL_CHANNEL_ID: int = int(os.getenv("REFERRAL_CHANNEL_ID", "0"))
    CHALLENGES_CHANNEL_ID: int = int(os.getenv("CHALLENGES_CHANNEL_ID", "0"))
    WIN_SHARING_CHANNEL_ID: int = int(os.getenv("WIN_SHARING_CHANNEL_ID", "0"))
    AMBASSADOR_ROLE_ID: int = int(os.getenv("AMBASSADOR_ROLE_ID", "0"))
    WIN_WEBHOOK_SECRET: str = os.getenv("WIN_WEBHOOK_SECRET", "")
    RESTRICTED_STATES: list = json.loads(
        os.getenv("RESTRICTED_STATES", '["NY", "NV", "ID", "WA", "MT"]')
    )

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
