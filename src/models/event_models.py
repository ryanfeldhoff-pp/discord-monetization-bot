"""
Community Events Database Models (Pillar 3)

Models for polls, tournaments, predictions, and game-day channels.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    BigInteger, DateTime, Integer, String, Text, Boolean, Index, Float,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.xp_models import Base


class Poll(Base):
    """Community poll (Taco Tuesday, custom polls, etc.)."""
    __tablename__ = "polls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    poll_type: Mapped[str] = mapped_column(String(50), default="custom")  # "taco_tuesday", "custom", "projection"
    options_json: Mapped[str] = mapped_column(Text)  # JSON array of option strings
    channel_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # Discord message with poll embed
    created_by: Mapped[int] = mapped_column(BigInteger)  # admin who created
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    closes_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_poll_active", "is_active"),
        Index("idx_poll_type", "poll_type"),
    )

    def __repr__(self) -> str:
        return f"<Poll(id={self.id}, title='{self.title}', active={self.is_active})>"


class PollVote(Base):
    """Individual vote on a poll."""
    __tablename__ = "poll_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    poll_id: Mapped[int] = mapped_column(Integer, index=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    option_index: Mapped[int] = mapped_column(Integer)  # 0-based index into options_json
    voted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_poll_user", "poll_id", "discord_user_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<PollVote(poll={self.poll_id}, user={self.discord_user_id}, option={self.option_index})>"


class Tournament(Base):
    """Prediction tournament container."""
    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tournament_type: Mapped[str] = mapped_column(String(50), default="weekly")  # "weekly", "seasonal", "special"
    sport: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entry_fee_xp: Mapped[int] = mapped_column(Integer, default=0)  # XP cost to enter (0 = free)
    max_participants: Mapped[int] = mapped_column(Integer, default=0)  # 0 = unlimited
    picks_required: Mapped[int] = mapped_column(Integer, default=5)
    prize_pool_json: Mapped[str] = mapped_column(Text, default='{"1st": "Free Entry ($10)", "2nd": "Free Entry ($5)", "3rd": "Discount Code"}')
    status: Mapped[str] = mapped_column(String(20), default="upcoming")  # "upcoming", "open", "locked", "scoring", "completed"
    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger)
    opens_at: Mapped[datetime] = mapped_column(DateTime)
    locks_at: Mapped[datetime] = mapped_column(DateTime)  # No more entries/predictions after this
    scores_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_tournament_status", "status"),
        Index("idx_tournament_opens", "opens_at"),
    )

    def __repr__(self) -> str:
        return f"<Tournament(id={self.id}, title='{self.title}', status={self.status})>"


class TournamentEntry(Base):
    """User entry/registration in a tournament."""
    __tablename__ = "tournament_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournament_id: Mapped[int] = mapped_column(Integer, index=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    predictions_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of picks
    score: Mapped[float] = mapped_column(Float, default=0.0)
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    xp_paid: Mapped[int] = mapped_column(Integer, default=0)
    entered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    scored_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_tourney_user", "tournament_id", "discord_user_id", unique=True),
        Index("idx_tourney_score", "tournament_id", "score"),
    )

    def __repr__(self) -> str:
        return f"<TournamentEntry(tournament={self.tournament_id}, user={self.discord_user_id}, score={self.score})>"


class GameDayChannel(Base):
    """Auto-created game-day channels."""
    __tablename__ = "gameday_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    sport: Mapped[str] = mapped_column(String(50))
    event_name: Mapped[str] = mapped_column(String(200))  # e.g. "Chiefs vs Bills"
    event_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # External event ID
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="scheduled")  # "scheduled", "active", "archived"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_gameday_status", "status"),
        Index("idx_gameday_start", "start_time"),
    )

    def __repr__(self) -> str:
        return f"<GameDayChannel(id={self.id}, event='{self.event_name}', status={self.status})>"
