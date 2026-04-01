"""Admin cog."""

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class AdminCog(commands.Cog):
    """Admin commands cog."""

    def __init__(self, bot: commands.Bot):
        """Initialize.

        Args:
            bot: Bot instance.
        """
        self.bot = bot

    @discord.app_commands.command(name="admin-status")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def admin_status(self, interaction: discord.Interaction) -> None:
        """Check admin status.

        Args:
            interaction: The interaction.
        """
        await interaction.response.send_message("Admin commands working!")


async def setup(bot: commands.Bot) -> None:
    """Setup the cog.

    Args:
        bot: Bot instance.
    """
    await bot.add_cog(AdminCog(bot))
