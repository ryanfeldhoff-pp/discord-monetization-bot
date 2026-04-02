"""
Tests for color constants in src/utils/colors.py

Validates that all color codes are valid hex values and properly defined.
"""

from src.utils.colors import (
    PRIZEPICKS_PRIMARY,
    PRIZEPICKS_SECONDARY,
    TIER_BRONZE,
    TIER_SILVER,
    TIER_GOLD,
    TIER_DIAMOND,
    TIER_LEGEND,
    SUCCESS,
    ERROR,
    WARNING,
    INFO,
    NEUTRAL,
    get_tier_color,
)


class TestColorConstants:
    """Test color constant definitions."""

    def test_prizepicks_primary_is_valid_hex(self):
        """Test that PRIZEPICKS_PRIMARY is a valid hex value."""
        assert isinstance(PRIZEPICKS_PRIMARY, int)
        assert PRIZEPICKS_PRIMARY == 0x6C2BD9
        assert 0 <= PRIZEPICKS_PRIMARY <= 0xFFFFFF

    def test_prizepicks_secondary_is_valid_hex(self):
        """Test that PRIZEPICKS_SECONDARY is a valid hex value."""
        assert isinstance(PRIZEPICKS_SECONDARY, int)
        assert PRIZEPICKS_SECONDARY == 0x1A1A2E
        assert 0 <= PRIZEPICKS_SECONDARY <= 0xFFFFFF

    def test_tier_bronze_is_valid_hex(self):
        """Test that TIER_BRONZE is a valid hex value."""
        assert isinstance(TIER_BRONZE, int)
        assert TIER_BRONZE == 0xCD7F32
        assert 0 <= TIER_BRONZE <= 0xFFFFFF

    def test_tier_silver_is_valid_hex(self):
        """Test that TIER_SILVER is a valid hex value."""
        assert isinstance(TIER_SILVER, int)
        assert TIER_SILVER == 0xC0C0C0
        assert 0 <= TIER_SILVER <= 0xFFFFFF

    def test_tier_gold_is_valid_hex(self):
        """Test that TIER_GOLD is a valid hex value."""
        assert isinstance(TIER_GOLD, int)
        assert TIER_GOLD == 0xFFD700
        assert 0 <= TIER_GOLD <= 0xFFFFFF

    def test_tier_diamond_is_valid_hex(self):
        """Test that TIER_DIAMOND is a valid hex value."""
        assert isinstance(TIER_DIAMOND, int)
        assert TIER_DIAMOND == 0x00F0FF
        assert 0 <= TIER_DIAMOND <= 0xFFFFFF

    def test_tier_legend_is_valid_hex(self):
        """Test that TIER_LEGEND is a valid hex value."""
        assert isinstance(TIER_LEGEND, int)
        assert TIER_LEGEND == 0xFF4500
        assert 0 <= TIER_LEGEND <= 0xFFFFFF

    def test_success_color_is_valid_hex(self):
        """Test that SUCCESS color is a valid hex value."""
        assert isinstance(SUCCESS, int)
        assert SUCCESS == 0x2ECC71
        assert 0 <= SUCCESS <= 0xFFFFFF

    def test_error_color_is_valid_hex(self):
        """Test that ERROR color is a valid hex value."""
        assert isinstance(ERROR, int)
        assert ERROR == 0xE74C3C
        assert 0 <= ERROR <= 0xFFFFFF

    def test_warning_color_is_valid_hex(self):
        """Test that WARNING color is a valid hex value."""
        assert isinstance(WARNING, int)
        assert WARNING == 0xF39C12
        assert 0 <= WARNING <= 0xFFFFFF

    def test_info_color_is_valid_hex(self):
        """Test that INFO color is a valid hex value."""
        assert isinstance(INFO, int)
        assert INFO == 0x3498DB
        assert 0 <= INFO <= 0xFFFFFF

    def test_neutral_color_is_valid_hex(self):
        """Test that NEUTRAL color is a valid hex value."""
        assert isinstance(NEUTRAL, int)
        assert NEUTRAL == 0x95A5A6
        assert 0 <= NEUTRAL <= 0xFFFFFF

    def test_semantic_colors_are_valid_hex(self):
        """Test that all semantic colors are valid hex values."""
        colors = {
            "SUCCESS": SUCCESS,
            "ERROR": ERROR,
            "WARNING": WARNING,
            "INFO": INFO,
            "NEUTRAL": NEUTRAL,
        }

        for name, color in colors.items():
            assert isinstance(color, int), f"{name} is not an integer"
            assert 0 <= color <= 0xFFFFFF, f"{name} is out of valid hex range"


class TestTierColors:
    """Test tier color functionality."""

    def test_tier_colors_are_valid_hex(self):
        """Test that all tier colors are valid hex values."""
        colors = {
            "TIER_BRONZE": TIER_BRONZE,
            "TIER_SILVER": TIER_SILVER,
            "TIER_GOLD": TIER_GOLD,
            "TIER_DIAMOND": TIER_DIAMOND,
            "TIER_LEGEND": TIER_LEGEND,
        }

        for name, color in colors.items():
            assert isinstance(color, int), f"{name} is not an integer"
            assert 0 <= color <= 0xFFFFFF, f"{name} is out of valid hex range"

    def test_get_tier_color_bronze(self):
        """Test get_tier_color returns correct color for bronze."""
        assert get_tier_color("bronze") == TIER_BRONZE

    def test_get_tier_color_silver(self):
        """Test get_tier_color returns correct color for silver."""
        assert get_tier_color("silver") == TIER_SILVER

    def test_get_tier_color_gold(self):
        """Test get_tier_color returns correct color for gold."""
        assert get_tier_color("gold") == TIER_GOLD

    def test_get_tier_color_diamond(self):
        """Test get_tier_color returns correct color for diamond."""
        assert get_tier_color("diamond") == TIER_DIAMOND

    def test_get_tier_color_legend(self):
        """Test get_tier_color returns correct color for legend."""
        assert get_tier_color("legend") == TIER_LEGEND

    def test_get_tier_color_case_insensitive(self):
        """Test get_tier_color is case-insensitive."""
        assert get_tier_color("BRONZE") == TIER_BRONZE
        assert get_tier_color("Silver") == TIER_SILVER
        assert get_tier_color("GOLD") == TIER_GOLD

    def test_get_tier_color_invalid_tier_returns_primary(self):
        """Test get_tier_color returns primary color for invalid tier."""
        assert get_tier_color("invalid") == PRIZEPICKS_PRIMARY
        assert get_tier_color("platinum") == PRIZEPICKS_PRIMARY
        assert get_tier_color("") == PRIZEPICKS_PRIMARY
