"""Debug cog for development."""

import logging
import sys

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class DebugCog(commands.Cog):
    """Debug commands."""

    def __init__(self, bot: commands.Bot):
        """Initialize.

        Args:
            bot: Bot instance.
        """
        self.bot = bot

    @discord.app_commands.command(name="ping")
    async def ping(self, interaction: discord.Interaction) -> None:
        """Bot ping.

        Args:
            interaction: The interaction.
        """
        latency = self.bot.latency * 1000
        await interaction.response.send_message(f"Pong! {latency:.2f}ms")

    @discord.app_commands.command(name="reload")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def reload(self, interaction: discord.Interaction) -> None:
        """Reload extensions.

        Args:
            interaction: The interaction.
        """
        await interaction.response.send_message("Reloading...")


async def setup(bot: commands.Bot) -> None:
    """Setup the cog.

    Args:
        bot: Bot instance.
    """
    await bot.add_cog(DebugCog(bot))
