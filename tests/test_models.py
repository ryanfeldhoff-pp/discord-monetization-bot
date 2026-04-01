"""Tests for models."""

import pytest
from datetime import datetime

from src.models.user import User
from src.models.transaction import Transaction, TransactionType


def test_user_creation():
    """Test user creation."""
    user = User(user_id=123)
    assert user.user_id == 123
    assert user.balance == 0


def test_user_add_balance():
    """Test adding balance to user."""
    user = User(user_id=123)
    user.add_balance(100)
    assert user.balance == 100


def test_user_subtract_balance():
    """Test subtracting balance from user."""
    user = User(user_id=123, balance=100)
    assert user.subtract_balance(50) is True
    assert user.balance == 50
    assert user.subtract_balance(100) is False
    assert user.balance == 50


def test_transaction_creation():
    """Test transaction creation."""
    tx = Transaction(
        from_user=123,
        to_user=456,
        amount=50,
        type=TransactionType.TRANSFER
    )
    assert tx.amount == 50
