"""
Community Events Database Models

Async SQLAlchemy models for managing polls, tournaments, game-day channels,
and scheduled events within Discord communities.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    String,
    Text,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.xp_models import Base


class Poll(Base):
    """
    Weekly community polls (Taco Tuesday, custom surveys, etc.).

    Tracks poll questions, options, votes, and lifecycle state.
    """
    __tablename__ = "polls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    poll_type: Mapped[str] = mapped_column(String(50))  # "taco_tuesday", "community", "custom"
    options_json: Mapped[str] = mapped_column(Text)  # JSON list of option dicts
    votes_json: Mapped[str] = mapped_column(Text)  # JSON dict of user_id -> option_index
    status: Mapped[str] = mapped_column(String(20))  # "active", "closed", "scheduled"
    created_by: Mapped[int] = mapped_column(BigInteger)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closes_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_guild_id", "guild_id"),
        Index("idx_status", "status"),
        Index("idx_poll_type", "poll_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<Poll(id={self.id}, guild_id={self.guild_id}, "
            f"title={self.title}, status={self.status})>"
        )


class PollVote(Base):
    """
    Individual votes on polls.

    Tracks which user voted for which option in a poll.
    """
    __tablename__ = "poll_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    poll_id: Mapped[int] = mapped_column(Integer, index=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    option_index: Mapped[int] = mapped_column(Integer)
    voted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("poll_id", "discord_user_id", name="uq_poll_vote"),
        Index("idx_poll_id", "poll_id"),
        Index("idx_discord_user_id", "discord_user_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<PollVote(id={self.id}, poll_id={self.poll_id}, "
            f"user_id={self.discord_user_id}, option={self.option_index})>"
        )


class Tournament(Base):
    """
    Weekly prediction tournaments within the community.

    Tracks tournament metadata, scoring rules, prizes, and lifecycle.
    """
    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tournament_type: Mapped[str] = mapped_column(String(50))  # "weekly_prediction", "special_event"
    status: Mapped[str] = mapped_column(String(20))  # "upcoming", "active", "scoring", "completed", "cancelled"
    entry_fee_xp: Mapped[int] = mapped_column(Integer, default=0)
    max_participants: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    prize_config_json: Mapped[str] = mapped_column(Text)  # JSON with prize tiers
    scoring_config_json: Mapped[str] = mapped_column(Text)  # JSON with scoring rules
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_guild_status", "guild_id", "status"),
        Index("idx_starts_at", "starts_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Tournament(id={self.id}, guild_id={self.guild_id}, "
            f"title={self.title}, status={self.status})>"
        )


class TournamentEntry(Base):
    """
    User entry records in tournaments.

    Tracks predictions, scores, rankings, and prize information per user per tournament.
    """
    __tablename__ = "tournament_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tournament_id: Mapped[int] = mapped_column(Integer, index=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    predictions_json: Mapped[str] = mapped_column(Text)  # JSON list of predictions
    score: Mapped[int] = mapped_column(Integer, default=0)
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    prize_awarded: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    scored_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("tournament_id", "discord_user_id", name="uq_tournament_user"),
        Index("idx_tournament_id", "tournament_id"),
        Index("idx_discord_user_id", "discord_user_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<TournamentEntry(id={self.id}, tournament_id={self.tournament_id}, "
            f"user_id={self.discord_user_id}, rank={self.rank})>"
        )


class GameDayChannel(Base):
    """
    Auto-generated game-day specific channels.

    Tracks channel lifecycle, sport/event metadata, and archive status.
    """
    __tablename__ = "gameday_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    sport: Mapped[str] = mapped_column(String(50))  # "nfl", "nba", "mlb", etc.
    event_name: Mapped[str] = mapped_column(String(200))
    event_id: Mapped[str] = mapped_column(String(100))  # External event ID
    status: Mapped[str] = mapped_column(String(20))  # "scheduled", "active", "archived"
    scheduled_start: Mapped[datetime] = mapped_column(DateTime)
    actual_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_guild_status", "guild_id", "status"),
        Index("idx_sport", "sport"),
        Index("idx_event_id", "event_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<GameDayChannel(id={self.id}, guild_id={self.guild_id}, "
            f"event={self.event_name}, status={self.status})>"
        )


class ScheduledEvent(Base):
    """
    Generic scheduled community events (AMAs, special events, etc.).

    Tracks event metadata, hosts, configuration, and lifecycle.
    """
    __tablename__ = "scheduled_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    event_type: Mapped[str] = mapped_column(String(50))  # "ama", "special", "custom"
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    host_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20))  # "scheduled", "active", "completed", "cancelled"
    config_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_guild_type_status", "guild_id", "event_type", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<ScheduledEvent(id={self.id}, guild_id={self.guild_id}, "
            f"type={self.event_type}, title={self.title}, status={self.status})>"
        )
