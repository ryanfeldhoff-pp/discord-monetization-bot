"""Economy features cog."""

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class EconomyCog(commands.Cog):
    """Economy features."""

    def __init__(self, bot: commands.Bot):
        """Initialize.

        Args:
            bot: Bot instance.
        """
        self.bot = bot

    @discord.app_commands.command(name="market")
    async def market(self, interaction: discord.Interaction) -> None:
        """View market.

        Args:
            interaction: The interaction.
        """
        await interaction.response.send_message("Market is closed")

    @discord.app_commands.command(name="inventory")
    async def inventory(self, interaction: discord.Interaction) -> None:
        """View inventory.

        Args:
            interaction: The interaction.
        """
        await interaction.response.send_message("Your inventory is empty")


async def setup(bot: commands.Bot) -> None:
    """Setup the cog.

    Args:
        bot: Bot instance.
    """
    await bot.add_cog(EconomyCog(bot))
