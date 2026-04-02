"""Authentication middleware."""

import logging
from typing import Callable

import discord

logger = logging.getLogger(__name__)


def require_admin() -> Callable:
    """Decorator to require admin permissions.

    Returns:
        Decorated function.
    """
    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.administrator
    return discord.app_commands.check(predicate)


def require_guild() -> Callable:
    """Decorator to require guild context.

    Returns:
        Decorated function.
    """
    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.guild is not None
    return discord.app_commands.check(predicate)
