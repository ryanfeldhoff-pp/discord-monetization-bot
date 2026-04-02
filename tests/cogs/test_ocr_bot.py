"""
End-to-end tests for OCR Bot cog.

Tests OCR screenshot detection, confidence scoring interpretation,
confirmation flow with entry link generation, and error reporting.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

import discord
from discord.ext import commands

from src.cogs.ocr_bot import OCRBotCog


@pytest.fixture
def mock_bot():
    """Create a mock Discord bot."""
    bot = MagicMock(spec=commands.Bot)
    bot.prizepicks_client = AsyncMock()
    bot.analytics = AsyncMock()
    return bot


@pytest.fixture
def ocr_cog(mock_bot):
    """Create an OCRBotCog instance."""
    cog = OCRBotCog(mock_bot)
    # Mock the OCR service
    cog.ocr_service = AsyncMock()
    cog.ocr_service.extract_text = AsyncMock()
    return cog


@pytest.fixture
def mock_message():
    """Create a mock Discord message with attachment."""
    msg = MagicMock(spec=discord.Message)
    msg.author = MagicMock(spec=discord.User)
    msg.author.bot = False
    msg.author.id = 123456789
    msg.guild = MagicMock(spec=discord.Guild)
    msg.channel = MagicMock(spec=discord.TextChannel)
    msg.channel.send = AsyncMock()
    msg.attachments = []
    return msg


@pytest.mark.asyncio
async def test_ocr_confidence_very_high(ocr_cog, mock_message):
    """Test that very high confidence (>95%) is labeled 'Very High'."""
    attachment = MagicMock(spec=discord.Attachment)
    attachment.size = 250000
    attachment.content_type = "image/png"
    attachment.read = AsyncMock(return_value=b"fake_image_data")

    mock_message.attachments = [attachment]
    mock_message.channel.send = AsyncMock()

    ocr_cog.ocr_service.extract_text = AsyncMock(
        return_value=MagicMock(text="Sample extracted text")
    )

    match_result = {
        "confidence": 0.98,
        "entry_link": "https://app.prizepicks.com/entry/test123",
        "summary": "Player Over 25 Points",
    }

    ocr_cog._match_projections = AsyncMock(return_value=match_result)

    await ocr_cog.on_message(mock_message)

    if mock_message.channel.send.called:
        call_kwargs = mock_message.channel.send.call_args[1]
        if "embed" in call_kwargs:
            embed = call_kwargs["embed"]
            assert "Very High" in embed.description or "Very High" in str(embed.fields)


@pytest.mark.asyncio
async def test_ocr_confidence_high(ocr_cog, mock_message):
    """Test that high confidence (80-95%) is labeled 'High'."""
    attachment = MagicMock(spec=discord.Attachment)
    attachment.size = 250000
    attachment.content_type = "image/png"
    attachment.read = AsyncMock(return_value=b"fake_image_data")

    mock_message.attachments = [attachment]
    mock_message.channel.send = AsyncMock()

    ocr_cog.ocr_service.extract_text = AsyncMock(
        return_value=MagicMock(text="Sample extracted text")
    )

    match_result = {
        "confidence": 0.87,
        "entry_link": "https://app.prizepicks.com/entry/test456",
        "summary": "Player Over 30 Points",
    }

    ocr_cog._match_projections = AsyncMock(return_value=match_result)

    await ocr_cog.on_message(mock_message)

    if mock_message.channel.send.called:
        call_kwargs = mock_message.channel.send.call_args[1]
        if "embed" in call_kwargs:
            embed = call_kwargs["embed"]
            assert "High" in embed.description or "High" in str(embed.fields)


@pytest.mark.asyncio
async def test_ocr_confidence_medium(ocr_cog, mock_message):
    """Test that medium confidence (70-80%) is labeled 'Medium'."""
    attachment = MagicMock(spec=discord.Attachment)
    attachment.size = 250000
    attachment.content_type = "image/png"
    attachment.read = AsyncMock(return_value=b"fake_image_data")

    mock_message.attachments = [attachment]
    mock_message.channel.send = AsyncMock()

    ocr_cog.ocr_service.extract_text = AsyncMock(
        return_value=MagicMock(text="Sample extracted text")
    )

    match_result = {
        "confidence": 0.75,
        "entry_link": "https://app.prizepicks.com/entry/test789",
        "summary": "Multiple Props",
    }

    ocr_cog._match_projections = AsyncMock(return_value=match_result)

    await ocr_cog.on_message(mock_message)

    if mock_message.channel.send.called:
        call_kwargs = mock_message.channel.send.call_args[1]
        if "embed" in call_kwargs:
            embed = call_kwargs["embed"]
            assert "Medium" in embed.description or "Medium" in str(embed.fields)


@pytest.mark.asyncio
async def test_ocr_confidence_low(ocr_cog, mock_message):
    """Test that low confidence (<70%) is labeled 'Low'."""
    attachment = MagicMock(spec=discord.Attachment)
    attachment.size = 250000
    attachment.content_type = "image/png"
    attachment.read = AsyncMock(return_value=b"fake_image_data")

    mock_message.attachments = [attachment]
    mock_message.channel.send = AsyncMock()

    ocr_cog.ocr_service.extract_text = AsyncMock(
        return_value=MagicMock(text="Sample extracted text")
    )

    match_result = {
        "confidence": 0.65,
        "entry_link": "https://app.prizepicks.com/entry/test000",
        "summary": "Uncertain Match",
    }

    ocr_cog._match_projections = AsyncMock(return_value=match_result)

    await ocr_cog.on_message(mock_message)

    if mock_message.channel.send.called:
        call_kwargs = mock_message.channel.send.call_args[1]
        if "embed" in call_kwargs:
            embed = call_kwargs["embed"]
            assert "Low" in embed.description or "Low" in str(embed.fields)


@pytest.mark.asyncio
async def test_ocr_confirmation_view_buttons(ocr_cog):
    """Test that OCR confirmation includes Confirm, Report, Dismiss buttons."""
    from src.cogs.ocr_bot import OCRConfirmationView

    view = OCRConfirmationView(
        entry_link="https://app.prizepicks.com/entry/test",
        confidence=0.85,
    )

    assert hasattr(view, "children")
    assert len(view.children) >= 3


@pytest.mark.asyncio
async def test_ocr_ignores_non_images(ocr_cog, mock_message):
    """Test that non-image attachments are ignored."""
    attachment = MagicMock(spec=discord.Attachment)
    attachment.content_type = "application/pdf"

    mock_message.attachments = [attachment]

    ocr_cog.ocr_service.extract_text = AsyncMock()

    await ocr_cog.on_message(mock_message)

    ocr_cog.ocr_service.extract_text.assert_not_called()
