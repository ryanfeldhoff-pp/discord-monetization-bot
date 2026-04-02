"""
Pytest configuration and shared fixtures for bot testing.

Provides comprehensive fixtures for mocking Discord objects, database sessions,
Redis clients, and other services used throughout the bot.
"""

import os
import pytest
import asyncio
from datetime import datetime
from typing import Optional, List
from unittest.mock import AsyncMock, MagicMock, patch
from unittest.mock import Mock

import discord
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Import models for database setup
from src.models.xp_models import Base


# ── Discord Object Fixtures ──

@pytest.fixture
def mock_bot():
    """
    Create a mock Discord bot instance.

    Includes common attributes like guilds, users, and channels.
    """
    bot = AsyncMock(spec=discord.Bot)
    bot.user = MagicMock(spec=discord.ClientUser)
    bot.user.id = 999999999
    bot.user.name = "TestBot"
    bot.user.discriminator = "0001"
    bot.user.avatar = None

    bot.guilds = []
    bot.cogs = {}
    bot.latency = 0.1
    bot.owner_id = 111111111

    # Mock methods
    bot.get_guild = MagicMock(return_value=None)
    bot.get_user = MagicMock(return_value=None)
    bot.get_channel = MagicMock(return_value=None)

    return bot


@pytest.fixture
def mock_ctx():
    """
    Create a mock ApplicationContext for slash commands.

    Includes response/followup methods, author, guild, and channel.
    """
    ctx = AsyncMock(spec=discord.ApplicationContext)

    # Author
    ctx.author = MagicMock(spec=discord.User)
    ctx.author.id = 123456789
    ctx.author.name = "test_user"
    ctx.author.discriminator = "0001"
    ctx.author.bot = False

    # Guild
    ctx.guild = MagicMock(spec=discord.Guild)
    ctx.guild.id = 654321
    ctx.guild.name = "Test Guild"

    # Channel
    ctx.channel = MagicMock(spec=discord.TextChannel)
    ctx.channel.id = 555555555
    ctx.channel.name = "test-channel"

    # Response methods
    ctx.respond = AsyncMock()
    ctx.interaction = AsyncMock(spec=discord.Interaction)
    ctx.interaction.response = AsyncMock()
    ctx.interaction.response.send_message = AsyncMock()
    ctx.interaction.followup = AsyncMock()
    ctx.interaction.followup.send = AsyncMock()

    return ctx


@pytest.fixture
def mock_interaction():
    """
    Create a mock Interaction for button/view testing.

    Used for testing UI components and button handlers.
    """
    interaction = AsyncMock(spec=discord.Interaction)

    # User/member info
    interaction.user = MagicMock(spec=discord.User)
    interaction.user.id = 123456789
    interaction.user.name = "test_user"

    interaction.guild = MagicMock(spec=discord.Guild)
    interaction.guild.id = 654321

    # Response methods
    interaction.response = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.defer = AsyncMock()

    interaction.followup = AsyncMock()
    interaction.followup.send = AsyncMock()

    # Message
    interaction.message = AsyncMock(spec=discord.Message)
    interaction.message.delete = AsyncMock()
    interaction.message.edit = AsyncMock()

    return interaction


@pytest.fixture
def sample_user():
    """
    Create a test Discord user object.

    Returns a mock user with realistic attributes.
    """
    user = MagicMock(spec=discord.User)
    user.id = 123456789
    user.name = "TestUser"
    user.discriminator = "0001"
    user.avatar = None
    user.bot = False
    user.system = False
    return user


@pytest.fixture
def sample_guild():
    """
    Create a test guild object.

    Returns a mock guild with realistic attributes.
    """
    guild = MagicMock(spec=discord.Guild)
    guild.id = 654321
    guild.name = "Test Guild"
    guild.owner_id = 111111111
    guild.member_count = 100
    guild.created_at = datetime.utcnow()
    return guild


@pytest.fixture
def sample_channel():
    """
    Create a test text channel object.

    Returns a mock channel with realistic attributes.
    """
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 555555555
    channel.name = "test-channel"
    channel.topic = "A test channel"
    channel.guild = MagicMock(spec=discord.Guild)
    channel.guild.id = 654321
    channel.guild.name = "Test Guild"
    channel.created_at = datetime.utcnow()
    return channel


# ── Database Fixtures ──

@pytest.fixture
async def mock_db_session():
    """
    Create an async SQLAlchemy session using SQLite in-memory.

    This fixture provides a real async database connection for testing
    without requiring an external database server.
    """
    # Use in-memory SQLite with async support
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Create and return session
    async with async_session() as session:
        yield session

    # Cleanup
    await engine.dispose()


# ── Cache/Redis Fixtures ──

@pytest.fixture
def mock_redis():
    """
    Create a mock Redis client.

    Uses a dict-based implementation for fast testing.
    """
    redis = AsyncMock()

    # Internal storage for the mock
    redis._data = {}

    async def mock_get(key: str) -> Optional[str]:
        return redis._data.get(key)

    async def mock_set(key: str, value: str, ex: Optional[int] = None) -> None:
        redis._data[key] = value

    async def mock_delete(*keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in redis._data:
                del redis._data[key]
                deleted += 1
        return deleted

    async def mock_incr(key: str) -> int:
        redis._data[key] = redis._data.get(key, 0) + 1
        return redis._data[key]

    async def mock_expire(key: str, seconds: int) -> bool:
        return key in redis._data

    redis.get = AsyncMock(side_effect=mock_get)
    redis.set = AsyncMock(side_effect=mock_set)
    redis.delete = AsyncMock(side_effect=mock_delete)
    redis.incr = AsyncMock(side_effect=mock_incr)
    redis.expire = AsyncMock(side_effect=mock_expire)
    redis.ping = AsyncMock(return_value=True)
    redis.close = AsyncMock()

    return redis


# ── Service Fixtures ──

@pytest.fixture
def mock_xp_manager():
    """
    Create a mock XP manager.

    Provides methods for awarding XP, checking balances, and tier progression.
    """
    manager = AsyncMock()

    manager.award_xp = AsyncMock(return_value=True)
    manager.get_xp = AsyncMock(return_value=0)
    manager.get_tier = AsyncMock(return_value="bronze")
    manager.check_tier_up = AsyncMock(return_value=None)
    manager.get_leaderboard = AsyncMock(return_value=[])

    return manager


@pytest.fixture
def mock_tournament_engine():
    """
    Create a mock tournament engine.

    Provides methods for managing tournaments and rankings.
    """
    engine = AsyncMock()

    engine.create_tournament = AsyncMock(return_value={"id": 1, "name": "Test Tournament"})
    engine.get_tournament = AsyncMock(return_value=None)
    engine.list_tournaments = AsyncMock(return_value=[])
    engine.award_tournament_points = AsyncMock(return_value=True)
    engine.finalize_tournament = AsyncMock(return_value=True)

    return engine


@pytest.fixture
def mock_referral_manager():
    """
    Create a mock referral manager.

    Provides methods for managing referral tracking and rewards.
    """
    manager = AsyncMock()

    manager.track_referral = AsyncMock(return_value=True)
    manager.get_referral_code = AsyncMock(return_value="REF123ABC")
    manager.validate_referral = AsyncMock(return_value=True)
    manager.claim_referral_reward = AsyncMock(return_value=True)
    manager.get_referral_stats = AsyncMock(return_value={"referrals": 0, "rewards": 0})

    return manager


@pytest.fixture
def mock_prizepicks_api():
    """
    Create a mock PrizePicks API client.

    Provides methods for API calls to PrizePicks backend.
    """
    client = AsyncMock()

    client.get_user = AsyncMock(return_value=None)
    client.get_entries = AsyncMock(return_value=[])
    client.get_contests = AsyncMock(return_value=[])
    client.validate_state = AsyncMock(return_value=True)
    client.close = AsyncMock()

    return client


# ── Test Markers ──

def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow")
    config.addinivalue_line("markers", "unit: mark test as unit test")


# ── Test Utilities ──

@pytest.fixture
def mock_message():
    """Create a mock Discord message."""
    msg = MagicMock(spec=discord.Message)
    msg.id = 999999999
    msg.author = MagicMock(spec=discord.User)
    msg.author.id = 123456789
    msg.author.name = "test_user"
    msg.author.bot = False
    msg.guild = MagicMock(spec=discord.Guild)
    msg.guild.id = 654321
    msg.channel = MagicMock(spec=discord.TextChannel)
    msg.channel.id = 555555555
    msg.content = "Test message"
    msg.created_at = datetime.utcnow()
    msg.edited_at = None
    msg.embeds = []
    msg.mentions = []
    return msg


@pytest.fixture
def mock_settings():
    """Create mock configuration settings."""
    settings = MagicMock()
    settings.discord = MagicMock()
    settings.discord.bot_token = "test_token"
    settings.discord.guild_id = 654321

    settings.database = MagicMock()
    settings.database.database_url = "sqlite+aiosqlite:///:memory:"

    settings.redis = MagicMock()
    settings.redis.redis_url = "redis://localhost:6379/0"
    settings.redis.enabled = True

    settings.xp = MagicMock()
    settings.xp.xp_per_message = 5
    settings.xp.xp_per_share = 15
    settings.xp.xp_linked_multiplier = 2.0
    settings.xp.xp_daily_cap = 500

    settings.tiers = MagicMock()
    settings.tiers.bronze_threshold = 500
    settings.tiers.silver_threshold = 2500
    settings.tiers.gold_threshold = 7500
    settings.tiers.diamond_threshold = 15000
    settings.tiers.legend_threshold = 30000

    settings.api = MagicMock()
    settings.api.prizepicks_base_url = "https://api.prizepicks.com"
    settings.api.prizepicks_api_key = "test_key"

    return settings


@pytest.fixture
def env_vars(monkeypatch):
    """Set required environment variables for testing."""
    monkeypatch.setenv("DISCORD_TOKEN", "test_token")
    monkeypatch.setenv("DISCORD_GUILD_ID", "654321")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("REDIS_ENABLED", "true")
    monkeypatch.setenv("PRIZEPICKS_API_KEY", "test_key")
    monkeypatch.setenv("PRIZEPICKS_API_BASE", "https://api.prizepicks.com")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
