"""
Referral Amplifier System Database Models

Async SQLAlchemy models for tracking referral codes, conversions, challenges,
ambassador programs, and fraud detection.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    String,
    Text,
    Boolean,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from src.models.xp_models import Base


class ReferralCode(Base):
    """
    Maps Discord users to referral codes and tracks referral performance.

    Tracks referral codes, URLs, conversion counts, earnings, and ambassador status.
    """
    __tablename__ = "referral_codes"

    discord_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    referral_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    referral_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    total_referrals: Mapped[int] = mapped_column(Integer, default=0)
    total_ftds: Mapped[int] = mapped_column(Integer, default=0)
    total_earnings: Mapped[int] = mapped_column(Integer, default=0)  # in cents
    is_ambassador: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # "active", "suspended", "revoked"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<ReferralCode(user_id={self.discord_user_id}, "
            f"code={self.referral_code}, status={self.status})>"
        )


class ReferralConversion(Base):
    """
    Tracks each referral conversion event.

    Records when a referred user signs up, completes FTD, or places an entry,
    along with reward details and fraud flags.
    """
    __tablename__ = "referral_conversions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_discord_id: Mapped[int] = mapped_column(BigInteger, index=True)
    referred_discord_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    referred_pp_user_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    referral_code_used: Mapped[str] = mapped_column(String(50), index=True)
    conversion_type: Mapped[str] = mapped_column(String(50))  # "signup", "ftd", "entry_placed"
    attribution_source: Mapped[str] = mapped_column(String(50))  # "tail", "win_share", "recap_card", "direct", "challenge"
    reward_amount: Mapped[int] = mapped_column(Integer, default=0)  # in cents
    reward_status: Mapped[str] = mapped_column(String(20), default="pending")  # "pending", "credited", "denied", "fraud_flagged"
    converted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    rewarded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_referrer_converted_at", "referrer_discord_id", "converted_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ReferralConversion(id={self.id}, referrer={self.referrer_discord_id}, "
            f"type={self.conversion_type}, status={self.reward_status})>"
        )


class ReferralChallenge(Base):
    """
    Community-wide referral challenges.

    Tracks guild-specific referral challenges with targets, rewards, and status.
    """
    __tablename__ = "referral_challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    challenge_type: Mapped[str] = mapped_column(String(50))  # "ftd_milestone", "monthly_target", "seasonal"
    target_count: Mapped[int] = mapped_column(Integer)
    current_count: Mapped[int] = mapped_column(Integer, default=0)
    reward_config_json: Mapped[str] = mapped_column(Text)  # JSON with reward details
    status: Mapped[str] = mapped_column(String(20))  # "upcoming", "active", "completed", "failed"
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_guild_status", "guild_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<ReferralChallenge(id={self.id}, guild_id={self.guild_id}, "
            f"type={self.challenge_type}, status={self.status})>"
        )


class Ambassador(Base):
    """
    Ambassador program details and tier information.

    Tracks ambassador tier, FTD counts, perks, and status for top referrers.
    """
    __tablename__ = "ambassadors"

    discord_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tier: Mapped[str] = mapped_column(String(20))  # "rising_star", "veteran", "elite"
    referral_bonus_cents: Mapped[int] = mapped_column(Integer, default=2500)
    monthly_ftd_count: Mapped[int] = mapped_column(Integer, default=0)
    lifetime_ftd_count: Mapped[int] = mapped_column(Integer, default=0)
    nominated_at: Mapped[datetime] = mapped_column(DateTime)
    promoted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # "active", "probation", "removed"
    perks_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON with current perks
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_tier_status", "tier", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<Ambassador(user_id={self.discord_user_id}, "
            f"tier={self.tier}, status={self.status})>"
        )


class WinShareLog(Base):
    """
    Tracks win sharing events with embedded referral CTAs.

    Records when users share wins via channel posts, DMs, or social, and tracks
    engagement and conversions from referral CTAs.
    """
    __tablename__ = "win_share_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    entry_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    win_amount_cents: Mapped[int] = mapped_column(Integer)
    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    referral_code_attached: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    share_type: Mapped[str] = mapped_column(String(50))  # "channel_post", "dm_prompt", "social_share"
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)
    shared_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_user_shared_at", "discord_user_id", "shared_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<WinShareLog(id={self.id}, user_id={self.discord_user_id}, "
            f"type={self.share_type}, conversions={self.conversions})>"
        )


class FraudFlag(Base):
    """
    Fraud detection and flagging records.

    Tracks suspected fraud indicators, severity levels, and actions taken
    against flagged users.
    """
    __tablename__ = "fraud_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    flag_type: Mapped[str] = mapped_column(String(50))  # "self_referral", "velocity_spike", "shared_ip", "duplicate_account"
    severity: Mapped[str] = mapped_column(String(20))  # "low", "medium", "high", "critical"
    details_json: Mapped[str] = mapped_column(Text)
    action_taken: Mapped[str] = mapped_column(String(50))  # "none", "flagged", "suspended", "revoked"
    flagged_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        Index("idx_flag_type_severity", "flag_type", "severity"),
    )

    def __repr__(self) -> str:
        return (
            f"<FraudFlag(id={self.id}, user_id={self.discord_user_id}, "
            f"type={self.flag_type}, severity={self.severity})>"
        )
