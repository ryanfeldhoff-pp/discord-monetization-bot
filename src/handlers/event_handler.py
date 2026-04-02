"""Event handler utilities."""

import logging
from typing import Callable

from discord.ext import commands

logger = logging.getLogger(__name__)


class EventHandler:
    """Handles event routing and execution."""

    def __init__(self, bot: commands.Bot):
        """Initialize.

        Args:
            bot: Bot instance.
        """
        self.bot = bot
        self.handlers: dict = {}

    def on_event(
        self,
        event_name: str
    ) -> Callable:
        """Register an event handler.

        Args:
            event_name: The event name.

        Returns:
            Decorator function.
        """
        def decorator(func: Callable) -> Callable:
            if event_name not in self.handlers:
                self.handlers[event_name] = []
            self.handlers[event_name].append(func)
            logger.info(f"Registered event handler: {event_name}")
            return func
        return decorator

    async def emit_event(
        self,
        event_name: str,
        *args,
        **kwargs
    ) -> None:
        """Emit an event.

        Args:
            event_name: The event name.
            *args: Arguments.
            **kwargs: Keyword arguments.
        """
        handlers = self.handlers.get(event_name, [])
        for handler in handlers:
            try:
                await handler(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")
