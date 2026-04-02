"""User management service."""

import logging
from typing import Optional

from src.models.user import User

logger = logging.getLogger(__name__)


class UserService:
    """Service for user operations."""

    def __init__(self):
        """Initialize."""
        self.users: dict = {}

    def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID.

        Args:
            user_id: User ID.

        Returns:
            User object or None.
        """
        return self.users.get(user_id)

    def create_user(self, user_id: int) -> User:
        """Create new user.

        Args:
            user_id: User ID.

        Returns:
            Created user.
        """
        user = User(user_id=user_id)
        self.users[user_id] = user
        return user
