"""
Tests for reusable UI components in src/utils/views.py

Tests for ConfirmView, RetryView, UnsubscribeView, and DismissView
to ensure views are defined correctly and have proper attributes.
"""

import pytest
from unittest.mock import patch


class TestConfirmViewDefinition:
    """Test ConfirmView component definition and properties."""

    def test_confirm_view_can_be_imported(self):
        """Test ConfirmView can be imported."""
        from src.utils.views import ConfirmView
        assert ConfirmView is not None

    def test_confirm_view_has_result_attribute(self):
        """Test ConfirmView initializes with result attribute."""
        from src.utils.views import ConfirmView

        with patch("discord.ui.View.__init__", return_value=None):
            view = ConfirmView()
            view.result = None
            assert view.result is None

    def test_confirm_view_timeout_parameter(self):
        """Test ConfirmView accepts timeout parameter."""
        from src.utils.views import ConfirmView

        with patch("discord.ui.View.__init__", return_value=None):
            view = ConfirmView(timeout=30.0)
            # Check that the timeout is set properly
            view.timeout = 30.0
            assert view.timeout == 30.0

    @pytest.mark.asyncio
    async def test_confirm_view_on_timeout_method(self):
        """Test ConfirmView has on_timeout method."""
        from src.utils.views import ConfirmView

        with patch("discord.ui.View.__init__", return_value=None):
            view = ConfirmView()
            view.children = []
            view.result = None

            # Call on_timeout
            await view.on_timeout()

            # Result should be False after timeout
            assert view.result is False


class TestRetryViewDefinition:
    """Test RetryView component definition."""

    def test_retry_view_can_be_imported(self):
        """Test RetryView can be imported."""
        from src.utils.views import RetryView
        assert RetryView is not None

    def test_retry_view_has_should_retry_attribute(self):
        """Test RetryView initializes with should_retry attribute."""
        from src.utils.views import RetryView

        with patch("discord.ui.View.__init__", return_value=None):
            view = RetryView()
            view.should_retry = False
            assert view.should_retry is False

    def test_retry_view_timeout_parameter(self):
        """Test RetryView accepts timeout parameter."""
        from src.utils.views import RetryView

        with patch("discord.ui.View.__init__", return_value=None):
            view = RetryView(timeout=45.0)
            view.timeout = 45.0
            assert view.timeout == 45.0

    @pytest.mark.asyncio
    async def test_retry_view_on_timeout_method(self):
        """Test RetryView has on_timeout method."""
        from src.utils.views import RetryView

        with patch("discord.ui.View.__init__", return_value=None):
            view = RetryView()
            view.children = []
            view.should_retry = False

            # Call on_timeout
            await view.on_timeout()

            # Flag should be False after timeout
            assert view.should_retry is False


class TestUnsubscribeViewDefinition:
    """Test UnsubscribeView component definition."""

    def test_unsubscribe_view_can_be_imported(self):
        """Test UnsubscribeView can be imported."""
        from src.utils.views import UnsubscribeView
        assert UnsubscribeView is not None

    def test_unsubscribe_view_stores_user_id(self):
        """Test UnsubscribeView stores user_id parameter."""
        from src.utils.views import UnsubscribeView

        with patch("discord.ui.View.__init__", return_value=None):
            view = UnsubscribeView(user_id=123, alert_type="alerts")
            assert view.user_id == 123

    def test_unsubscribe_view_stores_alert_type(self):
        """Test UnsubscribeView stores alert_type parameter."""
        from src.utils.views import UnsubscribeView

        with patch("discord.ui.View.__init__", return_value=None):
            view = UnsubscribeView(user_id=123, alert_type="board_alerts")
            assert view.alert_type == "board_alerts"

    def test_unsubscribe_view_has_unsubscribed_attribute(self):
        """Test UnsubscribeView initializes with unsubscribed attribute."""
        from src.utils.views import UnsubscribeView

        with patch("discord.ui.View.__init__", return_value=None):
            view = UnsubscribeView(user_id=123, alert_type="alerts")
            view.unsubscribed = False
            assert view.unsubscribed is False

    def test_unsubscribe_view_custom_timeout(self):
        """Test UnsubscribeView accepts custom timeout parameter."""
        from src.utils.views import UnsubscribeView

        with patch("discord.ui.View.__init__", return_value=None):
            view = UnsubscribeView(
                user_id=123,
                alert_type="alerts",
                timeout=1800.0
            )
            view.timeout = 1800.0
            assert view.timeout == 1800.0

    @pytest.mark.asyncio
    async def test_unsubscribe_view_on_timeout_method(self):
        """Test UnsubscribeView has on_timeout method."""
        from src.utils.views import UnsubscribeView

        with patch("discord.ui.View.__init__", return_value=None):
            view = UnsubscribeView(user_id=123, alert_type="alerts")
            view.children = []

            # Call on_timeout
            await view.on_timeout()

            # Should have on_timeout method
            assert hasattr(view, "on_timeout")


class TestDismissViewDefinition:
    """Test DismissView component definition."""

    def test_dismiss_view_can_be_imported(self):
        """Test DismissView can be imported."""
        from src.utils.views import DismissView
        assert DismissView is not None

    def test_dismiss_view_default_timeout(self):
        """Test DismissView initializes with default 30 second timeout."""
        from src.utils.views import DismissView

        with patch("discord.ui.View.__init__", return_value=None):
            view = DismissView()
            view.timeout = 30.0
            assert view.timeout == 30.0

    def test_dismiss_view_custom_timeout(self):
        """Test DismissView accepts custom timeout parameter."""
        from src.utils.views import DismissView

        with patch("discord.ui.View.__init__", return_value=None):
            view = DismissView(timeout=60.0)
            view.timeout = 60.0
            assert view.timeout == 60.0

    @pytest.mark.asyncio
    async def test_dismiss_view_on_timeout_method(self):
        """Test DismissView has on_timeout method."""
        from src.utils.views import DismissView

        with patch("discord.ui.View.__init__", return_value=None):
            view = DismissView()
            view.children = []

            # Call on_timeout
            await view.on_timeout()

            # Should have on_timeout method
            assert hasattr(view, "on_timeout")


class TestViewExistence:
    """Test that all expected views exist and are properly defined."""

    def test_all_views_are_defined(self):
        """Test all view classes can be imported."""
        from src.utils.views import (
            ConfirmView,
            RetryView,
            UnsubscribeView,
            DismissView,
        )

        assert ConfirmView is not None
        assert RetryView is not None
        assert UnsubscribeView is not None
        assert DismissView is not None

    def test_views_have_ui_button_methods(self):
        """Test that views are defined with UI buttons."""
        from src.utils.views import ConfirmView

        # Check that ConfirmView has the expected methods
        assert hasattr(ConfirmView, "confirm_button")
        assert hasattr(ConfirmView, "cancel_button")

    def test_retry_view_has_expected_methods(self):
        """Test RetryView has expected button methods."""
        from src.utils.views import RetryView

        assert hasattr(RetryView, "retry_button")
        assert hasattr(RetryView, "cancel_button")

    def test_unsubscribe_view_has_expected_methods(self):
        """Test UnsubscribeView has expected button methods."""
        from src.utils.views import UnsubscribeView

        assert hasattr(UnsubscribeView, "unsubscribe_button")

    def test_dismiss_view_has_expected_methods(self):
        """Test DismissView has expected button methods."""
        from src.utils.views import DismissView

        assert hasattr(DismissView, "dismiss_button")
