"""Tests for the main bot."""

import pytest

from src.bot import MonetizationBot
from config.settings import Settings


@pytest.fixture
def bot_settings():
    """Create test settings."""
    return Settings(token="test_token", prefix="!")


@pytest.fixture
async def bot(bot_settings):
    """Create a test bot instance."""
    bot = MonetizationBot(bot_settings, command_prefix=bot_settings.prefix)
    yield bot
    await bot.close()


@pytest.mark.asyncio
async def test_bot_initialization(bot):
    """Test bot initialization."""
    assert bot.settings.prefix == "!"
    assert bot.settings.debug is False
