"""
Referral Manager Service (Pillar 4)

Manages referral codes, conversion tracking, ambassador tiers,
community challenges, and fraud prevention.
"""

import hashlib
import json
import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from src.models.referral_models import (
    ReferralCode,
    ReferralConversion,
    CommunityChallenge,
    WinShare,
    WinSharePreference,
)

logger = logging.getLogger(__name__)


class ReferralManager:
    """
    Service for managing referral codes, tracking, and community challenges.

    Features:
    - Generate unique referral codes (PP-XXXXXX format)
    - Track referral conversions (signup → FTD)
    - Ambassador tier management (Rising Star → Veteran → Elite)
    - Community challenge progress tracking
    - Fraud detection (self-referral, velocity, shared IP)
    - Win sharing with referral attribution
    """

    # Ambassador tier thresholds (by FTDs)
    AMBASSADOR_TIERS = {
        "rising_star": {"min_ftds": 5, "bonus_cents": 2500},   # $25 base
        "veteran": {"min_ftds": 15, "bonus_cents": 3500},      # $35 per FTD
        "elite": {"min_ftds": 50, "bonus_cents": 5000},        # $50 per FTD
    }

    # Fraud limits
    MAX_REFERRALS_PER_HOUR = 10
    MAX_SAME_IP_REFERRALS = 3

    def __init__(
        self,
        db_session: AsyncSession,
        prizepicks_api=None,
        redis_client: Optional[redis.Redis] = None,
        config: Optional[Dict] = None,
    ):
        self.db = db_session
        self.pp_api = prizepicks_api
        self.redis = redis_client
        self.config = config or {}

    def _generate_code(self) -> str:
        """Generate a unique referral code in PP-XXXXXX format."""
        chars = string.ascii_uppercase + string.digits
        suffix = "".join(secrets.choice(chars) for _ in range(6))
        return f"PP-{suffix}"

    async def get_or_create_code(self, discord_user_id: int) -> Dict:
        """Get existing referral code or create a new one."""
        try:
            stmt = select(ReferralCode).where(ReferralCode.discord_user_id == discord_user_id)
            result = await self.db.execute(stmt)
            code_record = result.scalar_one_or_none()

            if code_record:
                return {
                    "code": code_record.code,
                    "referral_url": code_record.referral_url,
                    "total_signups": code_record.total_signups,
                    "total_ftds": code_record.total_ftds,
                    "total_earned_cents": code_record.total_earned_cents,
                    "ambassador_tier": code_record.ambassador_tier,
                }

            # Generate unique code
            for _ in range(10):  # retry loop for uniqueness
                code = self._generate_code()
                exists = await self.db.execute(
                    select(ReferralCode).where(ReferralCode.code == code)
                )
                if not exists.scalar_one_or_none():
                    break

            # Try to get referral URL from PP API
            referral_url = f"https://app.prizepicks.com/sign-up?invite_code={code}"
            if self.pp_api:
                try:
                    api_result = await self.pp_api.generate_referral_link(discord_user_id)
                    if api_result:
                        referral_url = api_result.get("referral_url", referral_url)
                except Exception:
                    pass  # Fall back to constructed URL

            new_code = ReferralCode(
                discord_user_id=discord_user_id,
                code=code,
                referral_url=referral_url,
            )
            self.db.add(new_code)
            await self.db.flush()

            logger.info(f"Created referral code {code} for user {discord_user_id}")
            return {
                "code": code,
                "referral_url": referral_url,
                "total_signups": 0,
                "total_ftds": 0,
                "total_earned_cents": 0,
                "ambassador_tier": None,
            }

        except Exception as e:
            logger.error(f"Error getting/creating referral code: {e}")
            return {}

    async def record_conversion(
        self,
        referral_code: str,
        referred_user_id: str,
        conversion_type: str,
        source: Optional[str] = None,
        ip_hash: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Record a referral conversion (signup or FTD)."""
        try:
            # Look up referral code
            stmt = select(ReferralCode).where(ReferralCode.code == referral_code)
            result = await self.db.execute(stmt)
            code_record = result.scalar_one_or_none()

            if not code_record:
                return False, "Invalid referral code"

            # Fraud checks
            fraud_check = await self._check_fraud(
                code_record.discord_user_id, referred_user_id, ip_hash
            )
            if not fraud_check[0]:
                return fraud_check

            # Determine reward based on ambassador tier
            reward_cents = 2500  # Default $25
            if code_record.ambassador_tier:
                tier_info = self.AMBASSADOR_TIERS.get(code_record.ambassador_tier)
                if tier_info:
                    reward_cents = tier_info["bonus_cents"]

            # Only pay reward on FTD, not signup
            actual_reward = reward_cents if conversion_type == "ftd" else 0

            conversion = ReferralConversion(
                referrer_discord_id=code_record.discord_user_id,
                referred_user_id=referred_user_id,
                referral_code=referral_code,
                conversion_type=conversion_type,
                reward_amount_cents=actual_reward,
                reward_status="pending" if actual_reward > 0 else "paid",
                source=source,
                ip_hash=ip_hash,
            )
            self.db.add(conversion)

            # Update referral code stats
            if conversion_type == "signup":
                code_record.total_signups += 1
            elif conversion_type == "ftd":
                code_record.total_ftds += 1
                code_record.total_earned_cents += actual_reward

            # Check for ambassador tier promotion
            await self._update_ambassador_tier(code_record)

            await self.db.flush()

            logger.info(
                f"Recorded {conversion_type} conversion for code {referral_code} "
                f"(referrer={code_record.discord_user_id})"
            )
            return True, f"Conversion recorded: {conversion_type}"

        except Exception as e:
            logger.error(f"Error recording conversion: {e}")
            return False, "Error recording conversion"

    async def _check_fraud(
        self, referrer_id: int, referred_user_id: str, ip_hash: Optional[str]
    ) -> Tuple[bool, str]:
        """Run fraud checks on a referral conversion."""
        # Self-referral check
        if str(referrer_id) == referred_user_id:
            logger.warning(f"Self-referral attempt: {referrer_id}")
            return False, "Self-referral detected"

        # Velocity check: max referrals per hour
        if self.redis:
            velocity_key = f"referral_velocity:{referrer_id}"
            current = await self.redis.incr(velocity_key)
            if current == 1:
                await self.redis.expire(velocity_key, 3600)
            if current > self.MAX_REFERRALS_PER_HOUR:
                logger.warning(f"Velocity limit exceeded for referrer {referrer_id}")
                return False, "Too many referrals in short period"

        # Shared IP check
        if ip_hash:
            stmt = select(func.count()).select_from(ReferralConversion).where(
                and_(
                    ReferralConversion.ip_hash == ip_hash,
                    ReferralConversion.converted_at >= datetime.utcnow() - timedelta(days=7),
                )
            )
            result = await self.db.execute(stmt)
            ip_count = result.scalar()
            if ip_count >= self.MAX_SAME_IP_REFERRALS:
                logger.warning(f"Shared IP limit for hash {ip_hash[:8]}...")
                return False, "Suspicious activity detected"

        return True, "OK"

    async def _update_ambassador_tier(self, code_record: ReferralCode) -> None:
        """Check and update ambassador tier based on FTD count."""
        current_tier = code_record.ambassador_tier
        new_tier = None

        for tier_name in ["elite", "veteran", "rising_star"]:
            if code_record.total_ftds >= self.AMBASSADOR_TIERS[tier_name]["min_ftds"]:
                new_tier = tier_name
                break

        if new_tier and new_tier != current_tier:
            code_record.ambassador_tier = new_tier
            logger.info(
                f"User {code_record.discord_user_id} promoted to ambassador tier: {new_tier}"
            )

    async def get_referral_stats(self, discord_user_id: int) -> Dict:
        """Get comprehensive referral stats for a user."""
        try:
            code_data = await self.get_or_create_code(discord_user_id)

            # Get recent conversions
            stmt = (
                select(ReferralConversion)
                .where(ReferralConversion.referrer_discord_id == discord_user_id)
                .order_by(ReferralConversion.converted_at.desc())
                .limit(10)
            )
            result = await self.db.execute(stmt)
            recent = result.scalars().all()

            return {
                **code_data,
                "recent_conversions": [
                    {
                        "type": c.conversion_type,
                        "source": c.source,
                        "reward_cents": c.reward_amount_cents,
                        "date": c.converted_at.isoformat(),
                    }
                    for c in recent
                ],
            }
        except Exception as e:
            logger.error(f"Error getting referral stats: {e}")
            return {}

    async def get_referral_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get top referrers by FTD count."""
        try:
            if self.redis:
                cached = await self.redis.get("referral_leaderboard")
                if cached:
                    return json.loads(cached)

            stmt = (
                select(ReferralCode)
                .where(ReferralCode.total_ftds > 0)
                .order_by(ReferralCode.total_ftds.desc())
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            codes = result.scalars().all()

            lb = [
                {
                    "rank": i + 1,
                    "user_id": c.discord_user_id,
                    "ftds": c.total_ftds,
                    "signups": c.total_signups,
                    "earned_cents": c.total_earned_cents,
                    "tier": c.ambassador_tier,
                }
                for i, c in enumerate(codes)
            ]

            if self.redis:
                await self.redis.setex("referral_leaderboard", 1800, json.dumps(lb))

            return lb
        except Exception as e:
            logger.error(f"Error getting referral leaderboard: {e}")
            return []

    # ── Community Challenges ──

    async def create_challenge(
        self,
        title: str,
        description: str,
        challenge_type: str,
        target_value: int,
        reward_description: str,
        reward_type: str,
        reward_value: int,
        starts_at: datetime,
        ends_at: datetime,
        created_by: int,
    ) -> Optional[CommunityChallenge]:
        """Create a community-wide challenge."""
        try:
            challenge = CommunityChallenge(
                title=title,
                description=description,
                challenge_type=challenge_type,
                target_value=target_value,
                reward_description=reward_description,
                reward_type=reward_type,
                reward_value=reward_value,
                starts_at=starts_at,
                ends_at=ends_at,
                created_by=created_by,
            )
            self.db.add(challenge)
            await self.db.flush()
            logger.info(f"Created community challenge: {title}")
            return challenge
        except Exception as e:
            logger.error(f"Error creating challenge: {e}")
            return None

    async def update_challenge_progress(
        self, challenge_id: int, increment: int = 1
    ) -> Optional[Dict]:
        """Update challenge progress and check for completion."""
        try:
            stmt = select(CommunityChallenge).where(CommunityChallenge.id == challenge_id)
            result = await self.db.execute(stmt)
            challenge = result.scalar_one_or_none()

            if not challenge or challenge.status != "active":
                return None

            challenge.current_value += increment

            completed = challenge.current_value >= challenge.target_value
            if completed:
                challenge.status = "completed"
                challenge.completed_at = datetime.utcnow()

            await self.db.flush()

            return {
                "id": challenge.id,
                "title": challenge.title,
                "current": challenge.current_value,
                "target": challenge.target_value,
                "progress_pct": min(100, round(challenge.current_value / challenge.target_value * 100, 1)),
                "completed": completed,
                "reward_description": challenge.reward_description,
            }
        except Exception as e:
            logger.error(f"Error updating challenge progress: {e}")
            return None

    async def get_active_challenges(self) -> List[Dict]:
        """Get all active community challenges."""
        try:
            stmt = (
                select(CommunityChallenge)
                .where(CommunityChallenge.status == "active")
                .order_by(CommunityChallenge.ends_at.asc())
            )
            result = await self.db.execute(stmt)
            challenges = result.scalars().all()

            return [
                {
                    "id": c.id,
                    "title": c.title,
                    "description": c.description,
                    "current": c.current_value,
                    "target": c.target_value,
                    "progress_pct": min(100, round(c.current_value / c.target_value * 100, 1)),
                    "reward": c.reward_description,
                    "ends_at": c.ends_at.isoformat(),
                }
                for c in challenges
            ]
        except Exception as e:
            logger.error(f"Error getting active challenges: {e}")
            return []

    # ── Win Sharing ──

    async def record_win_share(
        self,
        discord_user_id: int,
        entry_id: str,
        win_amount_cents: int,
        channel_id: int,
        message_id: Optional[int] = None,
    ) -> Optional[Dict]:
        """Record a win share to the community."""
        try:
            # Get user's referral code
            code_data = await self.get_or_create_code(discord_user_id)

            share = WinShare(
                discord_user_id=discord_user_id,
                entry_id=entry_id,
                win_amount_cents=win_amount_cents,
                channel_id=channel_id,
                message_id=message_id,
                referral_code=code_data.get("code"),
            )
            self.db.add(share)
            await self.db.flush()

            return {
                "share_id": share.id,
                "referral_code": code_data.get("code"),
                "referral_url": code_data.get("referral_url"),
            }
        except Exception as e:
            logger.error(f"Error recording win share: {e}")
            return None

    async def get_win_share_prefs(self, discord_user_id: int) -> Dict:
        """Get win share preferences for a user."""
        try:
            stmt = select(WinSharePreference).where(
                WinSharePreference.discord_user_id == discord_user_id
            )
            result = await self.db.execute(stmt)
            pref = result.scalar_one_or_none()

            if not pref:
                return {"dm_enabled": True, "auto_share": False, "min_win_amount_cents": 500}

            return {
                "dm_enabled": pref.dm_enabled,
                "auto_share": pref.auto_share,
                "min_win_amount_cents": pref.min_win_amount_cents,
            }
        except Exception as e:
            logger.error(f"Error getting win share prefs: {e}")
            return {"dm_enabled": True, "auto_share": False, "min_win_amount_cents": 500}

    async def update_win_share_prefs(
        self, discord_user_id: int, dm_enabled: Optional[bool] = None
    ) -> bool:
        """Update win share preferences."""
        try:
            stmt = select(WinSharePreference).where(
                WinSharePreference.discord_user_id == discord_user_id
            )
            result = await self.db.execute(stmt)
            pref = result.scalar_one_or_none()

            if not pref:
                pref = WinSharePreference(discord_user_id=discord_user_id)
                self.db.add(pref)

            if dm_enabled is not None:
                pref.dm_enabled = dm_enabled

            await self.db.flush()
            return True
        except Exception as e:
            logger.error(f"Error updating win share prefs: {e}")
            return False
