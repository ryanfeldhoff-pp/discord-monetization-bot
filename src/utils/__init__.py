"""Utilities package."""


def validate_guild_id(guild_id: int) -> bool:
    """Validate a Discord guild ID.

    Args:
        guild_id: The guild ID to validate.

    Returns:
        True if valid, False otherwise.
    """
    return guild_id > 0


__all__ = ["validate_guild_id"]
