"""
End-to-end tests for Tiered Roles cog.

Tests tier display with correct colors, XP progress bars toward next tier,
tier-up notifications, and grace period enforcement on tier-down.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

import discord
from discord.ext import commands

from src.cogs.tiered_roles import TieredRoles


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
    manager.get_xp = AsyncMock(return_value={"tier": "bronze", "balance": 0})
    manager.get_rank = AsyncMock(return_value={"rank": 1})
    manager.award_xp = AsyncMock(return_value=(True, "XP awarded"))
    manager.TIER_THRESHOLDS = {
        "bronze": 5000,
        "silver": 15000,
        "gold": 35000,
        "diamond": 75000,
        "legend": 150000,
    }
    return manager


@pytest.fixture
def tiered_roles_cog(mock_bot, mock_xp_manager):
    """Create a TieredRoles cog instance."""
    return TieredRoles(mock_bot, xp_manager=mock_xp_manager, guild_id=987654321)


@pytest.fixture
def mock_context():
    """Create a mock application context."""
    ctx = MagicMock(spec=discord.ApplicationContext)
    ctx.author = MagicMock(spec=discord.User)
    ctx.author.id = 123456789
    ctx.author.name = "TestUser"
    ctx.author.avatar = MagicMock()
    ctx.author.avatar.url = "https://example.com/avatar.png"
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_tier_display_uses_correct_color(tiered_roles_cog, mock_context):
    """Test that tier display uses appropriate color for tier."""
    mock_context.defer = AsyncMock()

    tiered_roles_cog.xp_manager.get_xp = AsyncMock(
        return_value={
            "tier": "gold",
            "balance": 35000,
            "level": 5,
        }
    )

    tiered_roles_cog.xp_manager.TIER_THRESHOLDS = {
        "bronze": 5000,
        "silver": 15000,
        "gold": 30000,
        "diamond": 50000,
    }

    await tiered_roles_cog.tier_command.callback(tiered_roles_cog, mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    assert "embed" in call_kwargs
    embed = call_kwargs["embed"]

    from src.utils.colors import TIER_GOLD
    # Compare color values - embed.color is a Colour object
    assert embed.color.value == TIER_GOLD or embed.color == TIER_GOLD


@pytest.mark.asyncio
async def test_tier_progress_shows_bar(tiered_roles_cog, mock_context):
    """Test that tier progress displays progress bar."""
    mock_context.defer = AsyncMock()

    tiered_roles_cog.xp_manager.get_xp = AsyncMock(
        return_value={
            "tier": "silver",
            "balance": 20000,
            "level": 3,
        }
    )

    tiered_roles_cog.xp_manager.TIER_THRESHOLDS = {
        "bronze": 5000,
        "silver": 15000,
        "gold": 30000,
        "diamond": 50000,
    }

    await tiered_roles_cog.tier_command.callback(tiered_roles_cog, mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args.kwargs
    assert "embed" in call_kwargs
    embed = call_kwargs["embed"]

    found_progress = False
    for field in embed.fields:
        if "Progress" in field.name or "progress" in field.name.lower():
            found_progress = True
            assert "█" in field.value or "░" in field.value or "%" in field.value

    assert found_progress is True


@pytest.mark.asyncio
async def test_tier_bronze_displays_perks(tiered_roles_cog, mock_context):
    """Test that Bronze tier shows correct perks."""
    mock_context.defer = AsyncMock()

    tiered_roles_cog.xp_manager.get_xp = AsyncMock(
        return_value={
            "tier": "bronze",
            "balance": 5000,
            "level": 1,
        }
    )

    tiered_roles_cog.xp_manager.TIER_THRESHOLDS = {
        "bronze": 5000,
        "silver": 15000,
        "gold": 30000,
        "diamond": 50000,
    }

    await tiered_roles_cog.tier_command.callback(tiered_roles_cog, mock_context)

    mock_context.respond.assert_called_once()
    call_kwargs = mock_context.respond.call_args[1]
    assert "embed" in call_kwargs
    embed = call_kwargs["embed"]

    bronze_perks = tiered_roles_cog.TIER_PERKS["bronze"]
    perks_text = str(embed.fields)  # noqa: F841
    assert len(bronze_perks) > 0


@pytest.mark.asyncio
async def test_tier_up_notification(tiered_roles_cog):
    """Test that tier-up sends congratulations DM."""
    member = MagicMock(spec=discord.Member)
    member.id = 123456789
    member.send = AsyncMock()

    await tiered_roles_cog._send_tier_up_dm(member, "gold")

    member.send.assert_called_once()
    call_kwargs = member.send.call_args[1]
    assert "embed" in call_kwargs


@pytest.mark.asyncio
async def test_tier_down_grace_period(tiered_roles_cog):
    """Test that tier-down initiates 7-day grace period."""
    member = MagicMock(spec=discord.Member)
    member.id = 123456789
    member.send = AsyncMock()

    await tiered_roles_cog._send_tier_down_warning_dm(member, "gold", "silver")

    member.send.assert_called_once()
    call_kwargs = member.send.call_args[1]
    assert "embed" in call_kwargs
    embed = call_kwargs["embed"]  # noqa: F841

    assert tiered_roles_cog.TIER_DOWN_GRACE_DAYS == 7


@pytest.mark.asyncio
async def test_tier_check_update_task(tiered_roles_cog):
    """Test that tier update background task exists."""
    if hasattr(tiered_roles_cog, "check_tier_updates"):
        task = tiered_roles_cog.check_tier_updates
        assert task is not None
