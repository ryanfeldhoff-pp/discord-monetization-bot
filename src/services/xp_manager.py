"""
XP Manager Service

Core service handling all XP operations: awards, deductions, leaderboard queries,
tier calculations, and decay logic.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from collections import defaultdict

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from src.models.xp_models import (
    XPLedger,
    XPTransaction,
    RedemptionCounter,
)

logger = logging.getLogger(__name__)


class XPManager:
    """
    Service for managing user XP, tiers, and leaderboards.

    Features:
    - Award/deduct XP with audit trail
    - In-memory buffer for batch writes (flushed every 5 minutes)
    - Redis-backed leaderboard caching
    - Tier calculation and progression
    - XP decay for inactive users
    """

    # Tier thresholds
    TIER_THRESHOLDS = {
        "bronze": 0,
        "silver": 1000,
        "gold": 5000,
        "diamond": 20000,
    }

    # XP values (configurable via config file)
    XP_VALUES = {
        "message": 5,
        "entry_shared": 25,
        "entry_tailed": 10,
        "poll_participation": 15,
        "tournament_participation": 50,
        "tournament_win": 200,
        "helping_member": 30,
    }

    # Redemption limits per tier per month
    REDEMPTION_LIMITS = {
        "bronze": 1,
        "silver": 2,
        "gold": 4,
        "diamond": float("inf"),
    }

    # XP decay config
    DECAY_INACTIVE_DAYS = 30
    DECAY_RATE = 0.10  # 10% per week
    DECAY_FLOOR = 0.5  # Don't decay below 50% of peak

    def __init__(
        self,
        db_session: AsyncSession,
        redis_client: Optional[redis.Redis] = None,
        config: Optional[Dict] = None,
    ):
        """
        Initialize XP Manager.

        Args:
            db_session: AsyncSession for database operations
            redis_client: Optional Redis client for caching
            config: Optional config dict to override XP_VALUES
        """
        self.db = db_session
        self.redis = redis_client
        self.config = config or {}

        # Override XP values if provided in config
        if "xp_values" in self.config:
            self.XP_VALUES.update(self.config["xp_values"])

        # In-memory buffer for batch XP writes
        self._xp_buffer: Dict[int, int] = defaultdict(int)

    async def award_xp(
        self,
        user_id: int,
        amount: int,
        source: str,
        metadata: Optional[Dict] = None,
        ignore_daily_cap: bool = False,
    ) -> Tuple[bool, str]:
        """
        Award XP to a user.

        Args:
            user_id: Discord user ID
            amount: XP amount to award
            source: Source of XP (e.g., "message", "tournament_win")
            metadata: Optional metadata dict
            ignore_daily_cap: If True, bypass daily cap (events/shares don't count toward cap)

        Returns:
            Tuple of (success: bool, message: str)
        """
        if amount <= 0:
            logger.warning(f"Attempted to award {amount} XP to {user_id}")
            return False, "XP amount must be positive"

        try:
            # Check daily cap for messages only
            if source == "message" and not ignore_daily_cap:
                today_xp = await self._get_today_xp(user_id)
                if today_xp + amount > 500:
                    return False, "Daily XP cap (500) reached"

            # Add to in-memory buffer
            self._xp_buffer[user_id] += amount

            # Log transaction
            transaction = XPTransaction(
                discord_user_id=user_id,
                amount=amount,
                source=source,
                metadata_json=json.dumps(metadata) if metadata else None,
            )
            self.db.add(transaction)
            await self.db.flush()

            logger.info(f"Awarded {amount} XP to user {user_id} (source: {source})")
            return True, f"Awarded {amount} XP"

        except Exception as e:
            logger.error(f"Error awarding XP to user {user_id}: {e}")
            return False, "Error awarding XP"

    async def deduct_xp(
        self,
        user_id: int,
        amount: int,
        reason: str,
    ) -> Tuple[bool, str]:
        """
        Deduct XP from a user (for redemptions).

        Args:
            user_id: Discord user ID
            amount: XP amount to deduct
            reason: Reason for deduction (e.g., "redemption_discount_code")

        Returns:
            Tuple of (success: bool, message: str)
        """
        if amount <= 0:
            return False, "Deduction amount must be positive"

        try:
            # Get current XP
            xp_data = await self.get_xp(user_id)
            if xp_data["balance"] < amount:
                return False, f"Insufficient XP (have {xp_data['balance']}, need {amount})"

            # Deduct from buffer
            self._xp_buffer[user_id] -= amount

            # Log transaction
            transaction = XPTransaction(
                discord_user_id=user_id,
                amount=-amount,
                source="deduction",
                metadata_json=json.dumps({"reason": reason}),
            )
            self.db.add(transaction)
            await self.db.flush()

            logger.info(f"Deducted {amount} XP from user {user_id} ({reason})")
            return True, f"Deducted {amount} XP"

        except Exception as e:
            logger.error(f"Error deducting XP from user {user_id}: {e}")
            return False, "Error deducting XP"

    async def get_xp(self, user_id: int) -> Dict:
        """
        Get current XP balance and metadata for user.

        Args:
            user_id: Discord user ID

        Returns:
            Dict with keys: balance, lifetime, peak, tier, last_active
        """
        try:
            stmt = select(XPLedger).where(XPLedger.discord_user_id == user_id)
            result = await self.db.execute(stmt)
            ledger = result.scalar_one_or_none()

            if not ledger:
                # Create new ledger entry
                ledger = XPLedger(discord_user_id=user_id)
                self.db.add(ledger)
                await self.db.flush()

            # Include pending buffer XP
            current_balance = ledger.xp_balance + self._xp_buffer.get(user_id, 0)

            return {
                "balance": current_balance,
                "lifetime": ledger.xp_lifetime,
                "peak": ledger.xp_peak,
                "tier": ledger.current_tier,
                "last_active": ledger.last_active,
            }

        except Exception as e:
            logger.error(f"Error getting XP for user {user_id}: {e}")
            return {"balance": 0, "lifetime": 0, "peak": 0, "tier": "bronze", "last_active": None}

    async def get_tier(self, user_id: int) -> str:
        """
        Calculate current tier from XP.

        Args:
            user_id: Discord user ID

        Returns:
            Tier string ("bronze", "silver", "gold", "diamond")
        """
        xp_data = await self.get_xp(user_id)
        xp = xp_data["balance"]

        for tier in ["diamond", "gold", "silver", "bronze"]:
            if xp >= self.TIER_THRESHOLDS[tier]:
                return tier

        return "bronze"

    async def get_rank(self, user_id: int) -> Dict:
        """
        Get leaderboard rank and nearby ranks for user.

        Args:
            user_id: Discord user ID

        Returns:
            Dict with keys: rank, percentile, total_users
        """
        try:
            # Try Redis cache first
            if self.redis:
                rank_key = f"xp_rank:{user_id}"
                cached = await self.redis.get(rank_key)
                if cached:
                    return json.loads(cached)

            # Calculate from database
            user_xp = await self.get_xp(user_id)
            current_xp = user_xp["balance"]

            # Count users with higher XP
            stmt = select(func.count()).select_from(XPLedger).where(XPLedger.xp_balance > current_xp)
            result = await self.db.execute(stmt)
            rank = result.scalar() + 1

            # Get total users
            stmt = select(func.count()).select_from(XPLedger)
            result = await self.db.execute(stmt)
            total_users = result.scalar() or 1

            percentile = ((total_users - rank) / total_users * 100) if total_users > 0 else 0

            rank_data = {
                "rank": rank,
                "percentile": round(percentile, 2),
                "total_users": total_users,
            }

            # Cache in Redis for 1 hour
            if self.redis:
                await self.redis.setex(
                    f"xp_rank:{user_id}",
                    3600,
                    json.dumps(rank_data),
                )

            return rank_data

        except Exception as e:
            logger.error(f"Error getting rank for user {user_id}: {e}")
            return {"rank": 0, "percentile": 0, "total_users": 0}

    async def get_leaderboard(
        self,
        period: str = "alltime",
        limit: int = 10,
        user_id: Optional[int] = None,
    ) -> Dict:
        """
        Get leaderboard for period with optional user highlight.

        Args:
            period: "daily", "weekly", "monthly", or "alltime"
            limit: Number of top users to return
            user_id: Optional Discord user ID to include user's position

        Returns:
            Dict with keys: leaderboard (list of dicts), user_position (optional)
        """
        try:
            # Try Redis cache first
            if self.redis:
                cache_key = f"leaderboard:{period}:{limit}"
                cached = await self.redis.get(cache_key)
                if cached:
                    return json.loads(cached)

            # Calculate time filter
            time_filter = None
            if period == "daily":
                time_filter = datetime.utcnow() - timedelta(days=1)
            elif period == "weekly":
                time_filter = datetime.utcnow() - timedelta(weeks=1)
            elif period == "monthly":
                time_filter = datetime.utcnow() - timedelta(days=30)

            # Query leaderboard
            if time_filter:
                stmt = (
                    select(
                        XPTransaction.discord_user_id,
                        func.sum(XPTransaction.amount).label("period_xp"),
                    )
                    .where(XPTransaction.timestamp >= time_filter)
                    .group_by(XPTransaction.discord_user_id)
                    .order_by(func.sum(XPTransaction.amount).desc())
                    .limit(limit)
                )
            else:
                stmt = (
                    select(
                        XPLedger.discord_user_id,
                        XPLedger.xp_balance.label("period_xp"),
                    )
                    .order_by(XPLedger.xp_balance.desc())
                    .limit(limit)
                )

            result = await self.db.execute(stmt)
            rows = result.fetchall()

            leaderboard = [
                {
                    "rank": i + 1,
                    "user_id": row.discord_user_id,
                    "xp": row.period_xp,
                }
                for i, row in enumerate(rows)
            ]

            response = {"leaderboard": leaderboard}

            # Get user position if requested
            if user_id:
                user_rank = await self.get_rank(user_id)
                response["user_position"] = {
                    "rank": user_rank["rank"],
                    "percentile": user_rank["percentile"],
                }

            # Cache in Redis for 30 minutes
            if self.redis:
                await self.redis.setex(
                    f"leaderboard:{period}:{limit}",
                    1800,
                    json.dumps(response),
                )

            return response

        except Exception as e:
            logger.error(f"Error getting leaderboard (period={period}): {e}")
            return {"leaderboard": [], "user_position": None}

    async def flush_xp_buffer(self) -> int:
        """
        Flush in-memory XP buffer to database.

        This should be called every 5 minutes by a background task.

        Returns:
            Number of users updated
        """
        if not self._xp_buffer:
            return 0

        try:
            updated_count = 0

            for user_id, xp_delta in self._xp_buffer.items():
                if xp_delta == 0:
                    continue

                stmt = select(XPLedger).where(XPLedger.discord_user_id == user_id)
                result = await self.db.execute(stmt)
                ledger = result.scalar_one_or_none()

                if not ledger:
                    ledger = XPLedger(discord_user_id=user_id)
                    self.db.add(ledger)

                ledger.xp_balance = max(0, ledger.xp_balance + xp_delta)
                ledger.xp_lifetime = max(0, ledger.xp_lifetime + xp_delta)
                ledger.xp_peak = max(ledger.xp_peak, ledger.xp_balance)
                ledger.last_active = datetime.utcnow()
                ledger.current_tier = await self.get_tier(user_id)
                ledger.updated_at = datetime.utcnow()

                updated_count += 1

            await self.db.commit()
            self._xp_buffer.clear()

            # Invalidate leaderboard cache
            if self.redis:
                await self.redis.delete("leaderboard:*")

            logger.info(f"Flushed XP for {updated_count} users")
            return updated_count

        except Exception as e:
            logger.error(f"Error flushing XP buffer: {e}")
            await self.db.rollback()
            return 0

    async def process_decay(self) -> int:
        """
        Process XP decay for inactive users (daily task).

        Decays XP by 10% per week after 30 days of inactivity,
        with floor at 50% of peak XP.

        Returns:
            Number of users affected
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.DECAY_INACTIVE_DAYS)

            stmt = select(XPLedger).where(XPLedger.last_active < cutoff_date)
            result = await self.db.execute(stmt)
            inactive_users = result.scalars().all()

            updated_count = 0

            for ledger in inactive_users:
                weeks_inactive = (datetime.utcnow() - ledger.last_active).days / 7
                decay_multiplier = (1 - self.DECAY_RATE) ** weeks_inactive
                floor_xp = int(ledger.xp_peak * self.DECAY_FLOOR)

                new_balance = max(floor_xp, int(ledger.xp_balance * decay_multiplier))
                if new_balance < ledger.xp_balance:
                    decay_amount = ledger.xp_balance - new_balance

                    ledger.xp_balance = new_balance
                    ledger.current_tier = await self.get_tier(ledger.discord_user_id)
                    ledger.updated_at = datetime.utcnow()

                    # Log decay transaction
                    transaction = XPTransaction(
                        discord_user_id=ledger.discord_user_id,
                        amount=-decay_amount,
                        source="decay",
                        metadata_json=json.dumps({
                            "weeks_inactive": round(weeks_inactive, 2),
                            "multiplier": round(decay_multiplier, 3),
                        }),
                    )
                    self.db.add(transaction)

                    updated_count += 1

            await self.db.commit()
            logger.info(f"Processed decay for {updated_count} users")
            return updated_count

        except Exception as e:
            logger.error(f"Error processing XP decay: {e}")
            await self.db.rollback()
            return 0

    async def can_redeem(self, user_id: int, tier: str) -> Tuple[bool, str]:
        """
        Check if user can redeem based on monthly limit.

        Args:
            user_id: Discord user ID
            tier: User's tier ("bronze", "silver", "gold", "diamond")

        Returns:
            Tuple of (can_redeem: bool, message: str)
        """
        try:
            if self.REDEMPTION_LIMITS[tier] == float("inf"):
                return True, "No limit"

            now = datetime.utcnow()
            stmt = select(RedemptionCounter).where(
                and_(
                    RedemptionCounter.discord_user_id == user_id,
                    RedemptionCounter.month == now.month,
                    RedemptionCounter.year == now.year,
                )
            )
            result = await self.db.execute(stmt)
            counter = result.scalar_one_or_none()

            current_count = counter.count if counter else 0
            limit = self.REDEMPTION_LIMITS[tier]

            if current_count >= limit:
                return False, f"Monthly limit ({limit}) reached"

            return True, f"{limit - current_count} redemptions remaining"

        except Exception as e:
            logger.error(f"Error checking redemption limit for user {user_id}: {e}")
            return False, "Error checking limit"

    async def _get_today_xp(self, user_id: int) -> int:
        """
        Get XP awarded today (for daily cap).

        Args:
            user_id: Discord user ID

        Returns:
            XP awarded today
        """
        try:
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

            stmt = (
                select(func.sum(XPTransaction.amount))
                .where(
                    and_(
                        XPTransaction.discord_user_id == user_id,
                        XPTransaction.timestamp >= today_start,
                        XPTransaction.source == "message",
                    )
                )
            )
            result = await self.db.execute(stmt)
            today_xp = result.scalar() or 0

            return max(0, today_xp)

        except Exception as e:
            logger.error(f"Error getting today's XP for user {user_id}: {e}")
            return 0
