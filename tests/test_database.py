"""Tests for database module."""

import pytest
from src.database import DatabaseManager


@pytest.fixture
async def db():
    """Create a test database."""
    manager = DatabaseManager(":memory:")
    await manager.init()
    yield manager


@pytest.mark.asyncio
async def test_get_user_balance(db):
    """Test getting user balance."""
    balance = await db.get_user_balance(123456)
    assert balance >= 0


@pytest.mark.asyncio
async def test_update_user_balance(db):
    """Test updating user balance."""
    result = await db.update_user_balance(123456, 100)
    assert result is True
