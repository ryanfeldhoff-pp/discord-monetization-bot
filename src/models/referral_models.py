"""
Referral Amplifier Database Models (Pillar 4)

Models for referral tracking, challenges, ambassador program, and win sharing.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    BigInteger, DateTime, Integer, String, Text, Boolean, Index, Float,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.xp_models import Base


class ReferralCode(Base):
    """User's referral code and stats."""
    __tablename__ = "referral_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # PP-XXXXXX format
    referral_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    total_signups: Mapped[int] = mapped_column(Integer, default=0)
    total_referrals: Mapped[int] = mapped_column(Integer, default=0)  # Total referral count
    total_ftds: Mapped[int] = mapped_column(Integer, default=0)  # First-time deposits
    total_earned_cents: Mapped[int] = mapped_column(Integer, default=0)  # Total rewards earned
    total_earnings: Mapped[int] = mapped_column(Integer, default=0)  # Alias for total_earned_cents
    ambassador_tier: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # "rising_star", "veteran", "elite"
    is_ambassador: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_referral_ftds", "total_ftds"),
        Index("idx_referral_ambassador", "ambassador_tier"),
    )

    def __repr__(self) -> str:
        return f"<ReferralCode(user={self.discord_user_id}, code='{self.code}', ftds={self.total_ftds})>"


class ReferralConversion(Base):
    """Individual referral conversion event (signup or FTD)."""
    __tablename__ = "referral_conversions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_discord_id: Mapped[int] = mapped_column(BigInteger, index=True)
    referred_user_id: Mapped[str] = mapped_column(String(100))  # PP user ID of referred person
    referral_code: Mapped[str] = mapped_column(String(20), index=True)
    conversion_type: Mapped[str] = mapped_column(String(20))  # "signup", "ftd"
    reward_amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    reward_status: Mapped[str] = mapped_column(String(20), default="pending")  # "pending", "paid", "flagged"
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # "tail", "share", "link", "qr"
    ip_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # For fraud detection
    converted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_conversion_referrer", "referrer_discord_id", "converted_at"),
        Index("idx_conversion_code", "referral_code"),
    )

    def __repr__(self) -> str:
        return f"<ReferralConversion(referrer={self.referrer_discord_id}, type={self.conversion_type})>"


class CommunityChallenge(Base):
    """Community-wide referral challenge (e.g., '500 FTDs this month → everyone gets a free entry')."""
    __tablename__ = "community_challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    challenge_type: Mapped[str] = mapped_column(String(50), default="ftd_count")  # "ftd_count", "entry_count", "referral_count"
    target_value: Mapped[int] = mapped_column(Integer)  # Goal to hit
    current_value: Mapped[int] = mapped_column(Integer, default=0)  # Current progress
    reward_description: Mapped[str] = mapped_column(String(200))  # "Free entry for everyone"
    reward_type: Mapped[str] = mapped_column(String(50), default="free_entry")  # "free_entry", "xp_multiplier", "promo_code"
    reward_value: Mapped[int] = mapped_column(Integer, default=0)  # cents or XP amount
    status: Mapped[str] = mapped_column(String(20), default="active")  # "active", "completed", "failed", "cancelled"
    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # Progress bar message
    created_by: Mapped[int] = mapped_column(BigInteger)
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_challenge_status", "status"),
        Index("idx_challenge_dates", "starts_at", "ends_at"),
    )

    def __repr__(self) -> str:
        return f"<CommunityChallenge(id={self.id}, title='{self.title}', progress={self.current_value}/{self.target_value})>"


class WinShare(Base):
    """Record of a user sharing a win in the community."""
    __tablename__ = "win_shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    entry_id: Mapped[str] = mapped_column(String(100))  # PP entry ID
    win_amount_cents: Mapped[int] = mapped_column(Integer)
    channel_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    referral_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    tails_generated: Mapped[int] = mapped_column(Integer, default=0)
    referrals_generated: Mapped[int] = mapped_column(Integer, default=0)
    shared_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_winshare_user", "discord_user_id", "shared_at"),
    )

    def __repr__(self) -> str:
        return f"<WinShare(user={self.discord_user_id}, win=${self.win_amount_cents/100:.2f})>"


class WinSharePreference(Base):
    """User preferences for post-win DM notifications."""
    __tablename__ = "win_share_preferences"

    discord_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dm_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_share: Mapped[bool] = mapped_column(Boolean, default=False)
    min_win_amount_cents: Mapped[int] = mapped_column(Integer, default=500)  # Only DM for wins > $5
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<WinSharePreference(user={self.discord_user_id}, dm={self.dm_enabled})>"


class ReferralChallenge(Base):
    """Guild-specific referral challenge for tracking FTD milestones and rewarding participants."""
    __tablename__ = "referral_challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    challenge_type: Mapped[str] = mapped_column(String(50))  # "ftd_milestone", "monthly_target", "seasonal"
    target_count: Mapped[int] = mapped_column(Integer)  # Target FTD count
    current_count: Mapped[int] = mapped_column(Integer, default=0)  # Current progress
    reward_config_json: Mapped[str] = mapped_column(Text)  # JSON with reward details
    status: Mapped[str] = mapped_column(String(20), default="active")  # "upcoming", "active", "completed", "failed"
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_challenge_guild_status", "guild_id", "status"),
        Index("idx_challenge_dates", "starts_at", "ends_at"),
    )

    def __repr__(self) -> str:
        return f"<ReferralChallenge(guild={self.guild_id}, title='{self.title}', progress={self.current_count}/{self.target_count})>"


class Ambassador(Base):
    """Ambassador program member with tier and referral tracking."""
    __tablename__ = "ambassadors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    tier: Mapped[str] = mapped_column(String(50))  # "rising_star", "veteran", "elite"
    referral_bonus_cents: Mapped[int] = mapped_column(Integer, default=0)  # Tier-specific bonus
    lifetime_ftd_count: Mapped[int] = mapped_column(Integer, default=0)  # Total FTDs generated
    status: Mapped[str] = mapped_column(String(20), default="active")  # "active", "inactive", "suspended"
    nominated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    promoted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_ambassador_tier", "tier"),
        Index("idx_ambassador_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Ambassador(user={self.discord_user_id}, tier='{self.tier}', ftds={self.lifetime_ftd_count})>"


class FraudFlag(Base):
    """Suspicious activity flag for fraud detection."""
    __tablename__ = "fraud_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    flag_type: Mapped[str] = mapped_column(String(50))  # "ip_mismatch", "rapid_conversions", "unusual_pattern", etc.
    severity: Mapped[str] = mapped_column(String(20))  # "low", "medium", "high"
    reason: Mapped[str] = mapped_column(Text)  # Description of suspicious activity
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Additional data
    status: Mapped[str] = mapped_column(String(20), default="open")  # "open", "investigating", "resolved", "dismissed"
    flagged_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_fraud_user_status", "discord_user_id", "status"),
        Index("idx_fraud_severity", "severity"),
    )

    def __repr__(self) -> str:
        return f"<FraudFlag(user={self.discord_user_id}, type='{self.flag_type}', severity='{self.severity}')>"
