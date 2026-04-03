"""
XP System Database Models

Async SQLAlchemy models for tracking user XP, transactions, redemptions,
and ranking data.
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
    JSON,
    Index,
)
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession

Base = declarative_base()


class XPLedger(Base):
    """
    Core XP balance and metadata per user.

    Tracks current XP, lifetime XP, peak XP, last activity, and current tier.
    """
    __tablename__ = "xp_ledger"

    discord_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    xp_balance: Mapped[int] = mapped_column(Integer, default=0)
    xp_lifetime: Mapped[int] = mapped_column(Integer, default=0)
    xp_peak: Mapped[int] = mapped_column(Integer, default=0)
    current_tier: Mapped[str] = mapped_column(String(20), default="bronze")
    last_active: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_xp_balance", "xp_balance"),
        Index("idx_last_active", "last_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<XPLedger(user_id={self.discord_user_id}, "
            f"balance={self.xp_balance}, tier={self.current_tier})>"
        )


class XPTransaction(Base):
    """
    Audit trail for all XP modifications.

    Tracks every XP award, deduction, or decay event with source and metadata.
    """
    __tablename__ = "xp_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount: Mapped[int] = mapped_column(Integer)  # Positive or negative
    source: Mapped[str] = mapped_column(String(50))  # "message", "entry_shared", "tournament_win", etc.
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON stringified metadata
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_user_timestamp", "discord_user_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<XPTransaction(user_id={self.discord_user_id}, "
            f"amount={self.amount}, source={self.source})>"
        )


class Redemption(Base):
    """
    Record of XP redemptions for promotional rewards.

    Tracks what items were redeemed, when, and their redemption status.
    """
    __tablename__ = "redemptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    item_id: Mapped[str] = mapped_column(String(50))  # "discount_code", "free_entry_5", "deposit_match_25"
    xp_cost: Mapped[int] = mapped_column(Integer)
    promo_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="completed")  # "completed", "pending", "failed"
    redeemed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Additional context

    __table_args__ = (
        Index("idx_user_redeemed_at", "discord_user_id", "redeemed_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Redemption(user_id={self.discord_user_id}, "
            f"item={self.item_id}, status={self.status})>"
        )


class RedemptionCounter(Base):
    """
    Monthly redemption counter per user per tier.

    Enforces monthly limits on redemptions (resets 1st of each month).
    """
    __tablename__ = "redemption_counter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    month: Mapped[int] = mapped_column(Integer)  # 1-12
    year: Mapped[int] = mapped_column(Integer)
    count: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        Index("idx_user_month_year", "discord_user_id", "month", "year"),
    )

    def __repr__(self) -> str:
        return (
            f"<RedemptionCounter(user_id={self.discord_user_id}, "
            f"period={self.month}/{self.year}, count={self.count})>"
        )


class RecapPreference(Base):
    """
    User preferences for monthly recap cards.

    Tracks opt-out status and last recap generation timestamp.
    """
    __tablename__ = "recap_preference"

    discord_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)
    last_recap_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<RecapPreference(user_id={self.discord_user_id}, "
            f"opted_out={self.opted_out})>"
        )


class AccountLink(Base):
    """
    Links Discord user to PrizePicks account.

    Stores mapping between Discord user IDs and PrizePicks account identifiers.
    """
    __tablename__ = "account_links"

    discord_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    prizepicks_user_id: Mapped[str] = mapped_column(String(100))
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("idx_pp_user_id", "prizepicks_user_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<AccountLink(discord_id={self.discord_user_id}, "
            f"pp_id={self.prizepicks_user_id})>"
        )
