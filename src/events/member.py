"""Member event handlers."""

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class MemberEvents(commands.Cog):
    """Member event handlers."""

    def __init__(self, bot: commands.Bot):
        """Initialize.

        Args:
            bot: Bot instance.
        """
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Handle member join.

        Args:
            member: The member.
        """
        logger.info(f"{member} joined {member.guild}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        """Handle member remove.

        Args:
            member: The member.
        """
        logger.info(f"{member} left {member.guild}")


async def setup(bot: commands.Bot) -> None:
    """Setup the cog.

    Args:
        bot: Bot instance.
    """
    await bot.add_cog(MemberEvents(bot))
