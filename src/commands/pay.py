"""Payment commands."""

import logging
from typing import Optional

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class PayCommands(commands.Cog):
    """Payment-related commands."""

    def __init__(self, bot: commands.Bot):
        """Initialize.

        Args:
            bot: The bot instance.
        """
        self.bot = bot

    @discord.app_commands.command(name="pay", description="Pay coins to a user")
    async def pay(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        amount: int,
        reason: Optional[str] = None
    ) -> None:
        """Pay coins to another user.

        Args:
            interaction: The interaction object.
            user: The recipient.
            amount: Amount to pay.
            reason: Optional reason for payment.
        """
        if amount <= 0:
            await interaction.response.send_message("Amount must be positive")
            return
        await interaction.response.send_message(f"Paid {amount} coins to {user.mention}")


async def setup(bot: commands.Bot) -> None:
    """Set up the cog.

    Args:
        bot: The bot instance.
    """
    await bot.add_cog(PayCommands(bot))
