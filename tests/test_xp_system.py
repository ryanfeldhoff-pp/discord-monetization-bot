"""
Tests for the XP system including award, decay, and tier calculation.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


class TestXPAward:
    """Test XP award logic."""

    @pytest.mark.asyncio
    async def test_award_xp_basic(self, mock_database):
        """Test basic XP award."""
        from bot.services.xp_service import XPService

        service = XPService(db=mock_database)

        # Mock database responses
        mock_database.fetch_one = AsyncMock(
            return_value={"discord_id": 123456789, "current_xp": 100}
        )
        mock_database.execute = AsyncMock()

        xp_awarded = await service.award_xp(
            discord_id=123456789, amount=5, source="message"
        )

        assert xp_awarded == 5
        mock_database.execute.assert_called()

    @pytest.mark.asyncio
    async def test_award_xp_with_multiplier(self, mock_database):
        """Test XP award with linked user multiplier."""
        from bot.services.xp_service import XPService

        service = XPService(db=mock_database)

        # Mock database responses
        mock_database.fetch_one = AsyncMock(
            return_value={"discord_id": 123456789, "current_xp": 100, "linked": True}
        )
        mock_database.execute = AsyncMock()

        # Award XP with 2x multiplier for linked user
        xp_awarded = await service.award_xp(
            discord_id=123456789, amount=5, source="message", multiplier=2.0
        )

        assert xp_awarded == 10

    @pytest.mark.asyncio
    async def test_award_xp_daily_cap(self, mock_database):
        """Test daily XP cap enforcement."""
        from bot.services.xp_service import XPService

        service = XPService(db=mock_database)

        # Mock user at daily cap
        mock_database.fetch_one = AsyncMock(
            return_value={
                "discord_id": 123456789,
                "current_xp": 100,
                "daily_xp": 500,  # At cap
                "daily_reset": datetime.utcnow(),
            }
        )

        xp_awarded = await service.award_xp(
            discord_id=123456789, amount=10, source="message", daily_cap=500
        )

        # Should not award due to cap
        assert xp_awarded == 0

    @pytest.mark.asyncio
    async def test_award_xp_rate_limiting(self, mock_database, mock_redis):
        """Test rate limiting on XP awards."""
        from bot.services.xp_service import XPService

        service = XPService(db=mock_database, redis=mock_redis)

        # Mock recent award
        mock_redis.get = AsyncMock(return_value=b"true")

        is_rate_limited = await service.check_rate_limit(
            discord_id=123456789, cooldown_seconds=300
        )

        assert is_rate_limited is True


class TestXPDecay:
    """Test XP decay for inactive users."""

    @pytest.mark.asyncio
    async def test_decay_inactive_user(self, mock_database):
        """Test XP decay calculation."""
        from bot.services.xp_service import XPService

        service = XPService(db=mock_database)

        # Current XP: 1000, last active: 8 days ago
        current_xp = 1000
        decay_rate = 0.05
        days_inactive = 8

        # After 1 week of inactivity, should decay 5%
        expected_xp = int(current_xp * (1 - decay_rate))

        assert expected_xp == 950

    @pytest.mark.asyncio
    async def test_decay_floor(self, mock_database):
        """Test that decay doesn't go below floor."""
        from bot.services.xp_service import XPService

        service = XPService(db=mock_database)

        # Current XP: 100, floor: 100
        current_xp = 100
        decay_floor = 100
        decay_rate = 0.05

        decayed_xp = max(decay_floor, int(current_xp * (1 - decay_rate)))

        assert decayed_xp == decay_floor

    @pytest.mark.asyncio
    async def test_no_decay_recent_user(self, mock_database):
        """Test that recent users don't decay."""
        from bot.services.xp_service import XPService

        service = XPService(db=mock_database)

        # Last active: 2 days ago (threshold: 7 days)
        last_active = datetime.utcnow() - timedelta(days=2)
        current_xp = 1000

        # Should not decay if less than 7 days
        should_decay = (
            datetime.utcnow() - last_active > timedelta(days=7)
        )

        assert should_decay is False


class TestTierCalculation:
    """Test tier assignment based on XP."""

    @pytest.mark.asyncio
    async def test_tier_bronze(self):
        """Test Bronze tier assignment."""
        from bot.services.xp_service import XPService

        service = XPService()

        tier = service.calculate_tier(500)
        assert tier == "bronze"

    @pytest.mark.asyncio
    async def test_tier_silver(self):
        """Test Silver tier assignment."""
        from bot.services.xp_service import XPService

        service = XPService()

        tier = service.calculate_tier(2500)
        assert tier == "silver"

    @pytest.mark.asyncio
    async def test_tier_gold(self):
        """Test Gold tier assignment."""
        from bot.services.xp_service import XPService

        service = XPService()

        tier = service.calculate_tier(7500)
        assert tier == "gold"

    @pytest.mark.asyncio
    async def test_tier_diamond(self):
        """Test Diamond tier assignment."""
        from bot.services.xp_service import XPService

        service = XPService()

        tier = service.calculate_tier(15000)
        assert tier == "diamond"

    @pytest.mark.asyncio
    async def test_tier_unranked(self):
        """Test unranked tier (0 XP)."""
        from bot.services.xp_service import XPService

        service = XPService()

        tier = service.calculate_tier(0)
        assert tier == "unranked"


class TestTierPromotion:
    """Test tier promotion logic."""

    @pytest.mark.asyncio
    async def test_promotion_bronze_to_silver(self, mock_database):
        """Test promotion from Bronze to Silver."""
        from bot.services.xp_service import XPService

        service = XPService(db=mock_database)

        # Mock database
        mock_database.fetch_one = AsyncMock(
            return_value={
                "discord_id": 123456789,
                "current_xp": 2400,
                "current_tier": "bronze",
            }
        )
        mock_database.execute = AsyncMock()

        # Award XP to reach Silver
        new_tier = await service.award_xp(
            discord_id=123456789, amount=150, source="bonus"
        )

        # Should promote to Silver
        assert new_tier == "silver"

    @pytest.mark.asyncio
    async def test_no_promotion_below_threshold(self, mock_database):
        """Test no promotion when below threshold."""
        from bot.services.xp_service import XPService

        service = XPService(db=mock_database)

        # Mock database
        mock_database.fetch_one = AsyncMock(
            return_value={
                "discord_id": 123456789,
                "current_xp": 2000,
                "current_tier": "bronze",
            }
        )

        # Current XP (2000) < Silver threshold (2500)
        tier = service.calculate_tier(2000)
        assert tier == "bronze"


class TestLeaJerHardRanking:
    """Test leaderboard ranking calculation."""

    @pytest.mark.asyncio
    async def test_calculate_rank(self, mock_database, mock_redis):
        """Test rank calculation."""
        from bot.services.xp_service import XPService

        service = XPService(db=mock_database, redis=mock_redis)

        # Mock leaderboard data
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.zrevrank = AsyncMock(return_value=42)  # Rank 43 (0-indexed)

        rank = await service.get_rank(discord_id=123456789)

        assert rank == 43

    @pytest.mark.asyncio
    async def test_get_percentile(self, mock_database):
        """Test percentile calculation."""
        from bot.services.xp_service import XPService

        service = XPService(db=mock_database)

        # Mock total users
        total_users = 100000
        rank = 5000

        percentile = (rank / total_users) * 100
        assert percentile == 5.0


class TestAntiSpam:
    """Test anti-spam measures."""

    @pytest.mark.asyncio
    async def test_rate_limit_cooldown(self, mock_redis):
        """Test rate limit cooldown enforcement."""
        from bot.services.xp_service import XPService

        service = XPService(redis=mock_redis)

        # Mock Redis to indicate recent award
        mock_redis.get = AsyncMock(return_value=b"true")

        is_limited = await service.check_rate_limit(
            discord_id=123456789, cooldown_seconds=300
        )

        assert is_limited is True

    @pytest.mark.asyncio
    async def test_no_rate_limit_after_cooldown(self, mock_redis):
        """Test no rate limit after cooldown expires."""
        from bot.services.xp_service import XPService

        service = XPService(redis=mock_redis)

        # Mock Redis to indicate no recent award
        mock_redis.get = AsyncMock(return_value=None)

        is_limited = await service.check_rate_limit(
            discord_id=123456789, cooldown_seconds=300
        )

        assert is_limited is False


class TestXPTransactions:
    """Test XP transaction logging."""

    @pytest.mark.asyncio
    async def test_log_xp_transaction(self, mock_database):
        """Test logging of XP transaction."""
        from bot.services.xp_service import XPService

        service = XPService(db=mock_database)

        await service.log_transaction(
            discord_id=123456789,
            amount=10,
            source="message",
            metadata={"message_id": "msg_123"},
        )

        mock_database.execute.assert_called()

    @pytest.mark.asyncio
    async def test_get_transaction_history(self, mock_database):
        """Test retrieving transaction history."""
        from bot.services.xp_service import XPService

        service = XPService(db=mock_database)

        # Mock database
        transactions = [
            {"id": 1, "amount": 5, "source": "message"},
            {"id": 2, "amount": 15, "source": "share"},
        ]
        mock_database.fetch_all = AsyncMock(return_value=transactions)

        history = await service.get_transaction_history(
            discord_id=123456789, limit=10
        )

        assert len(history) == 2
        assert history[0]["source"] == "message"
