"""Input validation helpers."""

from typing import Optional


def is_valid_amount(amount: int) -> bool:
    """Validate transaction amount.

    Args:
        amount: The amount to validate.

    Returns:
        True if valid, False otherwise.
    """
    return amount > 0 and amount < 1000000


def is_valid_username(username: str) -> bool:
    """Validate username.

    Args:
        username: The username to validate.

    Returns:
        True if valid, False otherwise.
    """
    return 1 <= len(username) <= 32
