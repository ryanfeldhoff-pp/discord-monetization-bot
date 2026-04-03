"""
Tests for embed factory functions in src/utils/embeds.py

Validates all embed creation functions produce correctly formatted embeds
with proper colors, fields, and content.
"""


from src.utils.embeds import (
    success_embed,
    error_embed,
    warning_embed,
    info_embed,
    empty_state_embed,
    loading_embed,
    confirmation_embed,
    leaderboard_embed,
    progress_bar,
)
from src.utils.colors import (
    SUCCESS,
    ERROR,
    WARNING,
    INFO,
    NEUTRAL,
    PRIZEPICKS_PRIMARY,
)


class TestSuccessEmbed:
    """Test success_embed factory function."""

    def test_success_embed_has_correct_color(self):
        """Test success embed uses SUCCESS color."""
        embed = success_embed("Test", "Test message")
        assert embed.color.value == SUCCESS

    def test_success_embed_has_title_with_checkmark(self):
        """Test success embed title includes checkmark."""
        embed = success_embed("Success", "Test message")
        assert "✅" in embed.title
        assert "Success" in embed.title

    def test_success_embed_has_description(self):
        """Test success embed includes description."""
        embed = success_embed("Test", "This is a test message")
        assert "This is a test message" in embed.description

    def test_success_embed_has_footer(self):
        """Test success embed has footer."""
        embed = success_embed("Test", "Test message")
        assert embed.footer.text == "PrizePicks Community"

    def test_success_embed_has_timestamp(self):
        """Test success embed includes timestamp."""
        embed = success_embed("Test", "Test message")
        assert embed.timestamp is not None

    def test_success_embed_with_fields(self):
        """Test success embed can include fields."""
        fields = [
            ("Field 1", "Value 1", True),
            ("Field 2", "Value 2", False),
        ]
        embed = success_embed("Test", "Test message", fields=fields)
        assert len(embed.fields) == 2
        assert embed.fields[0].name == "Field 1"
        assert embed.fields[0].value == "Value 1"
        assert embed.fields[0].inline == True
        assert embed.fields[1].name == "Field 2"
        assert embed.fields[1].inline == False

    def test_success_embed_without_fields(self):
        """Test success embed without fields."""
        embed = success_embed("Test", "Test message", fields=None)
        assert len(embed.fields) == 0


class TestErrorEmbed:
    """Test error_embed factory function."""

    def test_error_embed_has_correct_color(self):
        """Test error embed uses ERROR color."""
        embed = error_embed("Error", "Error message")
        assert embed.color.value == ERROR

    def test_error_embed_has_title_with_x(self):
        """Test error embed title includes X mark."""
        embed = error_embed("Failed", "Error message")
        assert "❌" in embed.title
        assert "Failed" in embed.title

    def test_error_embed_has_description(self):
        """Test error embed includes description."""
        embed = error_embed("Error", "This failed")
        assert "This failed" in embed.description

    def test_error_embed_with_recovery_hint(self):
        """Test error embed can include recovery hint."""
        embed = error_embed("Error", "Failed", recovery_hint="Try again later")
        assert len(embed.fields) >= 1
        recovery_field = next(
            (f for f in embed.fields if f.name == "What you can do"), None
        )
        assert recovery_field is not None
        assert "Try again later" in recovery_field.value

    def test_error_embed_with_error_code(self):
        """Test error embed can include error code."""
        embed = error_embed("Error", "Failed", error_code="ERR_001")
        error_field = next(
            (f for f in embed.fields if f.name == "Error Code"), None
        )
        assert error_field is not None
        assert "ERR_001" in error_field.value

    def test_error_embed_with_both_hint_and_code(self):
        """Test error embed can include both hint and code."""
        embed = error_embed(
            "Error",
            "Failed",
            recovery_hint="Try again",
            error_code="ERR_001"
        )
        assert len(embed.fields) == 2

    def test_error_embed_without_optional_fields(self):
        """Test error embed without optional fields."""
        embed = error_embed("Error", "Failed")
        assert len(embed.fields) == 0


class TestWarningEmbed:
    """Test warning_embed factory function."""

    def test_warning_embed_has_correct_color(self):
        """Test warning embed uses WARNING color."""
        embed = warning_embed("Warning", "Warning message")
        assert embed.color.value == WARNING

    def test_warning_embed_has_title_with_symbol(self):
        """Test warning embed title includes warning symbol."""
        embed = warning_embed("Caution", "Warning message")
        assert "⚠️" in embed.title
        assert "Caution" in embed.title

    def test_warning_embed_has_description(self):
        """Test warning embed includes description."""
        embed = warning_embed("Warning", "Be careful")
        assert "Be careful" in embed.description

    def test_warning_embed_has_footer(self):
        """Test warning embed has footer."""
        embed = warning_embed("Warning", "Message")
        assert embed.footer.text == "PrizePicks Community"


class TestInfoEmbed:
    """Test info_embed factory function."""

    def test_info_embed_has_correct_color(self):
        """Test info embed uses INFO color."""
        embed = info_embed("Info", "Info message")
        assert embed.color.value == INFO

    def test_info_embed_has_title_with_symbol(self):
        """Test info embed title includes info symbol."""
        embed = info_embed("About", "Info message")
        assert "ℹ️" in embed.title
        assert "About" in embed.title

    def test_info_embed_has_description(self):
        """Test info embed includes description."""
        embed = info_embed("Info", "Here's some info")
        assert "Here's some info" in embed.description

    def test_info_embed_with_fields(self):
        """Test info embed can include fields."""
        fields = [("Key", "Value", True)]
        embed = info_embed("Info", "Message", fields=fields)
        assert len(embed.fields) == 1

    def test_info_embed_without_fields(self):
        """Test info embed without fields."""
        embed = info_embed("Info", "Message", fields=None)
        assert len(embed.fields) == 0


class TestEmptyStateEmbed:
    """Test empty_state_embed factory function."""

    def test_empty_state_embed_has_correct_color(self):
        """Test empty state embed uses primary color."""
        embed = empty_state_embed("Leaderboard", "No data yet", ["/xp"])
        assert embed.color.value == PRIZEPICKS_PRIMARY

    def test_empty_state_embed_has_mailbox_symbol(self):
        """Test empty state embed title includes mailbox symbol."""
        embed = empty_state_embed("Leaderboard", "No data", [])
        assert "📭" in embed.title
        assert "No Data Yet" in embed.title
        assert "Leaderboard" in embed.title

    def test_empty_state_embed_has_explanation(self):
        """Test empty state embed includes explanation."""
        embed = empty_state_embed("Feature", "This feature is empty", [])
        assert "This feature is empty" in embed.description

    def test_empty_state_embed_has_cta_commands(self):
        """Test empty state embed includes CTA commands."""
        commands = ["/xp", "/leaderboard"]
        embed = empty_state_embed("Leaderboard", "No data", commands)
        cta_field = next(
            (f for f in embed.fields if f.name == "Get Started"), None
        )
        assert cta_field is not None
        for cmd in commands:
            assert f"`{cmd}`" in cta_field.value

    def test_empty_state_embed_with_single_command(self):
        """Test empty state embed with single CTA command."""
        embed = empty_state_embed("Feature", "Empty", ["/start"])
        cta_field = next(
            (f for f in embed.fields if f.name == "Get Started"), None
        )
        assert "`/start`" in cta_field.value


class TestLoadingEmbed:
    """Test loading_embed factory function."""

    def test_loading_embed_has_correct_color(self):
        """Test loading embed uses NEUTRAL color."""
        embed = loading_embed("Loading...")
        assert embed.color.value == NEUTRAL

    def test_loading_embed_has_hourglass_symbol(self):
        """Test loading embed title includes hourglass."""
        embed = loading_embed("Please wait")
        assert "⏳" in embed.title
        assert "Processing..." in embed.title

    def test_loading_embed_has_task_description(self):
        """Test loading embed includes task description."""
        embed = loading_embed("Fetching your data...")
        assert "Fetching your data..." in embed.description


class TestConfirmationEmbed:
    """Test confirmation_embed factory function."""

    def test_confirmation_embed_has_warning_color(self):
        """Test confirmation embed uses WARNING color."""
        embed = confirmation_embed("Delete account", "Your data will be removed")
        assert embed.color.value == WARNING

    def test_confirmation_embed_has_warning_symbol(self):
        """Test confirmation embed title includes warning symbol."""
        embed = confirmation_embed("Action", "Consequence")
        assert "⚠️" in embed.title
        assert "Confirm Action" in embed.title

    def test_confirmation_embed_has_action_description(self):
        """Test confirmation embed includes action description."""
        embed = confirmation_embed("This is the action", "This is the consequence")
        assert "This is the action" in embed.description

    def test_confirmation_embed_has_consequence_field(self):
        """Test confirmation embed includes consequence field."""
        embed = confirmation_embed("Action", "This will happen")
        consequence_field = next(
            (f for f in embed.fields if f.name == "This will:"), None
        )
        assert consequence_field is not None
        assert "This will happen" in consequence_field.value


class TestLeaderboardEmbed:
    """Test leaderboard_embed factory function."""

    def test_leaderboard_embed_has_primary_color(self):
        """Test leaderboard embed uses primary color."""
        embed = leaderboard_embed("XP Leaderboard", [], 1, 1)
        assert embed.color.value == PRIZEPICKS_PRIMARY

    def test_leaderboard_embed_with_entries(self):
        """Test leaderboard embed with entries."""
        entries = [
            {"rank": 1, "username": "Player1", "value": 1000},
            {"rank": 2, "username": "Player2", "value": 900},
            {"rank": 3, "username": "Player3", "value": 800},
        ]
        embed = leaderboard_embed("Leaderboard", entries, 1, 1)
        description = embed.description
        assert "Player1" in description
        # Check for medals by looking at the string format
        assert "🥇" in description or "#1" in description  # Medal for rank 1
        assert "🥈" in description or "#2" in description  # Medal for rank 2
        assert "🥉" in description or "#3" in description  # Medal for rank 3

    def test_leaderboard_embed_with_numbered_ranks(self):
        """Test leaderboard embed with ranks beyond top 3."""
        entries = [
            {"rank": 4, "username": "Player4", "value": 700},
            {"rank": 5, "username": "Player5", "value": 600},
        ]
        embed = leaderboard_embed("Leaderboard", entries, 1, 1)
        description = embed.description
        assert "#4" in description
        assert "#5" in description

    def test_leaderboard_embed_has_pagination_info(self):
        """Test leaderboard embed includes pagination."""
        embed = leaderboard_embed("Leaderboard", [], 2, 5)
        page_field = next(
            (f for f in embed.fields if f.name == "Page"), None
        )
        assert page_field is not None
        assert "2 / 5" in page_field.value

    def test_leaderboard_embed_with_user_rank(self):
        """Test leaderboard embed includes user rank."""
        embed = leaderboard_embed("Leaderboard", [], 1, 1, user_rank=42)
        rank_field = next(
            (f for f in embed.fields if f.name == "Your Rank"), None
        )
        assert rank_field is not None
        assert "#42" in rank_field.value

    def test_leaderboard_embed_without_user_rank(self):
        """Test leaderboard embed without user rank."""
        embed = leaderboard_embed("Leaderboard", [], 1, 1, user_rank=None)
        rank_field = next(
            (f for f in embed.fields if f.name == "Your Rank"), None
        )
        assert rank_field is None

    def test_leaderboard_embed_empty_entries(self):
        """Test leaderboard embed with no entries."""
        embed = leaderboard_embed("Leaderboard", [], 1, 1)
        assert "No data available" in embed.description


class TestProgressBar:
    """Test progress_bar string generation function."""

    def test_progress_bar_zero_percent(self):
        """Test progress bar at 0%."""
        bar = progress_bar(0, 100)
        assert "░░░░░░░░░░" in bar  # All empty
        assert "0%" in bar

    def test_progress_bar_fifty_percent(self):
        """Test progress bar at 50%."""
        bar = progress_bar(50, 100)
        assert "█████░░░░░" in bar  # Half filled
        assert "50%" in bar

    def test_progress_bar_hundred_percent(self):
        """Test progress bar at 100%."""
        bar = progress_bar(100, 100)
        assert "██████████" in bar  # Fully filled
        assert "100%" in bar

    def test_progress_bar_overflow_capped(self):
        """Test progress bar capped at 100% with overflow indicator."""
        bar = progress_bar(150, 100)
        assert "██████████" in bar  # Fully filled
        assert "100%" in bar
        assert "⬆️" in bar  # Overflow indicator

    def test_progress_bar_custom_length(self):
        """Test progress bar with custom length."""
        bar = progress_bar(25, 100, length=20)
        assert len(bar) > 20  # Contains bar plus percentage

    def test_progress_bar_zero_total(self):
        """Test progress bar with zero total."""
        bar = progress_bar(0, 0)
        assert "0%" in bar

    def test_progress_bar_partial_fill(self):
        """Test progress bar with various fill levels."""
        bar_25 = progress_bar(25, 100, length=10)
        bar_75 = progress_bar(75, 100, length=10)
        assert "25%" in bar_25
        assert "75%" in bar_75

    def test_progress_bar_one_fourth(self):
        """Test progress bar at 1/4 filled."""
        bar = progress_bar(25, 100)
        assert "25%" in bar
        # Should have roughly 2-3 filled blocks out of 10
        filled = bar.count("█")
        assert 2 <= filled <= 3

    def test_progress_bar_three_fourths(self):
        """Test progress bar at 3/4 filled."""
        bar = progress_bar(75, 100)
        assert "75%" in bar
        # Should have roughly 7-8 filled blocks out of 10
        filled = bar.count("█")
        assert 7 <= filled <= 8
