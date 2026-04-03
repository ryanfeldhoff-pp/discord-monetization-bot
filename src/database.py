"""
Database initialization and session management.

Handles async SQLAlchemy setup and session creation.
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker

from src.models.xp_models import Base
# Import all model modules so their tables are registered with Base.metadata
import src.models.event_models  # noqa: F401
import src.models.referral_models  # noqa: F401

logger = logging.getLogger(__name__)


class Database:
    """Database management class."""

    def __init__(self, database_url: str, echo: bool = False):
        """
        Initialize database.

        Args:
            database_url: Async SQLAlchemy database URL
            echo: Enable SQL query logging
        """
        self.database_url = database_url
        self.engine: Optional[AsyncEngine] = None
        self.async_session_maker: Optional[sessionmaker] = None

    async def initialize(self) -> None:
        """
        Initialize database engine and create tables.

        Should be called during bot startup.
        """
        try:
            self.engine = create_async_engine(
                self.database_url,
                echo=False,
                pool_pre_ping=True,
            )

            self.async_session_maker = sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            # Create all tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def get_session(self) -> AsyncSession:
        """
        Get a new database session.

        Returns:
            AsyncSession instance
        """
        if not self.async_session_maker:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        return self.async_session_maker()

    async def close(self) -> None:
        """
        Close database engine.

        Should be called during bot shutdown.
        """
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connection closed")

    async def health_check(self) -> bool:
        """
        Check database connectivity.

        Returns:
            True if database is accessible
        """
        try:
            async with self.engine.connect() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
