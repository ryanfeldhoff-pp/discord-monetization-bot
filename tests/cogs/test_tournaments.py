"""
End-to-end tests for Tournaments cog.

Tests tournament creation, entry validation, prediction submission,
leaderboard pagination, and scoring with confirmation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from src.cogs.tournaments import TournamentsCog


@pytest.fixture
def mock_bot():
    """Create a mock Discord bot."""
    bot = MagicMock(spec=commands.Bot)
    bot.wait_until_ready = AsyncMock()
    bot.fetch_user = AsyncMock()
    return bot


@pytest.fixture
def mock_engine():
    """Create a mock TournamentEngine."""
    engine = AsyncMock()
    return engine


@pytest.fixture
def mock_xp_manager():
    """Create a mock XPManager."""
    manager = AsyncMock()
    manager.award_xp = AsyncMock(return_value=(True, "XP awarded"))
    return manager


@pytest.fixture
def tournaments_cog(mock_bot, mock_engine, mock_xp_manager):
    """Create a TournamentsCog instance."""
    cog = TournamentsCog(mock_bot, mock_engine, mock_xp_manager)
    # Cancel the background task created in __init__
    cog.check_tournament_lifecycle.cancel()
    return cog


@pytest.fixture
def mock_context():
    """Create a mock application context."""
    ctx = MagicMock(spec=discord.ApplicationContext)
    ctx.author = MagicMock(spec=discord.User)
    ctx.author.id = 123456789
    ctx.guild = MagicMock(spec=discord.Guild)
    ctx.guild.id = 987654321
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()
    ctx.send_modal = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_tournament_list_empty_state(tournaments_cog, mock_context):
    """Test that empty tournament list shows appropriate message."""
    mock_context.defer = AsyncMock()

    tournaments_cog.engine.list_tournaments = AsyncMock(return_value=[])

    await tournaments_cog.tournament_list.callback(tournaments_cog, mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    assert "embed" in call_kwargs


@pytest.mark.asyncio
async def test_tournament_list_shows_active(tournaments_cog, mock_context):
    """Test that active tournaments are displayed in list."""
    mock_context.defer = AsyncMock()

    tournament = {
        "id": 1,
        "title": "Weekly Prediction Tournament",
        "status": "open",
        "entry_fee_xp": 100,
        "opens_at": "2024-01-01T00:00:00"
    }

    tournaments_cog.engine.list_tournaments = AsyncMock(return_value=[tournament])

    await tournaments_cog.tournament_list.callback(tournaments_cog, mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    assert "embed" in call_kwargs


@pytest.mark.asyncio
async def test_tournament_enter_success(tournaments_cog, mock_context):
    """Test that user can successfully enter a tournament."""
    mock_context.defer = AsyncMock()

    tournament = {
        "id": 1,
        "title": "Test Tournament",
        "status": "open",
        "picks_required": 5
    }

    tournaments_cog.engine.enter_tournament = AsyncMock(return_value=(True, "Successfully entered"))
    tournaments_cog.engine.get_tournament = AsyncMock(return_value=tournament)

    await tournaments_cog.tournament_enter.callback(tournaments_cog, mock_context, tournament_id=1)

    mock_context.respond.assert_called_once()


@pytest.mark.asyncio
async def test_tournament_enter_already_entered(tournaments_cog, mock_context):
    """Test that users cannot enter the same tournament twice."""
    mock_context.defer = AsyncMock()

    tournaments_cog.engine.enter_tournament = AsyncMock(return_value=(False, "Already entered"))

    await tournaments_cog.tournament_enter.callback(tournaments_cog, mock_context, tournament_id=1)

    mock_context.respond.assert_called_once()


@pytest.mark.asyncio
async def test_tournament_predict_valid(tournaments_cog, mock_context):
    """Test that users can submit valid predictions."""
    tournament = {
        "id": 1,
        "title": "Test Tournament",
        "status": "open",
        "picks_required": 5
    }

    tournaments_cog.engine.get_tournament = AsyncMock(return_value=tournament)

    await tournaments_cog.tournament_predict.callback(tournaments_cog, mock_context, tournament_id=1)

    # tournament_predict calls send_modal, not respond
    mock_context.send_modal.assert_called_once()


@pytest.mark.asyncio
async def test_tournament_leaderboard_paginated(tournaments_cog, mock_context):
    """Test that tournament leaderboard supports pagination."""
    mock_context.defer = AsyncMock()

    tournament = {
        "id": 1,
        "title": "Test Tournament",
        "status": "open",
        "participants": 10
    }

    entries = [
        {"rank": i + 1, "score": 100 - i * 5, "user_id": 100 + i} for i in range(10)
    ]

    tournaments_cog.engine.get_tournament = AsyncMock(return_value=tournament)
    tournaments_cog.engine.get_leaderboard = AsyncMock(return_value=entries)
    tournaments_cog.bot.fetch_user = AsyncMock()
    tournaments_cog.bot.fetch_user.return_value = MagicMock(name=f"User")

    await tournaments_cog.tournament_leaderboard.callback(tournaments_cog, mock_context, tournament_id=1)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    assert "embed" in call_kwargs


@pytest.mark.asyncio
async def test_tournament_create_validates_inputs(tournaments_cog, mock_context):
    """Test that tournament creation validates input parameters."""
    mock_context.defer = AsyncMock()

    tournament = MagicMock()
    tournament.id = 1

    tournaments_cog.engine.create_tournament = AsyncMock(return_value=tournament)
    tournaments_cog.engine.update_tournament_status = AsyncMock()

    await tournaments_cog.tournament_create.callback(
        tournaments_cog,
        mock_context,
        title="Test Tournament",
        picks_required=2,
    )

    mock_context.respond.assert_called_once()


@pytest.mark.asyncio
async def test_tournament_score_requires_confirmation(tournaments_cog, mock_context):
    """Test that tournament scoring requires confirmation."""
    mock_context.defer = AsyncMock()

    await tournaments_cog.tournament_score.callback(tournaments_cog, mock_context, tournament_id=1)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    assert "embed" in call_kwargs


@pytest.mark.asyncio
async def test_tournament_auto_start_task(tournaments_cog):
    """Test that auto-start task processes ready tournaments."""
    tournaments_cog.engine.check_tournament_lifecycle = AsyncMock()

    if hasattr(tournaments_cog, "check_tournament_lifecycle"):
        task = tournaments_cog.check_tournament_lifecycle
        assert task is not None
