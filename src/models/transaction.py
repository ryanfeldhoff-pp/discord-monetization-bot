"""Transaction model."""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from enum import Enum


class TransactionType(Enum):
    """Transaction types."""
    TRANSFER = "transfer"
    REWARD = "reward"
    PENALTY = "penalty"


@dataclass
class Transaction:
    """Transaction data model."""

    from_user: int
    to_user: int
    amount: int
    type: TransactionType
    timestamp: datetime = field(default_factory=datetime.now)
    description: Optional[str] = None

    def __repr__(self) -> str:
        """String representation."""
        return f"Transaction({self.from_user} -> {self.to_user}: {self.amount} coins)"
