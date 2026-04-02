"""Tests for helper functions."""

from src.helpers.formatters import format_balance, format_user_list
from src.helpers.validators import is_valid_amount, is_valid_username


def test_format_balance():
    """Test balance formatting."""
    assert format_balance(1000) == "1,000 coins"
    assert format_balance(100) == "100 coins"


def test_format_user_list():
    """Test user list formatting."""
    assert format_user_list([]) == "No users"
    assert "Alice" in format_user_list(["Alice", "Bob"])


def test_is_valid_amount():
    """Test amount validation."""
    assert is_valid_amount(100) is True
    assert is_valid_amount(0) is False
    assert is_valid_amount(-100) is False


def test_is_valid_username():
    """Test username validation."""
    assert is_valid_username("alice") is True
    assert is_valid_username("") is False
    assert is_valid_username("a" * 33) is False
