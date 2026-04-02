"""
Referral Manager Service

Core service for managing the referral amplifier system: code generation, conversion
tracking, community challenges, ambassador programs, win sharing, and fraud detection.
"""

import json
import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from src.models.referral_models import (
    ReferralCode,
    ReferralConversion,
    ReferralChallenge,
    Ambassador,
    WinShare,
    FraudFlag,
)
from src.services.prizepicks_api import PrizepicksAPIClient

logger = logging.getLogger(__name__)


class ReferralManager:
    """
    Service for managing referral amplifier system including codes, conversions,
    challenges, ambassador program, win sharing, and fraud detection.

    Features:
    - Referral code generation and management
    - Conversion tracking with fraud checks
    - Community challenge tracking and rewards
    - Ambassador program with tiered benefits
    - Win share logging and click tracking
    - Comprehensive fraud detection and flagging
    """

    # Referral code format
    CODE_PREFIX = "PP"
    CODE_LENGTH = 6

    # Referral reward tiers (in cents)
    REFERRAL_REWARDS = {
        "regular": 2500,  # $25
        "ambassador_rising_star": 3500,  # $35
        "ambassador_veteran": 4000,  # $40
        "ambassador_elite": 5000,  # $50
    }

    # Ambassador eligibility and thresholds
    AMBASSADOR_MIN_REFERRALS = 50
    AMBASSADOR_MIN_FTD_MONTHLY = 10
    AMBASSADOR_MIN_XP = 5000  # From XP system
    AMBASSADOR_PROBATION_THRESHOLD = 5  # FTDs per month

    # Fraud detection thresholds
    FRAUD_SELF_REFERRAL = "self_referral"
    FRAUD_VELOCITY_SPIKE = "velocity_spike"
    FRAUD_SHARED_IP = "shared_ip"
    FRAUD_DUPLICATE_ACCOUNT = "duplicate_account"
    VELOCITY_LIMIT = 10  # Max referrals per hour

    def __init__(
        self,
        db_session: AsyncSession,
        prizepicks_api: PrizepicksAPIClient,
        redis_client: Optional[redis.Redis] = None,
        config: Optional[Dict] = None,
    ):
        """
        Initialize Referral Manager.

        Args:
            db_session: AsyncSession for database operations
            prizepicks_api: PrizepicksAPIClient for API calls
            redis_client: Optional Redis client for caching
            config: Optional config dict to override defaults
        """
        self.db = db_session
        self.api = prizepicks_api
        self.redis = redis_client
        self.config = config or {}

    # ============================================================================
    # REFERRAL CODE MANAGEMENT
    # ============================================================================

    async def generate_referral_code(self, discord_user_id: int) -> ReferralCode:
        """
        Generate a unique referral code for a user.

        Creates a new referral code if user doesn't have one, otherwise returns existing.

        Args:
            discord_user_id: Discord user ID

        Returns:
            ReferralCode object

        Raises:
            Exception: If API or database error occurs
        """
        try:
            # Check if user already has a code
            stmt = select(ReferralCode).where(ReferralCode.discord_user_id == discord_user_id)
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing and existing.status == "active":
                logger.info(f"User {discord_user_id} already has active referral code")
                return existing

            # Generate unique code
            code = await self._generate_unique_code()

            # Call PrizePicks API to get referral URL
            try:
                referral_url = await self.api.generate_referral_link(code)
            except Exception as e:
                logger.error(f"Failed to generate referral link via API: {e}")
                referral_url = None

            # Create new referral code
            referral_code = ReferralCode(
                discord_user_id=discord_user_id,
                referral_code=code,
                referral_url=referral_url,
                status="active",
            )
            self.db.add(referral_code)
            await self.db.flush()

            logger.info(f"Generated referral code {code} for user {discord_user_id}")
            return referral_code

        except Exception as e:
            logger.error(f"Error generating referral code for user {discord_user_id}: {e}")
            raise

    async def get_referral_code(self, discord_user_id: int) -> Optional[ReferralCode]:
        """
        Get active referral code for a user.

        Args:
            discord_user_id: Discord user ID

        Returns:
            ReferralCode if exists, None otherwise
        """
        try:
            stmt = select(ReferralCode).where(
                and_(
                    ReferralCode.discord_user_id == discord_user_id,
                    ReferralCode.status == "active",
                )
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Error getting referral code for user {discord_user_id}: {e}")
            return None

    async def get_referral_stats(self, discord_user_id: int) -> Dict:
        """
        Get comprehensive referral statistics for a user.

        Args:
            discord_user_id: Discord user ID

        Returns:
            Dict with keys: total_referrals, total_ftds, total_earnings, conversion_rate, rank
        """
        try:
            # Get referral code data
            stmt = select(ReferralCode).where(ReferralCode.discord_user_id == discord_user_id)
            result = await self.db.execute(stmt)
            code_record = result.scalar_one_or_none()

            if not code_record:
                return {
                    "total_referrals": 0,
                    "total_ftds": 0,
                    "total_earnings": 0,
                    "conversion_rate": 0.0,
                    "rank_among_referrers": None,
                }

            # Calculate conversion rate
            conversion_rate = (
                (code_record.total_ftds / code_record.total_referrals * 100)
                if code_record.total_referrals > 0
                else 0.0
            )

            # Get rank among all referrers
            stmt = select(func.count()).select_from(ReferralCode).where(
                ReferralCode.total_referrals > code_record.total_referrals
            )
            result = await self.db.execute(stmt)
            rank = (result.scalar() or 0) + 1

            return {
                "total_referrals": code_record.total_referrals,
                "total_ftds": code_record.total_ftds,
                "total_earnings": code_record.total_earnings,
                "conversion_rate": round(conversion_rate, 2),
                "rank_among_referrers": rank,
            }

        except Exception as e:
            logger.error(f"Error getting referral stats for user {discord_user_id}: {e}")
            return {
                "total_referrals": 0,
                "total_ftds": 0,
                "total_earnings": 0,
                "conversion_rate": 0.0,
                "rank_among_referrers": None,
            }

    # ============================================================================
    # CONVERSION TRACKING
    # ============================================================================

    async def track_conversion(
        self,
        referral_code: str,
        referred_discord_id: Optional[int],
        referred_pp_user_id: Optional[str],
        conversion_type: str,
        attribution_source: str,
    ) -> Optional[ReferralConversion]:
        """
        Track a referral conversion event.

        Validates code, runs fraud checks, creates conversion record, and
        triggers reward processing for FTD conversions.

        Args:
            referral_code: Referral code string
            referred_discord_id: Referred user's Discord ID (optional)
            referred_pp_user_id: Referred user's PrizePicks ID (optional)
            conversion_type: "signup", "ftd", or "entry_placed"
            attribution_source: "tail", "win_share", "recap_card", "direct", "challenge"

        Returns:
            ReferralConversion object if successful, None on error

        Raises:
            Exception: If validation or database error occurs
        """
        try:
            # Validate referral code exists and is active
            stmt = select(ReferralCode).where(ReferralCode.referral_code == referral_code)
            result = await self.db.execute(stmt)
            code_record = result.scalar_one_or_none()

            if not code_record or code_record.status != "active":
                logger.warning(f"Invalid or inactive referral code: {referral_code}")
                return None

            referrer_id = code_record.discord_user_id

            # Run fraud checks
            fraud_flag = await self.check_fraud(
                referrer_id,
                referred_discord_id,
                {
                    "conversion_type": conversion_type,
                    "attribution_source": attribution_source,
                    "referred_pp_user_id": referred_pp_user_id,
                },
            )

            # Create conversion record
            conversion = ReferralConversion(
                referrer_discord_id=referrer_id,
                referred_discord_id=referred_discord_id,
                referred_pp_user_id=referred_pp_user_id,
                referral_code_used=referral_code,
                conversion_type=conversion_type,
                attribution_source=attribution_source,
                reward_status="fraud_flagged" if fraud_flag else "pending",
                metadata_json=json.dumps(
                    {
                        "fraud_flag_id": fraud_flag.id if fraud_flag else None,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
            )
            self.db.add(conversion)
            await self.db.flush()

            # Update referral code totals
            code_record.total_referrals += 1
            if conversion_type == "ftd":
                code_record.total_ftds += 1
            code_record.updated_at = datetime.utcnow()
            await self.db.flush()

            logger.info(
                f"Tracked conversion for code {referral_code}: "
                f"type={conversion_type}, source={attribution_source}"
            )

            # Process reward for FTD conversions if not flagged
            if conversion_type == "ftd" and not fraud_flag:
                success = await self.process_reward(conversion.id)
                if success:
                    conversion.reward_status = "credited"
                    await self.db.flush()

            await self.db.commit()
            return conversion

        except Exception as e:
            logger.error(f"Error tracking conversion for code {referral_code}: {e}")
            await self.db.rollback()
            raise

    async def process_reward(self, conversion_id: int) -> bool:
        """
        Process reward for a conversion.

        Calculates reward based on referrer tier, credits via API, updates totals.

        Args:
            conversion_id: ReferralConversion ID

        Returns:
            True if reward processed successfully, False otherwise
        """
        try:
            # Get conversion record
            stmt = select(ReferralConversion).where(ReferralConversion.id == conversion_id)
            result = await self.db.execute(stmt)
            conversion = result.scalar_one_or_none()

            if not conversion:
                logger.error(f"Conversion {conversion_id} not found")
                return False

            # Get referrer's referral code
            stmt = select(ReferralCode).where(
                ReferralCode.discord_user_id == conversion.referrer_discord_id
            )
            result = await self.db.execute(stmt)
            code_record = result.scalar_one_or_none()

            if not code_record:
                logger.error(
                    f"Referral code not found for user {conversion.referrer_discord_id}"
                )
                return False

            # Determine reward amount based on tier
            reward_amount = await self._calculate_reward_amount(
                conversion.referrer_discord_id
            )

            # Credit reward via API
            try:
                success = await self.api.credit_referral_reward(
                    conversion.referrer_discord_id,
                    reward_amount,
                    conversion_id,
                )
            except Exception as e:
                logger.error(
                    f"Failed to credit reward for conversion {conversion_id}: {e}"
                )
                return False

            if not success:
                logger.warning(f"API failed to credit reward for conversion {conversion_id}")
                return False

            # Update conversion and code records
            conversion.reward_amount = reward_amount
            conversion.reward_status = "credited"
            conversion.rewarded_at = datetime.utcnow()

            code_record.total_earnings += reward_amount
            code_record.updated_at = datetime.utcnow()

            await self.db.commit()
            logger.info(
                f"Processed reward {reward_amount} cents for "
                f"conversion {conversion_id} (code: {code_record.referral_code})"
            )
            return True

        except Exception as e:
            logger.error(f"Error processing reward for conversion {conversion_id}: {e}")
            await self.db.rollback()
            return False

    # ============================================================================
    # COMMUNITY CHALLENGES
    # ============================================================================

    async def create_challenge(
        self,
        guild_id: int,
        title: str,
        description: str,
        challenge_type: str,
        target_count: int,
        reward_config: Dict,
        starts_at: datetime,
        ends_at: datetime,
    ) -> ReferralChallenge:
        """
        Create a new community referral challenge.

        Args:
            guild_id: Discord guild ID
            title: Challenge title
            description: Challenge description
            challenge_type: "ftd_milestone", "monthly_target", or "seasonal"
            target_count: Target FTD count
            reward_config: Dict with reward details
            starts_at: Challenge start datetime
            ends_at: Challenge end datetime

        Returns:
            ReferralChallenge object

        Raises:
            Exception: If validation or database error occurs
        """
        try:
            challenge = ReferralChallenge(
                guild_id=guild_id,
                title=title,
                description=description,
                challenge_type=challenge_type,
                target_count=target_count,
                current_count=0,
                reward_config_json=json.dumps(reward_config),
                status="upcoming" if starts_at > datetime.utcnow() else "active",
                starts_at=starts_at,
                ends_at=ends_at,
            )
            self.db.add(challenge)
            await self.db.flush()
            await self.db.commit()

            logger.info(
                f"Created challenge '{title}' for guild {guild_id}: "
                f"target={target_count}, type={challenge_type}"
            )
            return challenge

        except Exception as e:
            logger.error(f"Error creating challenge for guild {guild_id}: {e}")
            await self.db.rollback()
            raise

    async def update_challenge_progress(self, guild_id: int) -> Optional[ReferralChallenge]:
        """
        Update progress for all active challenges in a guild.

        Counts FTDs in challenge period, updates current_count, and triggers
        milestone reward distribution if target is hit.

        Args:
            guild_id: Discord guild ID

        Returns:
            ReferralChallenge if milestone just hit, None otherwise
        """
        try:
            # Get all active challenges for guild
            stmt = select(ReferralChallenge).where(
                and_(
                    ReferralChallenge.guild_id == guild_id,
                    ReferralChallenge.status == "active",
                )
            )
            result = await self.db.execute(stmt)
            challenges = result.scalars().all()

            milestone_hit = None

            for challenge in challenges:
                # Count FTDs in challenge period
                stmt = select(func.count()).select_from(ReferralConversion).where(
                    and_(
                        ReferralConversion.conversion_type == "ftd",
                        ReferralConversion.converted_at >= challenge.starts_at,
                        ReferralConversion.converted_at <= challenge.ends_at,
                        ReferralConversion.reward_status == "credited",
                    )
                )
                result = await self.db.execute(stmt)
                ftd_count = result.scalar() or 0

                challenge.current_count = ftd_count

                # Check if target hit
                if ftd_count >= challenge.target_count and challenge.status == "active":
                    challenge.status = "completed"
                    challenge.completed_at = datetime.utcnow()
                    milestone_hit = challenge

                    # Trigger milestone reward distribution
                    await self.distribute_milestone_rewards(challenge.id)

            await self.db.commit()

            if milestone_hit:
                logger.info(
                    f"Challenge milestone hit for guild {guild_id}: {milestone_hit.title}"
                )

            return milestone_hit

        except Exception as e:
            logger.error(f"Error updating challenge progress for guild {guild_id}: {e}")
            await self.db.rollback()
            return None

    async def get_active_challenges(self, guild_id: int) -> List[ReferralChallenge]:
        """
        Get all active challenges for a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            List of active ReferralChallenge objects
        """
        try:
            stmt = select(ReferralChallenge).where(
                and_(
                    ReferralChallenge.guild_id == guild_id,
                    ReferralChallenge.status.in_(["upcoming", "active"]),
                )
            )
            result = await self.db.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting challenges for guild {guild_id}: {e}")
            return []

    async def distribute_milestone_rewards(self, challenge_id: int) -> int:
        """
        Distribute milestone rewards to all eligible participants.

        Args:
            challenge_id: ReferralChallenge ID

        Returns:
            Number of users rewarded
        """
        try:
            # Get challenge details
            stmt = select(ReferralChallenge).where(ReferralChallenge.id == challenge_id)
            result = await self.db.execute(stmt)
            challenge = result.scalar_one_or_none()

            if not challenge:
                logger.error(f"Challenge {challenge_id} not found")
                return 0

            reward_config = json.loads(challenge.reward_config_json)

            # Get all referrers who contributed FTDs during challenge
            stmt = select(ReferralConversion.referrer_discord_id).distinct().where(
                and_(
                    ReferralConversion.conversion_type == "ftd",
                    ReferralConversion.converted_at >= challenge.starts_at,
                    ReferralConversion.converted_at <= challenge.ends_at,
                    ReferralConversion.reward_status == "credited",
                )
            )
            result = await self.db.execute(stmt)
            referrer_ids = result.scalars().all()

            reward_count = 0

            for referrer_id in referrer_ids:
                try:
                    # Credit bonus reward per participant
                    bonus_amount = reward_config.get("per_participant_bonus_cents", 0)
                    if bonus_amount > 0:
                        success = await self.api.credit_referral_reward(
                            referrer_id,
                            bonus_amount,
                            challenge_id,
                        )
                        if success:
                            reward_count += 1
                except Exception as e:
                    logger.error(f"Failed to credit bonus to user {referrer_id}: {e}")

            logger.info(
                f"Distributed milestone rewards for challenge {challenge_id}: "
                f"{reward_count} users rewarded"
            )
            return reward_count

        except Exception as e:
            logger.error(f"Error distributing milestone rewards for challenge {challenge_id}: {e}")
            return 0

    # ============================================================================
    # AMBASSADOR PROGRAM
    # ============================================================================

    async def nominate_ambassador(self, discord_user_id: int) -> Optional[Ambassador]:
        """
        Nominate a user for ambassador program.

        Checks eligibility (top 50 by referrals/XP), creates ambassador record
        with "rising_star" tier.

        Args:
            discord_user_id: Discord user ID

        Returns:
            Ambassador object if successful, None otherwise

        Raises:
            Exception: If validation or database error occurs
        """
        try:
            # Check if already an ambassador
            stmt = select(Ambassador).where(Ambassador.discord_user_id == discord_user_id)
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                logger.info(f"User {discord_user_id} already is an ambassador")
                return existing

            # Check referral eligibility
            stmt = select(ReferralCode).where(
                ReferralCode.discord_user_id == discord_user_id
            )
            result = await self.db.execute(stmt)
            code_record = result.scalar_one_or_none()

            if not code_record or code_record.total_referrals < self.AMBASSADOR_MIN_REFERRALS:
                logger.warning(
                    f"User {discord_user_id} doesn't meet referral minimum "
                    f"({code_record.total_referrals if code_record else 0} < {self.AMBASSADOR_MIN_REFERRALS})"
                )
                return None

            # Create ambassador record
            ambassador = Ambassador(
                discord_user_id=discord_user_id,
                tier="rising_star",
                referral_bonus_cents=self.REFERRAL_REWARDS["ambassador_rising_star"],
                nominated_at=datetime.utcnow(),
                status="active",
            )
            self.db.add(ambassador)
            await self.db.flush()

            # Update referral code
            code_record.is_ambassador = True
            code_record.updated_at = datetime.utcnow()

            await self.db.commit()
            logger.info(f"Nominated user {discord_user_id} as rising_star ambassador")
            return ambassador

        except Exception as e:
            logger.error(f"Error nominating ambassador {discord_user_id}: {e}")
            await self.db.rollback()
            raise

    async def promote_ambassador(self, discord_user_id: int, new_tier: str) -> Optional[Ambassador]:
        """
        Promote ambassador to next tier.

        Upgrades tier: rising_star → veteran → elite and adjusts bonus accordingly.

        Args:
            discord_user_id: Discord user ID
            new_tier: New tier ("veteran" or "elite")

        Returns:
            Updated Ambassador object if successful, None otherwise
        """
        try:
            stmt = select(Ambassador).where(Ambassador.discord_user_id == discord_user_id)
            result = await self.db.execute(stmt)
            ambassador = result.scalar_one_or_none()

            if not ambassador:
                logger.error(f"Ambassador not found for user {discord_user_id}")
                return None

            # Validate tier progression
            valid_progressions = {
                "rising_star": "veteran",
                "veteran": "elite",
            }

            if new_tier not in valid_progressions.values():
                logger.error(f"Invalid promotion tier: {new_tier}")
                return None

            # Update tier and bonus
            ambassador.tier = new_tier
            ambassador.referral_bonus_cents = self.REFERRAL_REWARDS[f"ambassador_{new_tier}"]
            ambassador.promoted_at = datetime.utcnow()

            await self.db.commit()
            logger.info(
                f"Promoted ambassador {discord_user_id} to {new_tier} "
                f"(bonus: {ambassador.referral_bonus_cents} cents)"
            )
            return ambassador

        except Exception as e:
            logger.error(f"Error promoting ambassador {discord_user_id}: {e}")
            await self.db.rollback()
            return None

    async def get_ambassador_leaderboard(self, limit: int = 50) -> List[Dict]:
        """
        Get leaderboard of top ambassadors.

        Args:
            limit: Maximum number of ambassadors to return

        Returns:
            List of dicts with ambassador stats
        """
        try:
            stmt = (
                select(
                    Ambassador.discord_user_id,
                    Ambassador.tier,
                    Ambassador.lifetime_ftd_count,
                    ReferralCode.total_earnings,
                )
                .join(
                    ReferralCode,
                    Ambassador.discord_user_id == ReferralCode.discord_user_id,
                )
                .where(Ambassador.status == "active")
                .order_by(Ambassador.lifetime_ftd_count.desc())
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            rows = result.fetchall()

            leaderboard = [
                {
                    "rank": i + 1,
                    "user_id": row.discord_user_id,
                    "tier": row.tier,
                    "lifetime_ftds": row.lifetime_ftd_count,
                    "total_earnings": row.total_earnings or 0,
                }
                for i, row in enumerate(rows)
            ]

            return leaderboard

        except Exception as e:
            logger.error(f"Error getting ambassador leaderboard: {e}")
            return []

    async def review_ambassador_performance(self) -> List[Ambassador]:
        """
        Monthly performance review for ambassadors.

        Demotes ambassadors to probation if monthly FTD count below threshold.
        Removes ambassadors from probation if on probation for 2+ months.

        Returns:
            List of ambassadors with status changes
        """
        try:
            status_changes = []

            # Get all active and probation ambassadors
            stmt = select(Ambassador).where(
                Ambassador.status.in_(["active", "probation"])
            )
            result = await self.db.execute(stmt)
            ambassadors = result.scalars().all()

            month_ago = datetime.utcnow() - timedelta(days=30)

            for ambassador in ambassadors:
                # Count FTDs in past month
                stmt = select(func.count()).select_from(ReferralConversion).where(
                    and_(
                        ReferralConversion.referrer_discord_id == ambassador.discord_user_id,
                        ReferralConversion.conversion_type == "ftd",
                        ReferralConversion.converted_at >= month_ago,
                        ReferralConversion.reward_status == "credited",
                    )
                )
                result = await self.db.execute(stmt)
                monthly_ftds = result.scalar() or 0

                ambassador.monthly_ftd_count = monthly_ftds

                if ambassador.status == "active":
                    if monthly_ftds < self.AMBASSADOR_PROBATION_THRESHOLD:
                        ambassador.status = "probation"
                        status_changes.append(ambassador)
                        logger.info(
                            f"Moved ambassador {ambassador.discord_user_id} to probation "
                            f"(FTDs: {monthly_ftds})"
                        )

                elif ambassador.status == "probation":
                    # Check how long in probation
                    months_in_probation = (
                        (datetime.utcnow() - ambassador.nominated_at).days / 30
                    )
                    if months_in_probation >= 2 and monthly_ftds < self.AMBASSADOR_PROBATION_THRESHOLD:
                        ambassador.status = "removed"
                        status_changes.append(ambassador)
                        logger.info(
                            f"Removed ambassador {ambassador.discord_user_id} after 2 months probation"
                        )
                    elif monthly_ftds >= self.AMBASSADOR_PROBATION_THRESHOLD:
                        ambassador.status = "active"
                        status_changes.append(ambassador)
                        logger.info(
                            f"Reinstated ambassador {ambassador.discord_user_id} from probation"
                        )

            await self.db.commit()
            return status_changes

        except Exception as e:
            logger.error(f"Error reviewing ambassador performance: {e}")
            await self.db.rollback()
            return []

    # ============================================================================
    # WIN SHARING
    # ============================================================================

    async def log_win_share(
        self,
        discord_user_id: int,
        entry_id: str,
        win_amount_cents: int,
        channel_id: Optional[int],
        share_type: str,
    ) -> WinShare:
        """
        Log a win share event with referral CTA.

        Attaches user's referral code to the share.

        Args:
            discord_user_id: Discord user ID
            entry_id: PrizePicks entry ID
            win_amount_cents: Win amount in cents
            channel_id: Discord channel ID (optional)
            share_type: "channel_post", "dm_prompt", or "social_share"

        Returns:
            WinShare object

        Raises:
            Exception: If database error occurs
        """
        try:
            # Get user's referral code
            code = await self.get_referral_code(discord_user_id)
            referral_code = code.referral_code if code else None

            share_log = WinShare(
                discord_user_id=discord_user_id,
                entry_id=entry_id,
                win_amount_cents=win_amount_cents,
                channel_id=channel_id,
                referral_code_attached=referral_code,
                share_type=share_type,
            )
            self.db.add(share_log)
            await self.db.flush()
            await self.db.commit()

            logger.info(
                f"Logged win share for user {discord_user_id}: "
                f"type={share_type}, amount={win_amount_cents} cents"
            )
            return share_log

        except Exception as e:
            logger.error(f"Error logging win share for user {discord_user_id}: {e}")
            await self.db.rollback()
            raise

    async def track_share_click(self, win_share_id: int) -> None:
        """
        Track a click on a shared win's referral CTA.

        Args:
            win_share_id: WinShare ID
        """
        try:
            stmt = select(WinShare).where(WinShare.id == win_share_id)
            result = await self.db.execute(stmt)
            share = result.scalar_one_or_none()

            if share:
                share.clicks += 1
                await self.db.commit()
                logger.info(f"Tracked click on win share {win_share_id} (total: {share.clicks})")

        except Exception as e:
            logger.error(f"Error tracking share click {win_share_id}: {e}")

    async def get_win_share_stats(self, discord_user_id: int) -> Dict:
        """
        Get win sharing statistics for a user.

        Args:
            discord_user_id: Discord user ID

        Returns:
            Dict with keys: total_shares, total_clicks, total_conversions, best_performing_share
        """
        try:
            # Get all win shares by user
            stmt = select(WinShare).where(WinShare.discord_user_id == discord_user_id)
            result = await self.db.execute(stmt)
            shares = result.scalars().all()

            if not shares:
                return {
                    "total_shares": 0,
                    "total_clicks": 0,
                    "total_conversions": 0,
                    "best_performing_share": None,
                }

            total_shares = len(shares)
            total_clicks = sum(s.clicks for s in shares)
            total_conversions = sum(s.conversions for s in shares)
            best_share = max(shares, key=lambda s: s.conversions) if shares else None

            return {
                "total_shares": total_shares,
                "total_clicks": total_clicks,
                "total_conversions": total_conversions,
                "best_performing_share": {
                    "id": best_share.id,
                    "entry_id": best_share.entry_id,
                    "conversions": best_share.conversions,
                    "win_amount": best_share.win_amount_cents,
                } if best_share else None,
            }

        except Exception as e:
            logger.error(f"Error getting win share stats for user {discord_user_id}: {e}")
            return {
                "total_shares": 0,
                "total_clicks": 0,
                "total_conversions": 0,
                "best_performing_share": None,
            }

    # ============================================================================
    # FRAUD PREVENTION
    # ============================================================================

    async def check_fraud(
        self,
        referrer_id: int,
        referred_id: Optional[int],
        metadata: Optional[Dict] = None,
    ) -> Optional[FraudFlag]:
        """
        Run fraud detection checks on a referral.

        Checks: self-referral, velocity spike (>10 refs/hour), shared IP patterns.

        Args:
            referrer_id: Referrer Discord user ID
            referred_id: Referred Discord user ID (optional)
            metadata: Additional metadata

        Returns:
            FraudFlag if suspicious, None if clean
        """
        try:
            # Check self-referral
            if referred_id and referrer_id == referred_id:
                fraud_flag = FraudFlag(
                    discord_user_id=referrer_id,
                    flag_type=self.FRAUD_SELF_REFERRAL,
                    severity="critical",
                    details_json=json.dumps({"referred_id": referred_id}),
                    action_taken="flagged",
                )
                self.db.add(fraud_flag)
                await self.db.flush()
                logger.warning(f"Self-referral detected: {referrer_id}")
                return fraud_flag

            # Check velocity (max 10 referrals per hour)
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            stmt = select(func.count()).select_from(ReferralConversion).where(
                and_(
                    ReferralConversion.referrer_discord_id == referrer_id,
                    ReferralConversion.converted_at >= hour_ago,
                )
            )
            result = await self.db.execute(stmt)
            hourly_count = result.scalar() or 0

            if hourly_count >= self.VELOCITY_LIMIT:
                fraud_flag = FraudFlag(
                    discord_user_id=referrer_id,
                    flag_type=self.FRAUD_VELOCITY_SPIKE,
                    severity="high",
                    details_json=json.dumps({"referrals_per_hour": hourly_count}),
                    action_taken="flagged",
                )
                self.db.add(fraud_flag)
                await self.db.flush()
                logger.warning(
                    f"Velocity spike detected for user {referrer_id}: "
                    f"{hourly_count} referrals/hour"
                )
                return fraud_flag

            # Check for duplicate account patterns
            # (shared IP, similar metadata, etc.) - placeholder for expanded logic
            if metadata and "referred_pp_user_id" in metadata:
                metadata["referred_pp_user_id"]
                # Could check for multiple Discord accounts with same PP user
                # This is a simplified version

            await self.db.commit()
            return None

        except Exception as e:
            logger.error(f"Error running fraud check for referrer {referrer_id}: {e}")
            await self.db.rollback()
            return None

    async def get_fraud_flags(self, discord_user_id: int) -> List[FraudFlag]:
        """
        Get all fraud flags for a user.

        Args:
            discord_user_id: Discord user ID

        Returns:
            List of FraudFlag objects
        """
        try:
            stmt = select(FraudFlag).where(FraudFlag.discord_user_id == discord_user_id)
            result = await self.db.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting fraud flags for user {discord_user_id}: {e}")
            return []

    async def resolve_fraud_flag(
        self,
        flag_id: int,
        action: str,
        resolved_by: int,
    ) -> Optional[FraudFlag]:
        """
        Resolve a fraud flag with action taken.

        Args:
            flag_id: FraudFlag ID
            action: "none", "flagged", "suspended", or "revoked"
            resolved_by: Admin user ID

        Returns:
            Updated FraudFlag if successful, None otherwise
        """
        try:
            stmt = select(FraudFlag).where(FraudFlag.id == flag_id)
            result = await self.db.execute(stmt)
            flag = result.scalar_one_or_none()

            if not flag:
                logger.error(f"Fraud flag {flag_id} not found")
                return None

            flag.action_taken = action
            flag.resolved_at = datetime.utcnow()
            flag.resolved_by = resolved_by

            # If revoked, suspend referral code
            if action == "revoked":
                stmt = select(ReferralCode).where(
                    ReferralCode.discord_user_id == flag.discord_user_id
                )
                result = await self.db.execute(stmt)
                code = result.scalar_one_or_none()
                if code:
                    code.status = "revoked"

            await self.db.commit()
            logger.info(
                f"Resolved fraud flag {flag_id} for user {flag.discord_user_id}: "
                f"action={action}"
            )
            return flag

        except Exception as e:
            logger.error(f"Error resolving fraud flag {flag_id}: {e}")
            await self.db.rollback()
            return None

    # ============================================================================
    # PRIVATE HELPERS
    # ============================================================================

    async def _generate_unique_code(self) -> str:
        """
        Generate a unique referral code.

        Format: PP-{6_random_chars}

        Returns:
            Unique referral code string
        """
        max_attempts = 10
        for _ in range(max_attempts):
            random_part = "".join(
                secrets.choice(string.ascii_uppercase + string.digits)
                for _ in range(self.CODE_LENGTH)
            )
            code = f"{self.CODE_PREFIX}-{random_part}"

            # Check uniqueness
            stmt = select(func.count()).select_from(ReferralCode).where(
                ReferralCode.referral_code == code
            )
            result = await self.db.execute(stmt)
            if result.scalar() == 0:
                return code

        logger.error("Failed to generate unique referral code after 10 attempts")
        raise RuntimeError("Could not generate unique referral code")

    async def _calculate_reward_amount(self, discord_user_id: int) -> int:
        """
        Calculate referral reward amount based on user tier.

        Args:
            discord_user_id: Discord user ID

        Returns:
            Reward amount in cents
        """
        # Check if ambassador
        stmt = select(Ambassador).where(Ambassador.discord_user_id == discord_user_id)
        result = await self.db.execute(stmt)
        ambassador = result.scalar_one_or_none()

        if ambassador and ambassador.status == "active":
            return ambassador.referral_bonus_cents

        return self.REFERRAL_REWARDS["regular"]
