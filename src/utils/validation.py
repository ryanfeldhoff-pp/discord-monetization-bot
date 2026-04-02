"""
Input validation helpers for command arguments and form inputs.

Provides functions for validating and parsing user input with
consistent error messages.
"""

from datetime import datetime, timedelta
from typing import Tuple, Optional, Union


def validate_positive_int(
    value: str,
    field_name: str,
) -> Tuple[Optional[int], Optional[str]]:
    """
    Validate and parse a positive integer.

    Args:
        value: String value to parse
        field_name: Name of field (for error messages)

    Returns:
        Tuple of (parsed_int, error_message). One will be None.
    """
    try:
        parsed = int(value)
        if parsed <= 0:
            return None, f"{field_name} must be positive"
        return parsed, None
    except ValueError:
        return None, f"{field_name} must be a whole number"


def validate_range(
    value: Union[int, float],
    min_val: Union[int, float],
    max_val: Union[int, float],
    field_name: str,
) -> Tuple[bool, Optional[str]]:
    """
    Validate that a numeric value is within a range.

    Args:
        value: Value to check
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        field_name: Name of field (for error messages)

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    if value < min_val or value > max_val:
        return False, f"{field_name} must be between {min_val} and {max_val}"
    return True, None


def validate_non_empty(
    value: str,
    field_name: str,
) -> Tuple[bool, Optional[str]]:
    """
    Validate that a string is not empty.

    Args:
        value: String to validate
        field_name: Name of field (for error messages)

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    if not value or not value.strip():
        return False, f"{field_name} cannot be empty"
    return True, None


def validate_date(
    value: str,
    field_name: str,
) -> Tuple[Optional[datetime], Optional[str]]:
    """
    Validate and parse a date string.

    Accepts formats:
    - YYYY-MM-DD (e.g., "2026-04-02")
    - "tomorrow"
    - "+7d" (7 days from now)
    - "-3d" (3 days ago)

    Args:
        value: String value to parse
        field_name: Name of field (for error messages)

    Returns:
        Tuple of (parsed_datetime, error_message). One will be None.
    """
    value = value.strip().lower()

    # Try ISO date format
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
        return parsed, None
    except ValueError:
        pass

    # Try "tomorrow"
    if value == "tomorrow":
        return datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1), None

    # Try relative format (+7d, -3d)
    if value.startswith(("+", "-")) and value.endswith("d"):
        try:
            days = int(value[:-1])
            parsed = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=days)
            return parsed, None
        except ValueError:
            pass

    return None, (
        f"{field_name} must be YYYY-MM-DD, 'tomorrow', "
        "or relative like '+7d'"
    )


def validate_datetime(
    value: str,
    field_name: str,
) -> Tuple[Optional[datetime], Optional[str]]:
    """
    Validate and parse a datetime string.

    Accepts format:
    - "YYYY-MM-DD HH:MM" (e.g., "2026-04-02 14:30")

    Args:
        value: String value to parse
        field_name: Name of field (for error messages)

    Returns:
        Tuple of (parsed_datetime, error_message). One will be None.
    """
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M")
        return parsed, None
    except ValueError:
        return None, (
            f"{field_name} must be in format 'YYYY-MM-DD HH:MM' "
            "(e.g., '2026-04-02 14:30')"
        )


def validate_length(
    value: str,
    min_length: int,
    max_length: int,
    field_name: str,
) -> Tuple[bool, Optional[str]]:
    """
    Validate string length.

    Args:
        value: String to validate
        min_length: Minimum length (inclusive)
        max_length: Maximum length (inclusive)
        field_name: Name of field (for error messages)

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    length = len(value)
    if length < min_length or length > max_length:
        return False, (
            f"{field_name} must be between {min_length} "
            f"and {max_length} characters"
        )
    return True, None
