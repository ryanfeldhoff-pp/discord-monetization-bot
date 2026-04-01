"""Balance commands."""

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class BalanceCommands(commands.Cog):
    """Balance-related commands."""

    def __init__(self, bot: commands.Bot):
        """Initialize.

        Args:
            bot: The bot instance.
        """
        self.bot = bot

    @discord.app_commands.command(name="balance", description="Check your balance")
    async def balance(self, interaction: discord.Interaction) -> None:
        """Get user balance.

        Args:
            interaction: The interaction object.
        """
        await interaction.response.send_message("Your balance: 0 coins")

    @discord.app_commands.command(name="balance-top", description="View top balances")
    async def balance_top(self, interaction: discord.Interaction) -> None:
        """Get top users by balance.

        Args:
            interaction: The interaction object.
        """
        await interaction.response.send_message("Top balances: None yet")


async def setup(bot: commands.Bot) -> None:
    """Set up the cog.

    Args:
        bot: The bot instance.
    """
    await bot.add_cog(BalanceCommands(bot))
