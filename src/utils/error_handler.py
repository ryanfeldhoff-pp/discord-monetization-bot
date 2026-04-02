"""
Custom error types and global error handling.

Defines custom exception classes for different error scenarios
and provides utilities for consistent error handling across the bot.
"""

import logging
from typing import Optional
import discord
from discord.ext import commands

from src.utils.embeds import error_embed

logger = logging.getLogger(__name__)


class BotError(Exception):
    """
    Base exception class for bot errors.

    Attributes:
        error_code: Machine-readable error code for logs
        user_message: Message to display to the user
        recovery_hint: Optional hint on how to recover
    """

    def __init__(
        self,
        user_message: str,
        error_code: str = "GENERIC_ERROR",
        recovery_hint: Optional[str] = None,
    ):
        """
        Initialize BotError.

        Args:
            user_message: Message to show the user
            error_code: Error code for logging
            recovery_hint: Optional recovery suggestion
        """
        self.user_message = user_message
        self.error_code = error_code
        self.recovery_hint = recovery_hint
        super().__init__(self.user_message)


class ValidationError(BotError):
    """
    Raised when user input validation fails.

    Typical usage: Invalid command arguments, malformed data.
    """

    def __init__(
        self,
        user_message: str,
        recovery_hint: Optional[str] = None,
    ):
        """
        Initialize ValidationError.

        Args:
            user_message: What was wrong with the input
            recovery_hint: How to fix it (e.g., "Use /help xp for details")
        """
        super().__init__(
            user_message=user_message,
            error_code="VALIDATION_ERROR",
            recovery_hint=recovery_hint,
        )


class TransientError(BotError):
    """
    Raised for transient errors that may succeed on retry.

    Typical usage: Rate limits, temporary service unavailability,
    network timeouts.
    """

    def __init__(
        self,
        user_message: str,
        recovery_hint: Optional[str] = None,
    ):
        """
        Initialize TransientError.

        Args:
            user_message: What went wrong
            recovery_hint: Usually "Please try again"
        """
        super().__init__(
            user_message=user_message,
            error_code="TRANSIENT_ERROR",
            recovery_hint=recovery_hint or "Please try again in a moment",
        )


class ServiceError(BotError):
    """
    Raised for backend service failures.

    Typical usage: Database errors, API failures, permission denied.
    """

    def __init__(
        self,
        user_message: str,
        recovery_hint: Optional[str] = None,
    ):
        """
        Initialize ServiceError.

        Args:
            user_message: What service failed
            recovery_hint: What the user can do
        """
        super().__init__(
            user_message=user_message,
            error_code="SERVICE_ERROR",
            recovery_hint=recovery_hint or "Please contact support",
        )


async def handle_error(
    ctx: discord.ApplicationContext,
    error: Exception,
) -> None:
    """
    Handle and respond to an error.

    Sends an appropriate error embed based on error type.
    Logs the error for debugging.

    Args:
        ctx: Discord application context
        error: Exception that occurred
    """
    if isinstance(error, BotError):
        # Custom bot error - user-friendly message
        logger.warning(
            f"BotError ({error.error_code}) for user {ctx.author.id}: "
            f"{error.user_message}"
        )

        embed = error_embed(
            title=error.error_code.replace("_", " ").title(),
            description=error.user_message,
            recovery_hint=error.recovery_hint,
            error_code=error.error_code,
        )

        await ctx.respond(embed=embed, ephemeral=True)

    elif isinstance(error, commands.MissingRequiredArgument):
        # Missing argument
        logger.warning(
            f"Missing argument for user {ctx.author.id}: "
            f"{error.param.name}"
        )

        embed = error_embed(
            title="Missing Argument",
            description=f"The `{error.param.name}` argument is required",
            recovery_hint="Check the command help for required arguments",
            error_code="MISSING_ARG",
        )

        await ctx.respond(embed=embed, ephemeral=True)

    elif isinstance(error, commands.BadArgument):
        # Bad argument format
        logger.warning(
            f"Bad argument for user {ctx.author.id}: {error}"
        )

        embed = error_embed(
            title="Invalid Argument",
            description=str(error),
            recovery_hint="Check the command help for correct format",
            error_code="BAD_ARG",
        )

        await ctx.respond(embed=embed, ephemeral=True)

    else:
        # Unexpected error
        logger.error(
            f"Unexpected error for user {ctx.author.id}",
            exc_info=error,
        )

        embed = error_embed(
            title="Something Went Wrong",
            description="An unexpected error occurred",
            recovery_hint="The team has been notified. Please try again later",
            error_code="INTERNAL_ERROR",
        )

        await ctx.respond(embed=embed, ephemeral=True)


def setup_error_handler(bot: commands.Bot) -> None:
    """
    Register global error handler on bot.

    This should be called during bot setup to enable global error handling.

    Args:
        bot: Discord bot instance
    """

    @bot.event
    async def on_application_command_error(
        ctx: discord.ApplicationContext,
        error: Exception,
    ) -> None:
        """Global error handler for slash commands."""
        await handle_error(ctx, error)

    logger.info("Global error handler registered")
