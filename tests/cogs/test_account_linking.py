"""
End-to-end tests for Account Linking cog.

Tests OAuth flow, account linking status, unlinking with confirmation,
and state management for CSRF protection.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import secrets

import discord
from discord.ext import commands

from src.cogs.account_linking import AccountLinkingCog


@pytest.fixture
def mock_bot():
    """Create a mock Discord bot."""
    bot = MagicMock(spec=commands.Bot)
    bot.prizepicks_client = AsyncMock()
    bot.wait_until_ready = AsyncMock()
    bot.analytics = None
    return bot


@pytest.fixture
def account_linking_cog(mock_bot):
    """Create an AccountLinkingCog instance."""
    cog = AccountLinkingCog(mock_bot)
    # Manually set db since cog_load is not called in tests
    cog.db = AsyncMock()
    cog.db.execute = AsyncMock()
    cog.db.add = MagicMock()
    cog.db.delete = MagicMock()
    cog.db.commit = AsyncMock()
    cog.db.get_account_link = AsyncMock(return_value=None)
    cog.db.delete_account_link = AsyncMock()
    cog.db.create_account_link = AsyncMock()
    return cog


@pytest.fixture
def mock_context():
    """Create a mock application context."""
    ctx = MagicMock(spec=discord.ApplicationContext)
    ctx.author = MagicMock(spec=discord.User)
    ctx.author.id = 123456789
    ctx.author.name = "TestUser"
    ctx.guild = MagicMock(spec=discord.Guild)
    ctx.guild.id = 987654321
    ctx.guild.roles = []
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()
    ctx.followup = MagicMock()
    ctx.followup.send = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_link_command_sends_oauth_url(account_linking_cog, mock_context):
    """Test that /link command generates and sends OAuth URL."""
    mock_context.defer = AsyncMock()
    account_linking_cog.db.get_account_link = AsyncMock(return_value=None)

    await account_linking_cog.link_account.callback(account_linking_cog, mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    assert "embed" in call_kwargs or "content" in call_kwargs


@pytest.mark.asyncio
async def test_link_already_linked_state(account_linking_cog, mock_context):
    """Test that /link shows when account is already linked."""
    mock_context.defer = AsyncMock()

    account_link = MagicMock()
    account_link.status = "linked"
    account_link.prizepicks_user_id = "pp_user_123"

    account_linking_cog.db.get_account_link = AsyncMock(return_value=account_link)

    await account_linking_cog.link_account.callback(account_linking_cog, mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    assert "embed" in call_kwargs


@pytest.mark.asyncio
async def test_link_not_linked_state(account_linking_cog, mock_context):
    """Test that /link shows when account is not linked."""
    mock_context.defer = AsyncMock()

    account_linking_cog.db.get_account_link = AsyncMock(return_value=None)

    await account_linking_cog.link_account.callback(account_linking_cog, mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    assert "embed" in call_kwargs


@pytest.mark.asyncio
async def test_unlink_requires_confirmation(account_linking_cog, mock_context):
    """Test that /unlink command shows confirmation prompt."""
    mock_context.defer = AsyncMock()

    account_link = MagicMock()
    account_link.status = "linked"

    account_linking_cog.db.get_account_link = AsyncMock(return_value=account_link)

    # Patch ConfirmView to avoid blocking on wait()
    with patch("src.cogs.account_linking.ConfirmView") as mock_confirm_view:
        mock_view_instance = MagicMock()
        mock_view_instance.wait = AsyncMock()
        mock_view_instance.result = False
        mock_confirm_view.return_value = mock_view_instance

        await account_linking_cog.unlink_account.callback(account_linking_cog, mock_context)

        mock_context.respond.assert_called_once()
        call_kwargs = mock_context.respond.call_args.kwargs
        assert "view" in call_kwargs or "embed" in call_kwargs


@pytest.mark.asyncio
async def test_unlink_confirmed_removes_link(account_linking_cog, mock_context):
    """Test that confirmed unlink removes the account link."""
    account_link = MagicMock()
    account_link.status = "linked"

    account_linking_cog.db.get_account_link = AsyncMock(return_value=account_link)
    account_linking_cog.db.delete_account_link = AsyncMock()
    account_linking_cog.bot.analytics = None

    # Patch ConfirmView and mock a confirmed interaction
    with patch("src.cogs.account_linking.ConfirmView") as mock_confirm_view:
        mock_view_instance = MagicMock()
        mock_view_instance.wait = AsyncMock()
        mock_view_instance.result = True  # User confirmed
        mock_confirm_view.return_value = mock_view_instance

        # Mock guild and author roles
        mock_context.guild.roles = []
        mock_context.author.roles = []
        mock_context.author.remove_roles = AsyncMock()
        mock_context.followup.send = AsyncMock()

        await account_linking_cog.unlink_account.callback(account_linking_cog, mock_context)

        mock_context.respond.assert_called_once()
        # Verify delete was called
        account_linking_cog.db.delete_account_link.assert_called_once_with(mock_context.author.id)


@pytest.mark.asyncio
async def test_link_command_stores_state(account_linking_cog, mock_context):
    """Test that link command stores state for CSRF protection."""
    mock_context.defer = AsyncMock()

    account_linking_cog.db.get_account_link = AsyncMock(return_value=None)
    account_linking_cog.db.add = MagicMock()
    account_linking_cog.db.commit = AsyncMock()

    await account_linking_cog.link_account.callback(account_linking_cog, mock_context)

    # State should be stored in oauth_states dict
    assert len(account_linking_cog.oauth_states) > 0


@pytest.mark.asyncio
async def test_oauth_url_generation(account_linking_cog):
    """Test that OAuth URL is correctly formatted."""
    state = secrets.token_urlsafe(32)
    url = account_linking_cog._generate_oauth_url(state)

    assert url is not None
    assert isinstance(url, str)
    assert "state=" in url or "state" in url
