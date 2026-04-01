"""Message event handlers."""

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class MessageEvents(commands.Cog):
    """Message event handlers."""

    def __init__(self, bot: commands.Bot):
        """Initialize.

        Args:
            bot: The bot instance.
        """
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Handle incoming messages.

        Args:
            message: The message object.
        """
        if message.author == self.bot.user:
            return
        logger.debug(f"Message from {message.author}: {message.content}")


async def setup(bot: commands.Bot) -> None:
    """Set up the cog.

    Args:
        bot: The bot instance.
    """
    await bot.add_cog(MessageEvents(bot))
