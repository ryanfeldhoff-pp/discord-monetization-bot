"""
Database Models and Connection Management.

Uses SQLAlchemy async with support for SQLite (dev) and PostgreSQL (prod).
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Time,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()


class AccountLink(Base):
    """Model for Discord-to-PrizePicks account linkage."""

    __tablename__ = "account_links"

    discord_user_id = Column(Integer, primary_key=True)
    prizepicks_user_id = Column(String, unique=True, nullable=False)
    linked_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="linked")  # linked, unlinked, pending


class Subscription(Base):
    """Model for board alert subscriptions."""

    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    discord_user_id = Column(Integer, nullable=False)
    sport = Column(String, nullable=False)
    quiet_hours_start = Column(Time, nullable=True)
    quiet_hours_end = Column(Time, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TailEvent(Base):
    """Model for entry tail events."""

    __tablename__ = "tail_events"

    id = Column(Integer, primary_key=True)
    entry_id = Column(String, nullable=False)
    discord_user_id = Column(Integer, nullable=False)
    action = Column(String)  # tail, fade, edit
    timestamp = Column(DateTime, default=datetime.utcnow)


class ProjectionSnapshot(Base):
    """Model for projection snapshots (for change detection)."""

    __tablename__ = "projection_snapshots"

    id = Column(Integer, primary_key=True)
    sport = Column(String, nullable=False)
    snapshot_json = Column(String, nullable=False)  # JSON string of projections
    captured_at = Column(DateTime, default=datetime.utcnow)


class Database:
    """Async database connection manager."""

    def __init__(self, engine):
        """
        Initialize database manager.

        Args:
            engine: SQLAlchemy async engine
        """
        self.engine = engine
        self.async_session = sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @classmethod
    async def create(cls, db_url: Optional[str] = None) -> "Database":
        """
        Create and initialize database connection.

        Args:
            db_url: Database URL (default: from env or SQLite)

        Returns:
            Database: Initialized database instance
        """
        import os

        if not db_url:
            db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bot.db")

        logger.info(f"Connecting to database: {db_url}")

        # Create async engine
        engine = create_async_engine(
            db_url,
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",
            pool_size=10 if "postgres" in db_url else 1,
            max_overflow=20,
        )

        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialized")
        return cls(engine)

    async def close(self) -> None:
        """Close database connection."""
        await self.engine.dispose()
        logger.info("Database connection closed")

    # Account Link Operations

    async def create_account_link(
        self,
        discord_user_id: int,
        prizepicks_user_id: str,
        status: str = "linked",
    ) -> AccountLink:
        """
        Create or update account link.

        Args:
            discord_user_id: Discord user ID
            prizepicks_user_id: PrizePicks user ID
            status: Link status

        Returns:
            AccountLink: Created link
        """
        async with self.async_session() as session:
            link = AccountLink(
                discord_user_id=discord_user_id,
                prizepicks_user_id=prizepicks_user_id,
                status=status,
            )
            session.merge(link)
            await session.commit()
            return link

    async def get_account_link(self, discord_user_id: int) -> Optional[AccountLink]:
        """
        Get account link for user.

        Args:
            discord_user_id: Discord user ID

        Returns:
            AccountLink or None
        """
        async with self.async_session() as session:
            result = await session.execute(
                select(AccountLink).where(
                    AccountLink.discord_user_id == discord_user_id
                )
            )
            return result.scalar_one_or_none()

    async def delete_account_link(self, discord_user_id: int) -> None:
        """
        Delete account link.

        Args:
            discord_user_id: Discord user ID
        """
        async with self.async_session() as session:
            await session.execute(
                select(AccountLink).where(
                    AccountLink.discord_user_id == discord_user_id
                )
            )
            link = await session.scalar(
                select(AccountLink).where(
                    AccountLink.discord_user_id == discord_user_id
                )
            )
            if link:
                await session.delete(link)
                await session.commit()

    # Subscription Operations

    async def create_subscription(
        self,
        discord_user_id: int,
        sport: str,
        quiet_hours_start: Optional[str] = None,
        quiet_hours_end: Optional[str] = None,
    ) -> Subscription:
        """
        Create subscription.

        Args:
            discord_user_id: Discord user ID
            sport: Sport name
            quiet_hours_start: Optional quiet hours start time
            quiet_hours_end: Optional quiet hours end time

        Returns:
            Subscription: Created subscription
        """
        async with self.async_session() as session:
            sub = Subscription(
                discord_user_id=discord_user_id,
                sport=sport,
                quiet_hours_start=quiet_hours_start,
                quiet_hours_end=quiet_hours_end,
            )
            session.add(sub)
            await session.commit()
            await session.refresh(sub)
            return sub

    async def get_subscription(
        self,
        discord_user_id: int,
        sport: str,
    ) -> Optional[Subscription]:
        """
        Get subscription.

        Args:
            discord_user_id: Discord user ID
            sport: Sport name

        Returns:
            Subscription or None
        """
        async with self.async_session() as session:
            result = await session.execute(
                select(Subscription).where(
                    (Subscription.discord_user_id == discord_user_id)
                    & (Subscription.sport == sport)
                )
            )
            return result.scalar_one_or_none()

    async def delete_subscription(
        self,
        discord_user_id: int,
        sport: str,
    ) -> None:
        """
        Delete subscription.

        Args:
            discord_user_id: Discord user ID
            sport: Sport name
        """
        async with self.async_session() as session:
            sub = await session.scalar(
                select(Subscription).where(
                    (Subscription.discord_user_id == discord_user_id)
                    & (Subscription.sport == sport)
                )
            )
            if sub:
                await session.delete(sub)
                await session.commit()

    async def get_user_subscriptions(self, discord_user_id: int) -> list[Subscription]:
        """
        Get all subscriptions for user.

        Args:
            discord_user_id: Discord user ID

        Returns:
            list: User's subscriptions
        """
        async with self.async_session() as session:
            result = await session.execute(
                select(Subscription).where(
                    Subscription.discord_user_id == discord_user_id
                )
            )
            return result.scalars().all()

    async def get_sport_subscribers(self, sport: str) -> list[Subscription]:
        """
        Get all subscribers for a sport.

        Args:
            sport: Sport name

        Returns:
            list: Sport subscribers
        """
        async with self.async_session() as session:
            result = await session.execute(
                select(Subscription).where(Subscription.sport == sport)
            )
            return result.scalars().all()

    # Tail Event Operations

    async def create_tail_event(
        self,
        entry_id: str,
        discord_user_id: int,
        action: str,
    ) -> TailEvent:
        """
        Create tail event.

        Args:
            entry_id: PrizePicks entry ID
            discord_user_id: Discord user ID
            action: Event action (tail, fade, edit)

        Returns:
            TailEvent: Created event
        """
        async with self.async_session() as session:
            event = TailEvent(
                entry_id=entry_id,
                discord_user_id=discord_user_id,
                action=action,
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)
            return event

    # Projection Snapshot Operations

    async def create_snapshot(
        self,
        sport: str,
        snapshot_json: str,
    ) -> ProjectionSnapshot:
        """
        Create projection snapshot.

        Args:
            sport: Sport name
            snapshot_json: JSON string of projections

        Returns:
            ProjectionSnapshot: Created snapshot
        """
        async with self.async_session() as session:
            snapshot = ProjectionSnapshot(
                sport=sport,
                snapshot_json=snapshot_json,
            )
            session.add(snapshot)
            await session.commit()
            await session.refresh(snapshot)
            return snapshot

    async def get_latest_snapshot(self, sport: str) -> Optional[ProjectionSnapshot]:
        """
        Get latest snapshot for sport.

        Args:
            sport: Sport name

        Returns:
            ProjectionSnapshot or None
        """
        async with self.async_session() as session:
            result = await session.execute(
                select(ProjectionSnapshot)
                .where(ProjectionSnapshot.sport == sport)
                .order_by(ProjectionSnapshot.captured_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
