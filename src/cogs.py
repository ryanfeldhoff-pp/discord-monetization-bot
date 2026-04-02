"""Cog loader for Discord bot."""

import logging
from pathlib import Path

from discord.ext import commands

logger = logging.getLogger(__name__)


async def setup_cogs(bot: commands.Bot) -> None:
    """Load all cogs from the cogs directory.

    Args:
        bot: The bot instance.
    """
    cogs_dir = Path(__file__).parent / "cogs"

    if not cogs_dir.exists():
        logger.warning(f"Cogs directory not found: {cogs_dir}")
        return

    for cog_file in cogs_dir.glob("*.py"):
        if cog_file.name.startswith("_"):
            continue

        cog_name = cog_file.stem
        try:
            await bot.load_extension(f"src.cogs.{cog_name}")
            logger.info(f"Loaded cog: {cog_name}")
        except Exception as e:
            logger.error(f"Failed to load cog {cog_name}: {e}")
