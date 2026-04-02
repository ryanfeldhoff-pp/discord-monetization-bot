"""Main Discord bot class."""

import logging

from discord.ext import commands, tasks

from config.settings import Settings
from src.cogs import setup_cogs

logger = logging.getLogger(__name__)


class MonetizationBot(commands.Bot):
    """Discord bot for monetization features."""

    def __init__(self, settings: Settings, *args, **kwargs):
        """Initialize the bot.

        Args:
            settings: Configuration settings.
        """
        super().__init__(*args, **kwargs)
        self.settings = settings
        self.logger = logger

    async def setup_hook(self) -> None:
        """Set up bot hooks and load cogs."""
        logger.info("Setting up bot hooks")
        await setup_cogs(self)
        self.sync_commands.start()

    @tasks.loop(hours=1)
    async def sync_commands(self) -> None:
        """Sync slash commands with Discord."""
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

    async def on_ready(self) -> None:
        """Called when bot is ready."""
        logger.info(f"{self.user} is now running!")

    async def on_error(self, event: str, *args, **kwargs) -> None:
        """Handle bot errors."""
        logger.exception(f"Error in {event}")
