"""Tests for middleware."""

import pytest
from src.middleware.auth import require_admin, require_guild


def test_require_admin_decorator():
    """Test admin requirement decorator."""
    decorator = require_admin()
    assert decorator is not None


def test_require_guild_decorator():
    """Test guild requirement decorator."""
    decorator = require_guild()
    assert decorator is not None
