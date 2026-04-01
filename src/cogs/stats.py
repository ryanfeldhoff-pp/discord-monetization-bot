"""Statistics cog."""

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class StatsCog(commands.Cog):
    """Server statistics."""

    def __init__(self, bot: commands.Bot):
        """Initialize.

        Args:
            bot: Bot instance.
        """
        self.bot = bot

    @discord.app_commands.command(name="stats")
    async def stats(self, interaction: discord.Interaction) -> None:
        """View server stats.

        Args:
            interaction: The interaction.
        """
        embed = discord.Embed(title="Server Statistics")
        embed.add_field(name="Members", value=str(interaction.guild.member_count))
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Setup the cog.

    Args:
        bot: Bot instance.
    """
    await bot.add_cog(StatsCog(bot))
