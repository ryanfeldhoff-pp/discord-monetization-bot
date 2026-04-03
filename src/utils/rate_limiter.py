"""
Rate Limiting Utility.

Token bucket algorithm for per-user and per-channel rate limiting.
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RateLimitBucket:
    """Token bucket for rate limiting."""

    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.

        Args:
            capacity: Maximum number of tokens
            refill_rate: Tokens per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = datetime.utcnow()

    def consume(self, amount: int = 1) -> bool:
        """
        Try to consume tokens.

        Args:
            amount: Number of tokens to consume

        Returns:
            bool: True if tokens were available
        """
        self._refill()

        if self.tokens >= amount:
            self.tokens -= amount
            return True

        return False

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = datetime.utcnow()
        elapsed = (now - self.last_refill).total_seconds()

        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now


class RateLimiter:
    """Rate limiter with support for per-user and per-channel limits."""

    def __init__(self):
        """Initialize rate limiter."""
        self.buckets: dict[str, RateLimitBucket] = {}

    def is_allowed(
        self,
        identifier: str,
        limit: int,
        window: int,
    ) -> bool:
        """
        Check if identifier is allowed based on rate limit.

        Uses token bucket algorithm where:
        - Capacity = limit
        - Refill rate = limit / window (tokens per second)

        Args:
            identifier: User/channel identifier (e.g., "user_123", "channel_456")
            limit: Maximum number of actions allowed
            window: Time window in seconds

        Returns:
            bool: True if action is allowed
        """
        # Get or create bucket
        if identifier not in self.buckets:
            refill_rate = limit / window
            self.buckets[identifier] = RateLimitBucket(limit, refill_rate)

        bucket = self.buckets[identifier]
        return bucket.consume(1)

    def get_reset_time(
        self,
        identifier: str,
        limit: int,
        window: int,
    ) -> datetime:
        """
        Get time when rate limit will reset.

        Args:
            identifier: User/channel identifier
            limit: Rate limit threshold
            window: Time window in seconds

        Returns:
            datetime: Time when rate limit resets
        """
        if identifier not in self.buckets:
            return datetime.utcnow()

        bucket = self.buckets[identifier]

        # Calculate how long until we get the needed tokens
        tokens_needed = limit - bucket.tokens
        time_needed = tokens_needed / bucket.refill_rate

        return bucket.last_refill + timedelta(seconds=time_needed)

    def reset(self, identifier: str) -> None:
        """
        Reset rate limit for identifier.

        Args:
            identifier: User/channel identifier
        """
        if identifier in self.buckets:
            del self.buckets[identifier]
            logger.debug(f"Rate limit reset for {identifier}")

    def cleanup_expired(self, ttl: int = 3600) -> None:
        """
        Remove old buckets that haven't been used.

        Args:
            ttl: Time to live in seconds (default 1 hour)
        """
        now = datetime.utcnow()
        expired = []

        for identifier, bucket in self.buckets.items():
            age = (now - bucket.last_refill).total_seconds()
            if age > ttl:
                expired.append(identifier)

        for identifier in expired:
            del self.buckets[identifier]

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired rate limit buckets")


class UserRateLimiter:
    """Specialized rate limiter for per-user limits."""

    def __init__(self, limit: int = 5, window: int = 60):
        """
        Initialize user rate limiter.

        Args:
            limit: Max actions per window
            window: Time window in seconds
        """
        self.limit = limit
        self.window = window
        self.limiter = RateLimiter()

    def is_allowed(self, user_id: int) -> bool:
        """
        Check if user is allowed an action.

        Args:
            user_id: Discord user ID

        Returns:
            bool: True if allowed
        """
        return self.limiter.is_allowed(f"user_{user_id}", self.limit, self.window)

    def reset(self, user_id: int) -> None:
        """
        Reset user's rate limit.

        Args:
            user_id: Discord user ID
        """
        self.limiter.reset(f"user_{user_id}")


class ChannelRateLimiter:
    """Specialized rate limiter for per-channel limits."""

    def __init__(self, limit: int = 10, window: int = 60):
        """
        Initialize channel rate limiter.

        Args:
            limit: Max actions per window
            window: Time window in seconds
        """
        self.limit = limit
        self.window = window
        self.limiter = RateLimiter()

    def is_allowed(self, channel_id: int) -> bool:
        """
        Check if channel is allowed an action.

        Args:
            channel_id: Discord channel ID

        Returns:
            bool: True if allowed
        """
        return self.limiter.is_allowed(f"channel_{channel_id}", self.limit, self.window)

    def reset(self, channel_id: int) -> None:
        """
        Reset channel's rate limit.

        Args:
            channel_id: Discord channel ID
        """
        self.limiter.reset(f"channel_{channel_id}")
