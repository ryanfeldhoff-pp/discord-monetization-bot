"""
Tests for the tail bot URL detection and deeplink generation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestTailBotURLDetection:
    """Test URL detection in messages."""

    @pytest.mark.asyncio
    async def test_detect_valid_prizepicks_url(self):
        """Test detection of valid PrizePicks URL."""
        from bot.services.tail_bot import TailBotService

        service = TailBotService()

        # Valid URLs
        urls = [
            "https://app.prizepicks.com/board/12345",
            "https://api.prizepicks.com/board/67890",
            "https://prizepicks.com/board/11111",
        ]

        for url in urls:
            assert service.detect_board_url(url) is not None

    @pytest.mark.asyncio
    async def test_detect_invalid_url(self):
        """Test non-detection of invalid URLs."""
        from bot.services.tail_bot import TailBotService

        service = TailBotService()

        invalid_urls = [
            "https://google.com",
            "https://example.com/board/123",
            "not a url",
        ]

        for url in invalid_urls:
            assert service.detect_board_url(url) is None

    @pytest.mark.asyncio
    async def test_extract_board_id(self):
        """Test extraction of board ID from URL."""
        from bot.services.tail_bot import TailBotService

        service = TailBotService()
        board_id = service.extract_board_id(
            "https://app.prizepicks.com/board/12345?some=param"
        )

        assert board_id == "12345"

    @pytest.mark.asyncio
    async def test_extract_board_id_invalid(self):
        """Test board ID extraction failure."""
        from bot.services.tail_bot import TailBotService

        service = TailBotService()
        board_id = service.extract_board_id("https://google.com")

        assert board_id is None


class TestDeepLinkGeneration:
    """Test deeplink generation for different platforms."""

    @pytest.mark.asyncio
    async def test_generate_ios_deeplink(self):
        """Test iOS deeplink generation."""
        from bot.services.tail_bot import TailBotService

        service = TailBotService()
        deeplink = service.generate_deeplink("12345", platform="ios")

        assert deeplink.startswith("prizepicks://")
        assert "12345" in deeplink
        assert "ref=discord" in deeplink

    @pytest.mark.asyncio
    async def test_generate_android_deeplink(self):
        """Test Android deeplink generation."""
        from bot.services.tail_bot import TailBotService

        service = TailBotService()
        deeplink = service.generate_deeplink("12345", platform="android")

        assert "com.prizepicks" in deeplink
        assert "12345" in deeplink

    @pytest.mark.asyncio
    async def test_generate_web_deeplink(self):
        """Test web deeplink generation."""
        from bot.services.tail_bot import TailBotService

        service = TailBotService()
        deeplink = service.generate_deeplink("12345", platform="web")

        assert deeplink.startswith("https://")
        assert "prizepicks.com" in deeplink
        assert "12345" in deeplink

    @pytest.mark.asyncio
    async def test_generate_all_platforms(self):
        """Test generating deeplinks for all platforms."""
        from bot.services.tail_bot import TailBotService

        service = TailBotService()
        board_id = "98765"

        deeplinks = service.generate_deeplinks(board_id)

        assert "ios" in deeplinks
        assert "android" in deeplinks
        assert "web" in deeplinks

        # All should contain board ID
        for platform, link in deeplinks.items():
            assert board_id in link or "board" in link.lower()


class TestQRCodeGeneration:
    """Test QR code generation for deeplinks."""

    @pytest.mark.asyncio
    async def test_generate_qr_code(self):
        """Test QR code generation."""
        from bot.services.tail_bot import TailBotService

        service = TailBotService()
        qr_data = service.generate_qr_code("https://prizepicks.com/board/12345")

        assert qr_data is not None
        assert isinstance(qr_data, bytes)

    @pytest.mark.asyncio
    async def test_qr_code_from_deeplink(self):
        """Test generating QR code from deeplink."""
        from bot.services.tail_bot import TailBotService

        service = TailBotService()
        deeplink = service.generate_deeplink("12345", platform="web")
        qr_data = service.generate_qr_code(deeplink)

        assert qr_data is not None


class TestMessageProcessing:
    """Test message processing and URL extraction."""

    @pytest.mark.asyncio
    async def test_process_message_with_url(self, mock_message):
        """Test processing message with PrizePicks URL."""
        mock_message.content = "Check this board https://app.prizepicks.com/board/12345"

        from bot.services.tail_bot import TailBotService

        service = TailBotService()
        urls = service.find_all_urls(mock_message.content)

        assert len(urls) > 0
        assert any("prizepicks.com" in url for url in urls)

    @pytest.mark.asyncio
    async def test_process_message_no_url(self, mock_message):
        """Test processing message without URL."""
        mock_message.content = "This is a regular message"

        from bot.services.tail_bot import TailBotService

        service = TailBotService()
        urls = service.find_all_urls(mock_message.content)

        assert len(urls) == 0

    @pytest.mark.asyncio
    async def test_process_message_multiple_urls(self, mock_message):
        """Test processing message with multiple URLs."""
        mock_message.content = (
            "Check these boards: https://app.prizepicks.com/board/111 and "
            "https://app.prizepicks.com/board/222"
        )

        from bot.services.tail_bot import TailBotService

        service = TailBotService()
        urls = service.find_all_urls(mock_message.content)

        assert len(urls) >= 2


class TestRateLimiting:
    """Test rate limiting for tail shares."""

    @pytest.mark.asyncio
    async def test_rate_limit_same_board_same_user(self, mock_redis):
        """Test rate limiting duplicate shares."""
        from bot.services.tail_bot import TailBotService

        service = TailBotService(redis=mock_redis)

        # Mock Redis to simulate recent share
        mock_redis.get = AsyncMock(return_value=b"true")

        is_rate_limited = await service.check_rate_limit(
            user_id=123456789, board_id="12345"
        )

        assert is_rate_limited is True

    @pytest.mark.asyncio
    async def test_no_rate_limit_different_board(self, mock_redis):
        """Test no rate limiting for different boards."""
        from bot.services.tail_bot import TailBotService

        service = TailBotService(redis=mock_redis)

        # Mock Redis to simulate no recent share
        mock_redis.get = AsyncMock(return_value=None)

        is_rate_limited = await service.check_rate_limit(
            user_id=123456789, board_id="12345"
        )

        assert is_rate_limited is False


class TestErrorHandling:
    """Test error handling in tail bot."""

    @pytest.mark.asyncio
    async def test_handle_invalid_board_id(self):
        """Test handling of invalid board ID."""
        from bot.services.tail_bot import TailBotService

        service = TailBotService()

        with pytest.raises(ValueError):
            service.generate_deeplink("", platform="web")

    @pytest.mark.asyncio
    async def test_handle_network_error(self, mock_api_client):
        """Test handling of network errors."""
        from bot.services.tail_bot import TailBotService

        service = TailBotService(api_client=mock_api_client)

        # Mock API error
        mock_api_client.get = AsyncMock(side_effect=Exception("Network error"))

        with pytest.raises(Exception):
            await service.fetch_board_data("12345")
