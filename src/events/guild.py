"""Guild event handlers."""

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class GuildEvents(commands.Cog):
    """Guild event handlers."""

    def __init__(self, bot: commands.Bot):
        """Initialize.

        Args:
            bot: The bot instance.
        """
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Handle guild join.

        Args:
            guild: The guild object.
        """
        logger.info(f"Joined guild: {guild.name} (ID: {guild.id})")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Handle guild remove.

        Args:
            guild: The guild object.
        """
        logger.info(f"Removed from guild: {guild.name} (ID: {guild.id})")


async def setup(bot: commands.Bot) -> None:
    """Set up the cog.

    Args:
        bot: The bot instance.
    """
    await bot.add_cog(GuildEvents(bot))
