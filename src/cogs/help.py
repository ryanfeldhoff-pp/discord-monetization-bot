"""Help command cog."""

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class HelpCog(commands.Cog):
    """Help and information commands."""

    def __init__(self, bot: commands.Bot):
        """Initialize.

        Args:
            bot: Bot instance.
        """
        self.bot = bot

    @discord.app_commands.command(name="help")
    async def help_command(self, interaction: discord.Interaction) -> None:
        """Show help information.

        Args:
            interaction: The interaction.
        """
        embed = discord.Embed(title="Bot Help")
        embed.add_field(name="Commands", value="Use / to see all commands")
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(name="about")
    async def about(self, interaction: discord.Interaction) -> None:
        """About the bot.

        Args:
            interaction: The interaction.
        """
        await interaction.response.send_message("Discord Monetization Bot v1.0.0")


async def setup(bot: commands.Bot) -> None:
    """Setup the cog.

    Args:
        bot: Bot instance.
    """
    await bot.add_cog(HelpCog(bot))
