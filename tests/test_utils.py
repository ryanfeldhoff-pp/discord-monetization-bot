"""Tests for utility functions."""

import pytest
from src.utils import validate_guild_id


def test_validate_guild_id():
    """Test guild ID validation."""
    assert validate_guild_id(123456) is True
    assert validate_guild_id(-1) is False
    assert validate_guild_id(0) is False
