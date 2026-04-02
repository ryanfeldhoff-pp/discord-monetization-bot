"""Integration tests."""

from src.models.transaction import TransactionType
from src.services.user_service import UserService
from src.services.transaction_service import TransactionService


def test_user_transaction_flow():
    """Test complete transaction flow."""
    user_service = UserService()
    tx_service = TransactionService()

    alice = user_service.create_user(1)
    bob = user_service.create_user(2)

    alice.add_balance(100)
    assert alice.balance == 100

    tx_service.create_transaction(
        from_user=alice.user_id,
        to_user=bob.user_id,
        amount=50,
        type=TransactionType.TRANSFER
    )

    assert len(tx_service.transactions) == 1
