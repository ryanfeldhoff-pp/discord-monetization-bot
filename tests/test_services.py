"""Tests for services."""

from src.services.user_service import UserService
from src.services.transaction_service import TransactionService
from src.models.transaction import TransactionType


def test_user_service_create():
    """Test user service."""
    service = UserService()
    user = service.create_user(123)
    assert user.user_id == 123
    assert service.get_user(123) == user


def test_transaction_service():
    """Test transaction service."""
    service = TransactionService()
    tx = service.create_transaction(
        from_user=123,
        to_user=456,
        amount=100,
        type=TransactionType.TRANSFER
    )
    assert tx.amount == 100
    assert len(service.transactions) == 1
