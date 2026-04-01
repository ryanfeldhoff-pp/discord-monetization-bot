"""Admin commands."""

import logging
from typing import Optional

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class AdminCommands(commands.Cog):
    """Admin-only commands."""

    def __init__(self, bot: commands.Bot):
        """Initialize.

        Args:
            bot: The bot instance.
        """
        self.bot = bot

    @discord.app_commands.command(name="admin-set-balance", description="Set a user's balance")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def set_balance(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        amount: int
    ) -> None:
        """Set a user's balance.

        Args:
            interaction: The interaction object.
            user: The target user.
            amount: The new balance.
        """
        if amount < 0:
            await interaction.response.send_message("Balance cannot be negative")
            return
        await interaction.response.send_message(f"Set {user.mention}'s balance to {amount} coins")


async def setup(bot: commands.Bot) -> None:
    """Set up the cog.

    Args:
        bot: The bot instance.
    """
    await bot.add_cog(AdminCommands(bot))
