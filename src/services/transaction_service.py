"""Transaction management service."""

import logging
from typing import List

from src.models.transaction import Transaction, TransactionType

logger = logging.getLogger(__name__)


class TransactionService:
    """Service for transaction operations."""

    def __init__(self):
        """Initialize."""
        self.transactions: List[Transaction] = []

    def create_transaction(
        self,
        from_user: int,
        to_user: int,
        amount: int,
        type: TransactionType
    ) -> Transaction:
        """Create a new transaction.

        Args:
            from_user: Sender ID.
            to_user: Recipient ID.
            amount: Amount.
            type: Transaction type.

        Returns:
            Created transaction.
        """
        tx = Transaction(
            from_user=from_user,
            to_user=to_user,
            amount=amount,
            type=type
        )
        self.transactions.append(tx)
        return tx
