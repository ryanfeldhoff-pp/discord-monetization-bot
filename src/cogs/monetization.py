"""Monetization features cog."""

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class MonetizationCog(commands.Cog):
    """Cog for monetization features."""

    def __init__(self, bot: commands.Bot):
        """Initialize the cog.

        Args:
            bot: The bot instance.
        """
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Called when the bot is ready."""
        logger.info("Monetization cog ready")

    @discord.app_commands.command(name="balance", description="Check your balance")
    async def balance(self, interaction: discord.Interaction) -> None:
        """Get user balance.

        Args:
            interaction: The interaction object.
        """
        await interaction.response.send_message("Balance: 0 coins")


async def setup(bot: commands.Bot) -> None:
    """Set up the cog.

    Args:
        bot: The bot instance.
    """
    await bot.add_cog(MonetizationCog(bot))
