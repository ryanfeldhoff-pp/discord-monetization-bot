"""Balance management service."""

import logging
from typing import Optional

from src.database import DatabaseManager

logger = logging.getLogger(__name__)


class BalanceService:
    """Service for balance operations."""

    def __init__(self, db: DatabaseManager):
        """Initialize.

        Args:
            db: Database manager instance.
        """
        self.db = db

    async def get_balance(self, user_id: int) -> int:
        """Get user balance.

        Args:
            user_id: User ID.

        Returns:
            User balance.
        """
        return await self.db.get_user_balance(user_id)

    async def transfer(self, from_id: int, to_id: int, amount: int) -> bool:
        """Transfer coins.

        Args:
            from_id: Sender ID.
            to_id: Recipient ID.
            amount: Amount to transfer.

        Returns:
            True if successful.
        """
        if amount <= 0:
            return False
        return await self.db.update_user_balance(from_id, -amount)
