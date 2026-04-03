"""
Main Discord bot entrypoint for PrizePicks Discord Monetization.

This module initializes and runs the Discord bot with all cogs loaded.
Handles graceful shutdown, logging configuration, and environment setup.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands

from src.services.analytics import AnalyticsService
from src.services.prizepicks_api import PrizepicksAPIClient


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class PrizepicksBot(commands.Bot):
    """Extended Discord bot with PrizePicks integration."""

    def __init__(self, *args, **kwargs):
        """Initialize the bot with required intents and configuration."""
        super().__init__(*args, **kwargs)
        self.analytics: Optional[AnalyticsService] = None
        self.prizepicks_client: Optional[PrizepicksAPIClient] = None
        self._ready = asyncio.Event()

    async def setup_hook(self) -> None:
        """Set up services and load all cogs."""
        logger.info("Setting up bot services and cogs...")

        # Initialize analytics service
        analytics_config = {
            "provider": os.getenv("ANALYTICS_PROVIDER", "webhook"),
            "webhook_url": os.getenv("ANALYTICS_WEBHOOK_URL"),
            "api_key": os.getenv("ANALYTICS_API_KEY"),
        }
        self.analytics = AnalyticsService(analytics_config)

        # Initialize PrizePicks API client
        api_config = {
            "base_url": os.getenv("PRIZEPICKS_API_URL", "https://api.prizepicks.com"),
            "api_key": os.getenv("PRIZEPICKS_API_KEY"),
            "timeout": int(os.getenv("PRIZEPICKS_API_TIMEOUT", "30")),
        }
        self.prizepicks_client = PrizepicksAPIClient(api_config)

        # Load all cogs
        await self._load_cogs()

        logger.info("Bot setup complete")

    async def _load_cogs(self) -> None:
        """Load all cogs from the cogs directory."""
        cogs_dir = Path(__file__).parent / "cogs"

        if not cogs_dir.exists():
            logger.warning(f"Cogs directory not found: {cogs_dir}")
            return

        for cog_file in cogs_dir.glob("*.py"):
            if cog_file.name.startswith("_"):
                continue

            cog_name = cog_file.stem
            try:
                await self.load_extension(f"src.cogs.{cog_name}")
                logger.info(f"Loaded cog: {cog_name}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog_name}: {e}", exc_info=True)

    async def on_ready(self) -> None:
        """Handle bot ready event."""
        logger.info(f"Bot logged in as {self.user} (ID: {self.user.id})")
        self._ready.set()

    async def close(self) -> None:
        """Graceful shutdown handler."""
        logger.info("Bot shutting down...")

        # Flush analytics
        if self.analytics:
            await self.analytics.flush()

        # Close API client
        if self.prizepicks_client:
            await self.prizepicks_client.close()

        await super().close()

    async def wait_until_ready(self) -> None:
        """Wait for the bot to be ready."""
        await self._ready.wait()


def create_bot() -> PrizepicksBot:
    """
    Create and configure the Discord bot instance.

    Returns:
        PrizepicksBot: Configured bot instance.
    """
    # Configure intents
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guild_members = True
    intents.guilds = True

    # Create bot instance
    bot = PrizepicksBot(
        command_prefix=os.getenv("BOT_PREFIX", "!"),
        intents=intents,
        description="PrizePicks Discord Monetization Bot",
        help_command=commands.DefaultHelpCommand(),
    )

    return bot


async def main() -> None:
    """Main entry point for the bot."""
    # Load environment variables
    from dotenv import load_dotenv

    load_dotenv()

    # Validate required environment variables
    required_vars = ["DISCORD_TOKEN"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        return

    # Create and run bot
    bot = create_bot()

    try:
        async with bot:
            await bot.start(os.getenv("DISCORD_TOKEN"))
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
    except Exception as e:
        logger.error(f"Bot encountered an error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
