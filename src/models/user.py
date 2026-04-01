"""User model."""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class User:
    """User data model."""

    user_id: int
    balance: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add_balance(self, amount: int) -> None:
        """Add to user balance.

        Args:
            amount: Amount to add.
        """
        self.balance += amount
        self.updated_at = datetime.now()

    def subtract_balance(self, amount: int) -> bool:
        """Subtract from user balance.

        Args:
            amount: Amount to subtract.

        Returns:
            True if successful, False if insufficient balance.
        """
        if self.balance >= amount:
            self.balance -= amount
            self.updated_at = datetime.now()
            return True
        return False
