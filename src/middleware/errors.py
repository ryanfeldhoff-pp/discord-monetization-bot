"""Error handling middleware."""

import logging

import discord

logger = logging.getLogger(__name__)


class BotError(Exception):
    """Base bot error."""
    pass


class InsufficientBalance(BotError):
    """Raised when user has insufficient balance."""
    pass


class InvalidUser(BotError):
    """Raised when user is invalid."""
    pass


async def handle_error(interaction: discord.Interaction, error: Exception) -> None:
    """Handle command errors.

    Args:
        interaction: The interaction object.
        error: The error that occurred.
    """
    if isinstance(error, InsufficientBalance):
        await interaction.response.send_message("You don't have enough coins for that")
    elif isinstance(error, InvalidUser):
        await interaction.response.send_message("Invalid user specified")
    else:
        logger.error(f"Unhandled error: {error}")
        await interaction.response.send_message("An error occurred")
