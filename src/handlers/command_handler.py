"""Command handler utilities."""

import logging
from typing import Callable, Any

from discord.ext import commands

logger = logging.getLogger(__name__)


class CommandHandler:
    """Handles command execution and routing."""

    def __init__(self, bot: commands.Bot):
        """Initialize.

        Args:
            bot: Bot instance.
        """
        self.bot = bot
        self.commands: dict = {}

    def register_command(
        self,
        name: str,
        handler: Callable
    ) -> None:
        """Register a command handler.

        Args:
            name: Command name.
            handler: Command handler function.
        """
        self.commands[name] = handler
        logger.info(f"Registered command: {name}")

    async def handle_command(
        self,
        name: str,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """Handle a command.

        Args:
            name: Command name.
            *args: Arguments.
            **kwargs: Keyword arguments.

        Returns:
            Command result.
        """
        handler = self.commands.get(name)
        if handler:
            return await handler(*args, **kwargs)
        logger.warning(f"Unknown command: {name}")
        return None
