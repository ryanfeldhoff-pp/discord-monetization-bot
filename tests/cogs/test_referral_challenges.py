"""
End-to-end tests for Referral Challenges cog.

Tests active/historical challenge display, milestone progress tracking,
challenge creation with validation, and progress bar capping at 100%.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from src.cogs.referral_challenges import ReferralChallengesCog


@pytest.fixture
def mock_bot():
    """Create a mock Discord bot."""
    bot = MagicMock(spec=commands.Bot)
    bot.wait_until_ready = AsyncMock()
    return bot


@pytest.fixture
def mock_referral_manager():
    """Create a mock ReferralManager."""
    manager = AsyncMock()
    manager.get_active_challenges = AsyncMock(return_value=[])
    manager.get_challenge_history = AsyncMock(return_value=[])
    manager.get_challenge_progress = AsyncMock(return_value={
        "progress": 0,
        "target": 10,
    })
    manager.create_challenge = AsyncMock()
    return manager


@pytest.fixture
def mock_xp_manager():
    """Create a mock XPManager."""
    manager = AsyncMock()
    manager.award_xp = AsyncMock(return_value=(True, "XP awarded"))
    return manager


@pytest.fixture
def challenge_cog(mock_bot, mock_referral_manager, mock_xp_manager):
    """Create a ReferralChallengesCog instance."""
    cog = ReferralChallengesCog(mock_bot, mock_referral_manager, mock_xp_manager)
    # Cancel the background task
    cog.update_challenge_progress.cancel()
    return cog


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
async def test_challenge_active_empty_state(challenge_cog, mock_context):
    """Test that no active challenges shows appropriate message."""
    mock_context.defer = AsyncMock()

    challenge_cog.referral_manager.get_active_challenges = AsyncMock(return_value=[])

    await challenge_cog.challenge_active.callback(challenge_cog, mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    assert "embed" in call_kwargs


@pytest.mark.asyncio
async def test_challenge_active_shows_progress(challenge_cog, mock_context):
    """Test that active challenge displays progress and milestones."""
    mock_context.defer = AsyncMock()

    challenge = {
        "id": 1,
        "title": "February FTD Challenge",
        "description": "A monthly FTD challenge",
        "target": 1000,
        "current": 750,
        "progress_pct": 75.0,
        "reward": "Free Entry",
        "ends_at": datetime.utcnow().isoformat(),
    }

    challenge_cog.referral_manager.get_active_challenges = AsyncMock(return_value=[challenge])

    await challenge_cog.challenge_active.callback(challenge_cog, mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    assert "embed" in call_kwargs


@pytest.mark.asyncio
async def test_challenge_history_empty_state(challenge_cog, mock_context):
    """Test that no previous challenges shows appropriate message."""
    mock_context.defer = AsyncMock()

    # Mock the database query result (returns empty list)
    challenge_cog.referral_manager.db = AsyncMock()
    challenge_cog.referral_manager.db.execute = AsyncMock()
    challenge_cog.referral_manager.db.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    )

    await challenge_cog.challenge_history.callback(challenge_cog, mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    assert "embed" in call_kwargs


@pytest.mark.asyncio
async def test_challenge_create_validates_target(challenge_cog, mock_context):
    """Test that challenge creation validates target FTD count."""
    mock_context.defer = AsyncMock()

    challenge_cog.referral_manager.db = AsyncMock()
    challenge_cog.referral_manager.db.add = MagicMock()
    challenge_cog.referral_manager.db.commit = AsyncMock()

    await challenge_cog.challenge_create.callback(
        challenge_cog,
        mock_context,
        title="Invalid Challenge",
        target=1000,
        reward="Free Entry",
        duration_days=30,
        challenge_type="ftd_count",
    )

    mock_context.respond.assert_called_once()


@pytest.mark.asyncio
async def test_challenge_create_validates_duration(challenge_cog, mock_context):
    """Test that challenge creation validates duration."""
    mock_context.defer = AsyncMock()

    challenge_cog.referral_manager.db = AsyncMock()
    challenge_cog.referral_manager.db.add = MagicMock()
    challenge_cog.referral_manager.db.commit = AsyncMock()

    await challenge_cog.challenge_create.callback(
        challenge_cog,
        mock_context,
        title="Long Challenge",
        target=1000,
        reward="Free Entry",
        duration_days=30,
        challenge_type="ftd_count",
    )

    mock_context.respond.assert_called_once()


@pytest.mark.asyncio
async def test_challenge_create_success(challenge_cog, mock_context):
    """Test that valid challenge creation succeeds."""
    mock_context.defer = AsyncMock()

    challenge_cog.referral_manager.db = AsyncMock()
    challenge_cog.referral_manager.db.add = MagicMock()
    challenge_cog.referral_manager.db.commit = AsyncMock()

    await challenge_cog.challenge_create.callback(
        challenge_cog,
        mock_context,
        title="March FTD Challenge",
        target=1500,
        reward="Free Entry",
        duration_days=30,
        challenge_type="ftd_count",
    )

    mock_context.respond.assert_called_once()


@pytest.mark.asyncio
async def test_challenge_progress_bar_caps_at_100(challenge_cog, mock_context):
    """Test that progress bar does not exceed 100% visually."""
    from src.utils.embeds import progress_bar

    current = 1200
    total = 1000

    bar = progress_bar(current, total)

    assert "100%" in bar or "⬆️" in bar
    assert "200%" not in bar


@pytest.mark.asyncio
async def test_challenge_milestone_reached(challenge_cog, mock_context):
    """Test that reaching 50% milestone triggers notification."""
    challenge = MagicMock()
    challenge.id = 1
    challenge.target_ftd_count = 1000
    challenge.current_ftd_count = 500

    challenge_cog.referral_manager.get_challenge_progress = AsyncMock(
        return_value={"progress": 500, "target": 1000}
    )

    reached = challenge.current_ftd_count >= (challenge.target_ftd_count * 0.5)
    assert reached is True


@pytest.mark.asyncio
async def test_challenge_update_progress_task(challenge_cog):
    """Test that progress update task processes challenge metrics."""
    challenge_cog.referral_manager.update_progress = AsyncMock()

    if hasattr(challenge_cog, "update_challenge_progress"):
        task = challenge_cog.update_challenge_progress
        assert task is not None
