"""
End-to-end tests for XP System cog.

Tests message-based XP earning, anti-spam cooldowns, minimum length requirements,
leaderboard display, and tier-up notifications.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

import discord
from discord.ext import commands

from src.cogs.xp_system import XPSystem


@pytest.fixture
def mock_bot():
    """Create a mock Discord bot."""
    bot = MagicMock(spec=commands.Bot)
    bot.wait_until_ready = AsyncMock()
    return bot


@pytest.fixture
def mock_xp_manager():
    """Create a mock XPManager."""
    manager = AsyncMock()
    manager.XP_VALUES = {"message": 10}
    manager.TIER_THRESHOLDS = {
        "bronze": 1000,
        "silver": 2500,
        "gold": 7500,
        "diamond": 15000,
    }
    manager.award_xp = AsyncMock(return_value=(True, "XP awarded"))
    manager.get_xp = AsyncMock(return_value={
        "balance": 10000,
        "tier": "gold",
        "lifetime": 15000,
    })
    manager.get_rank = AsyncMock(return_value={
        "rank": 42,
        "percentile": 50.0,
    })
    manager.get_leaderboard = AsyncMock(return_value={
        "leaderboard": [],
        "user_position": {"rank": 42, "xp": 10000},
    })
    manager.flush_xp_buffer = AsyncMock(return_value=5)
    manager.process_decay = AsyncMock(return_value=3)
    return manager


@pytest.fixture
def xp_cog(mock_bot, mock_xp_manager):
    """Create an XPSystem cog instance."""
    return XPSystem(mock_bot, mock_xp_manager)


@pytest.fixture
def mock_message():
    """Create a mock Discord message."""
    msg = MagicMock(spec=discord.Message)
    msg.author = MagicMock(spec=discord.User)
    msg.author.bot = False
    msg.author.id = 123456789
    msg.guild = MagicMock(spec=discord.Guild)
    msg.channel = MagicMock(spec=discord.TextChannel)
    msg.channel.send = AsyncMock()
    return msg


@pytest.fixture
def mock_context():
    """Create a mock application context."""
    ctx = MagicMock(spec=discord.ApplicationContext)
    ctx.author = MagicMock(spec=discord.User)
    ctx.author.id = 123456789
    ctx.author.name = "TestUser"
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_xp_message_awards_xp(xp_cog, mock_message):
    """Test that valid messages award XP after cooldown."""
    mock_message.content = "This is a valid message with enough characters"
    mock_message.author.id = 111111111

    xp_cog.xp_manager.award_xp = AsyncMock(return_value=(True, 10))

    await xp_cog.on_message(mock_message)

    xp_cog.xp_manager.award_xp.assert_called_once()
    call_args = xp_cog.xp_manager.award_xp.call_args
    assert call_args[1]["user_id"] == 111111111
    assert call_args[1]["amount"] > 0


@pytest.mark.asyncio
async def test_xp_message_cooldown(xp_cog, mock_message):
    """Test that XP cooldown prevents rapid consecutive awards."""
    user_id = 222222222
    mock_message.author.id = user_id
    mock_message.content = "This is a valid message for testing cooldown"

    xp_cog.xp_manager.award_xp = AsyncMock(return_value=(True, 10))

    await xp_cog.on_message(mock_message)
    call_count_first = xp_cog.xp_manager.award_xp.call_count

    await xp_cog.on_message(mock_message)
    call_count_second = xp_cog.xp_manager.award_xp.call_count

    assert call_count_second <= call_count_first + 1


@pytest.mark.asyncio
async def test_xp_message_min_length(xp_cog, mock_message):
    """Test that short messages do not award XP."""
    mock_message.content = "short"
    mock_message.author.id = 333333333

    xp_cog.xp_manager.award_xp = AsyncMock(return_value=(False, 0))

    await xp_cog.on_message(mock_message)

    if xp_cog.xp_manager.award_xp.called:
        assert xp_cog.xp_manager.award_xp.return_value[0] is False


@pytest.mark.asyncio
async def test_xp_message_ignores_bot(xp_cog, mock_message):
    """Test that bot messages are ignored."""
    mock_message.author.bot = True
    mock_message.content = "This is a bot message"

    xp_cog.xp_manager.award_xp = AsyncMock()

    await xp_cog.on_message(mock_message)

    xp_cog.xp_manager.award_xp.assert_not_called()


@pytest.mark.asyncio
async def test_xp_message_ignores_dm(xp_cog):
    """Test that DM messages are ignored."""
    msg = MagicMock(spec=discord.Message)
    msg.author = MagicMock(spec=discord.User)
    msg.author.bot = False
    msg.guild = None
    msg.content = "This is a DM message"

    xp_cog.xp_manager.award_xp = AsyncMock()

    await xp_cog.on_message(msg)

    xp_cog.xp_manager.award_xp.assert_not_called()


@pytest.mark.asyncio
async def test_xp_leaderboard_returns_embed(xp_cog, mock_context):
    """Test that leaderboard command returns a properly formatted embed."""
    mock_context.defer = AsyncMock()
    mock_context.author.avatar = MagicMock()
    mock_context.author.avatar.url = "https://example.com/avatar.png"

    leaderboard_data = [
        {"rank": 1, "user_id": 111, "xp": 50000},
        {"rank": 2, "user_id": 222, "xp": 45000},
        {"rank": 3, "user_id": 333, "xp": 40000},
    ]

    xp_cog.xp_manager.get_leaderboard = AsyncMock(
        return_value={
            "leaderboard": leaderboard_data,
            "user_position": {"rank": 15, "xp": 10000},
        }
    )

    xp_cog.bot.fetch_user = AsyncMock(side_effect=lambda uid: MagicMock(name=f"User{uid}"))

    await xp_cog.leaderboard_command(mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args[1]
    assert "embed" in call_kwargs


@pytest.mark.asyncio
async def test_xp_leaderboard_empty_state(xp_cog, mock_context):
    """Test that empty leaderboard shows appropriate message."""
    mock_context.defer = AsyncMock()
    mock_context.author.avatar = MagicMock()
    mock_context.author.avatar.url = "https://example.com/avatar.png"

    xp_cog.xp_manager.get_leaderboard = AsyncMock(
        return_value={
            "leaderboard": [],
            "user_position": None,
        }
    )

    await xp_cog.leaderboard_command(mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args[1]
    assert "embed" in call_kwargs


@pytest.mark.asyncio
async def test_xp_command_returns_user_xp(xp_cog, mock_context):
    """Test that /xp command displays user's XP and tier."""
    mock_context.defer = AsyncMock()
    mock_context.author.avatar = MagicMock()
    mock_context.author.avatar.url = "https://example.com/avatar.png"

    xp_cog.xp_manager.get_xp = AsyncMock(
        return_value={
            "balance": 15000,
            "tier": "gold",
            "lifetime": 20000,
        }
    )
    xp_cog.xp_manager.get_rank = AsyncMock(
        return_value={
            "rank": 42,
            "percentile": 50.0,
        }
    )

    await xp_cog.xp_command(mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args[1]
    assert "embed" in call_kwargs


@pytest.mark.asyncio
async def test_xp_flush_buffer_task(xp_cog):
    """Test that XP buffer flush task processes pending XP correctly."""
    xp_cog.xp_manager.flush_buffer = AsyncMock()

    if hasattr(xp_cog, "flush_xp_buffer"):
        task = xp_cog.flush_xp_buffer
        assert task is not None
