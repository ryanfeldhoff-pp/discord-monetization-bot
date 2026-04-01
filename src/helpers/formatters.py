"""Text formatting helpers."""

from typing import List


def format_balance(balance: int) -> str:
    """Format balance as string.

    Args:
        balance: The balance amount.

    Returns:
        Formatted balance string.
    """
    return f"{balance:,} coins"


def format_user_list(users: List[str]) -> str:
    """Format user list.

    Args:
        users: List of user names.

    Returns:
        Formatted user list.
    """
    if not users:
        return "No users"
    return ", ".join(users)
