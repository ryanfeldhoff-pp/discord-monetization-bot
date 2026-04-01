"""User validators."""

from typing import Tuple


def validate_user_id(user_id: int) -> Tuple[bool, str]:
    """Validate a user ID.

    Args:
        user_id: The user ID.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if user_id <= 0:
        return False, "User ID must be positive"
    if user_id > 9223372036854775807:  # Max int64
        return False, "User ID is too large"
    return True, ""


def validate_user_exists(user_id: int, users: dict) -> Tuple[bool, str]:
    """Validate user exists.

    Args:
        user_id: The user ID.
        users: Dictionary of existing users.

    Returns:
        Tuple of (exists, error_message).
    """
    if user_id not in users:
        return False, "User does not exist"
    return True, ""
