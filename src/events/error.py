"""Error event handlers."""

import logging

from discord.ext import commands

logger = logging.getLogger(__name__)


class ErrorEvents(commands.Cog):
    """Error event handlers."""

    def __init__(self, bot: commands.Bot):
        """Initialize.

        Args:
            bot: Bot instance.
        """
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError
    ) -> None:
        """Handle command errors.

        Args:
            ctx: The context.
            error: The error.
        """
        logger.error(f"Command error: {error}")
        await ctx.send("An error occurred")


async def setup(bot: commands.Bot) -> None:
    """Setup the cog.

    Args:
        bot: Bot instance.
    """
    await bot.add_cog(ErrorEvents(bot))
