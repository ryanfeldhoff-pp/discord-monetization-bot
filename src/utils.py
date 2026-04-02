"""Utility functions."""

import logging
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def log_error(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to log errors.

    Args:
        func: Function to decorate.

    Returns:
        Decorated function.
    """
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            raise
    return wrapper


def validate_guild_id(guild_id: int) -> bool:
    """Validate a Discord guild ID.

    Args:
        guild_id: The guild ID to validate.

    Returns:
        True if valid, False otherwise.
    """
    return guild_id > 0
