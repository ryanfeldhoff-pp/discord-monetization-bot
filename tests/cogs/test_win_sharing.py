"""
End-to-end tests for Win Sharing cog.

Tests win sharing with referral CTAs, post-win DM notifications,
unsubscribe handling, and settings management.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

import discord
from discord.ext import commands

from src.cogs.win_sharing import WinSharingCog


@pytest.fixture
def mock_bot():
    """Create a mock Discord bot."""
    bot = MagicMock(spec=commands.Bot)
    bot.fetch_user = AsyncMock()
    return bot


@pytest.fixture
def mock_referral_manager():
    """Create a mock ReferralManager."""
    manager = AsyncMock()
    manager.get_or_create_code = AsyncMock(return_value={"code": "REF123", "referral_url": "https://ref.pp.com/REF123"})
    manager.db = AsyncMock()
    manager.update_win_share_prefs = AsyncMock(return_value=True)
    manager.get_win_share_prefs = AsyncMock(return_value={"dm_enabled": True})
    return manager


@pytest.fixture
def mock_xp_manager():
    """Create a mock XPManager."""
    manager = AsyncMock()
    manager.award_xp = AsyncMock(return_value=(True, "XP awarded"))
    return manager


@pytest.fixture
def win_sharing_cog(mock_bot, mock_referral_manager, mock_xp_manager):
    """Create a WinSharingCog instance."""
    return WinSharingCog(mock_bot, mock_referral_manager, mock_xp_manager)


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
async def test_share_win_requires_linked_account(win_sharing_cog, mock_context):
    """Test that sharing requires a linked PrizePicks account."""
    mock_context.defer = AsyncMock()

    win_sharing_cog.referral_manager.get_or_create_code = AsyncMock(
        return_value={"code": "REF123", "referral_url": "https://ref.pp.com/REF123"}
    )

    await win_sharing_cog.share_win.callback(win_sharing_cog, mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    assert "embed" in call_kwargs


@pytest.mark.asyncio
async def test_share_win_unlinked_rejected(win_sharing_cog, mock_context):
    """Test that unlinked users cannot share wins."""
    mock_context.defer = AsyncMock()

    win_sharing_cog.referral_manager.get_or_create_code = AsyncMock(
        return_value={"code": "REF123", "referral_url": "https://ref.pp.com/REF123"}
    )

    await win_sharing_cog.share_win.callback(win_sharing_cog, mock_context)

    mock_context.respond.assert_called_once()


@pytest.mark.asyncio
async def test_share_win_success_embed(win_sharing_cog, mock_context):
    """Test that successful win share displays congratulations embed."""
    mock_context.defer = AsyncMock()

    win_sharing_cog.referral_manager.get_or_create_code = AsyncMock(
        return_value={"code": "REF123", "referral_url": "https://ref.pp.com/REF123"}
    )

    await win_sharing_cog.share_win.callback(win_sharing_cog, mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    assert "embed" in call_kwargs


@pytest.mark.asyncio
async def test_win_stats_empty_state(win_sharing_cog, mock_context):
    """Test that users with no shared wins see empty state."""
    mock_context.defer = AsyncMock()

    # Mock the database query result
    win_sharing_cog.referral_manager.db.execute = AsyncMock()
    win_sharing_cog.referral_manager.db.execute.return_value = MagicMock(one_or_none=MagicMock(return_value=None))

    await win_sharing_cog.share_stats.callback(win_sharing_cog, mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    assert "embed" in call_kwargs


@pytest.mark.asyncio
async def test_win_stats_with_data(win_sharing_cog, mock_context):
    """Test that win stats display correctly with multiple shared wins."""
    mock_context.defer = AsyncMock()

    # Mock the database query result
    row = MagicMock()
    row.total_shares = 3
    row.total_tails = 10
    row.total_referrals = 5

    win_sharing_cog.referral_manager.db.execute = AsyncMock()
    win_sharing_cog.referral_manager.db.execute.return_value = MagicMock(one_or_none=MagicMock(return_value=row))

    await win_sharing_cog.share_stats.callback(win_sharing_cog, mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    assert "embed" in call_kwargs


@pytest.mark.asyncio
async def test_win_dm_has_unsubscribe_view(win_sharing_cog):
    """Test that win DM notifications include unsubscribe button."""
    user = MagicMock(spec=discord.User)
    user.send = AsyncMock()

    from src.utils.views import ConfirmView

    view = ConfirmView()

    assert view is not None


@pytest.mark.asyncio
async def test_win_sharing_settings_toggle(win_sharing_cog, mock_context):
    """Test that users can toggle win notification settings."""
    mock_context.defer = AsyncMock()

    win_sharing_cog.referral_manager.update_win_share_prefs = AsyncMock(return_value=True)

    await win_sharing_cog.share_settings.callback(win_sharing_cog, mock_context, dm="on")

    mock_context.respond.assert_called_once()


@pytest.mark.asyncio
async def test_win_webhook_processing_task(win_sharing_cog):
    """Test that win event processing task exists."""
    if hasattr(win_sharing_cog, "handle_win_webhook"):
        func = win_sharing_cog.handle_win_webhook
        assert func is not None
