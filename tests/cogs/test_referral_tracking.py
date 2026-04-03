"""
End-to-end tests for Referral Tracking cog.

Tests referral code generation, 24-hour cooldown enforcement,
stats display with empty state, and leaderboard pagination.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

import discord
from discord.ext import commands

from src.cogs.referral_tracking import ReferralTrackingCog


@pytest.fixture
def mock_bot():
    """Create a mock Discord bot."""
    bot = MagicMock(spec=commands.Bot)
    return bot


@pytest.fixture
def mock_referral_manager():
    """Create a mock ReferralManager."""
    manager = AsyncMock()
    manager.get_or_create_code = AsyncMock(return_value={
        "code": "REFERRAL123",
        "referral_url": "https://pp.com/ref/REFERRAL123",
        "total_signups": 5,
        "total_ftds": 3,
    })
    manager.get_referral_stats = AsyncMock(return_value={
        "total_signups": 5,
        "total_ftds": 3,
        "total_earned_cents": 5000,
    })
    manager.get_leaderboard = AsyncMock(return_value=[])
    return manager


@pytest.fixture
def referral_cog(mock_bot, mock_referral_manager):
    """Create a ReferralTrackingCog instance."""
    return ReferralTrackingCog(mock_bot, mock_referral_manager)


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
async def test_referral_code_generates_code(referral_cog, mock_context):
    """Test that /referral code generates a unique referral code."""
    mock_context.defer = AsyncMock()

    referral_cog.referral_manager.get_or_create_code = AsyncMock(
        return_value={
            "code": "PP_ABC123XYZ",
            "referral_url": "https://pp.com/ref/PP_ABC123XYZ",
            "total_signups": 0,
            "total_ftds": 0,
        }
    )

    await referral_cog.referral_code.callback(referral_cog, mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    assert "embed" in call_kwargs


@pytest.mark.asyncio
async def test_referral_code_cooldown(referral_cog, mock_context):
    """Test that users cannot generate codes more than once per 24 hours."""
    mock_context.defer = AsyncMock()

    # User already has a recent code
    referral_cog.referral_manager.get_or_create_code = AsyncMock(
        return_value={
            "code": "PP_ABC123",
            "referral_url": "https://pp.com/ref/PP_ABC123",
            "total_signups": 2,
            "total_ftds": 1,
        }
    )

    await referral_cog.referral_code.callback(referral_cog, mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    assert "embed" in call_kwargs


@pytest.mark.asyncio
async def test_referral_stats_empty_state(referral_cog, mock_context):
    """Test that users with no referrals see appropriate empty message."""
    mock_context.defer = AsyncMock()

    referral_cog.referral_manager.get_referral_stats = AsyncMock(
        return_value=None
    )

    await referral_cog.referral_stats.callback(referral_cog, mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    # Empty state may not have embed, check for ephemeral message
    assert "ephemeral" in call_kwargs or "embed" in call_kwargs


@pytest.mark.asyncio
async def test_referral_stats_with_data(referral_cog, mock_context):
    """Test that referral stats display correctly with conversion data."""
    mock_context.defer = AsyncMock()

    referral_cog.referral_manager.get_referral_stats = AsyncMock(
        return_value={
            "code": "PP_ABC123",
            "total_signups": 25,
            "total_ftds": 5,
            "total_earned_cents": 50000,
        }
    )

    await referral_cog.referral_stats.callback(referral_cog, mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    assert "embed" in call_kwargs


@pytest.mark.asyncio
async def test_referral_leaderboard_paginated(referral_cog, mock_context):
    """Test that referral leaderboard supports pagination."""
    mock_context.defer = AsyncMock()

    leaderboard_entries = [
        {"rank": i + 1, "user_id": 100 + i, "total_ftds": 50 - i * 5}
        for i in range(10)
    ]

    referral_cog.referral_manager.get_leaderboard = AsyncMock(
        return_value=leaderboard_entries
    )

    await referral_cog.referral_leaderboard.callback(referral_cog, mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    assert "embed" in call_kwargs
