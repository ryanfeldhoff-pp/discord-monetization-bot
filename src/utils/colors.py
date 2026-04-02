"""
Centralized color constants for Discord embeds and UI elements.

Defines PrizePicks brand colors, tier colors, and semantic colors used
throughout the bot's UI.
"""

# PrizePicks brand colors
PRIZEPICKS_PRIMARY = 0x6C2BD9  # PrizePicks Purple
PRIZEPICKS_SECONDARY = 0x1A1A2E  # Dark background

# Tier colors for XP/progression system
TIER_BRONZE = 0xCD7F32  # Bronze
TIER_SILVER = 0xC0C0C0  # Silver
TIER_GOLD = 0xFFD700  # Gold
TIER_DIAMOND = 0x00F0FF  # Diamond/Cyan
TIER_LEGEND = 0xFF4500  # Legend/Orange-Red

# Semantic colors
SUCCESS = 0x2ECC71  # Green
ERROR = 0xE74C3C  # Red
WARNING = 0xF39C12  # Orange
INFO = 0x3498DB  # Blue
NEUTRAL = 0x95A5A6  # Gray


def get_tier_color(tier: str) -> int:
    """
    Get the color code for a given tier name.

    Args:
        tier: Tier name ("bronze", "silver", "gold", "diamond", "legend")

    Returns:
        int: Color code (hex as integer)
    """
    tier_map = {
        "bronze": TIER_BRONZE,
        "silver": TIER_SILVER,
        "gold": TIER_GOLD,
        "diamond": TIER_DIAMOND,
        "legend": TIER_LEGEND,
    }
    return tier_map.get(tier.lower(), PRIZEPICKS_PRIMARY)
