"""Reaction event handlers."""

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class ReactionEvents(commands.Cog):
    """Reaction event handlers."""

    def __init__(self, bot: commands.Bot):
        """Initialize.

        Args:
            bot: Bot instance.
        """
        self.bot = bot

    @commands.Cog.listener()
    async def on_reaction_add(
        self,
        reaction: discord.Reaction,
        user: discord.User
    ) -> None:
        """Handle reaction add.

        Args:
            reaction: The reaction.
            user: The user.
        """
        if user == self.bot.user:
            return
        logger.debug(f"{user} reacted with {reaction.emoji}")


async def setup(bot: commands.Bot) -> None:
    """Setup the cog.

    Args:
        bot: Bot instance.
    """
    await bot.add_cog(ReactionEvents(bot))
