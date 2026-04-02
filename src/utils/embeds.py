"""
Embed factory functions for consistent UI across the bot.

Provides helper functions to create embeds with standardized styling,
colors, and formatting to enforce PrizePicks brand guidelines.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import discord

from src.utils.colors import (
    PRIZEPICKS_PRIMARY,
    SUCCESS,
    ERROR,
    WARNING,
    INFO,
    NEUTRAL,
)


def _base_embed(
    title: str,
    description: str = "",
    color: int = PRIZEPICKS_PRIMARY,
) -> discord.Embed:
    """
    Create a base embed with PrizePicks styling.

    Args:
        title: Embed title
        description: Embed description
        color: Embed color (hex as integer)

    Returns:
        discord.Embed: Configured embed
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.utcnow(),
    )
    embed.set_footer(text="PrizePicks Community")
    return embed


def success_embed(
    title: str,
    description: str,
    fields: Optional[List[tuple]] = None,
) -> discord.Embed:
    """
    Create a success embed with green border and checkmark.

    Args:
        title: Embed title (checkmark will be prepended)
        description: Success message (keep under 100 chars)
        fields: Optional list of (name, value, inline) tuples

    Returns:
        discord.Embed: Success-styled embed
    """
    embed = _base_embed(f"✅ {title}", description, SUCCESS)

    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)

    return embed


def error_embed(
    title: str,
    description: str,
    recovery_hint: Optional[str] = None,
    error_code: Optional[str] = None,
) -> discord.Embed:
    """
    Create an error embed with red border and X.

    Args:
        title: Embed title (X will be prepended)
        description: Error message (keep under 100 chars)
        recovery_hint: Optional hint on how to recover
        error_code: Optional error code for support

    Returns:
        discord.Embed: Error-styled embed
    """
    embed = _base_embed(f"❌ {title}", description, ERROR)

    if recovery_hint:
        embed.add_field(
            name="What you can do",
            value=recovery_hint,
            inline=False,
        )

    if error_code:
        embed.add_field(
            name="Error Code",
            value=f"`{error_code}`",
            inline=True,
        )

    return embed


def warning_embed(title: str, description: str) -> discord.Embed:
    """
    Create a warning embed with yellow border.

    Args:
        title: Embed title (warning symbol will be prepended)
        description: Warning message

    Returns:
        discord.Embed: Warning-styled embed
    """
    return _base_embed(f"⚠️ {title}", description, WARNING)


def info_embed(
    title: str,
    description: str,
    fields: Optional[List[tuple]] = None,
) -> discord.Embed:
    """
    Create an info embed with purple border.

    Args:
        title: Embed title
        description: Information message
        fields: Optional list of (name, value, inline) tuples

    Returns:
        discord.Embed: Info-styled embed
    """
    embed = _base_embed(f"ℹ️ {title}", description, INFO)

    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)

    return embed


def empty_state_embed(
    feature_name: str,
    explanation: str,
    cta_commands: List[str],
) -> discord.Embed:
    """
    Create an empty state embed explaining a feature and how to get started.

    Args:
        feature_name: Name of the feature
        explanation: Explanation of what the feature does
        cta_commands: List of commands to get started (e.g., ["/xp", "/leaderboard"])

    Returns:
        discord.Embed: Empty state-styled embed
    """
    embed = _base_embed(
        f"📭 {feature_name} - No Data Yet",
        explanation,
        PRIZEPICKS_PRIMARY,
    )

    commands_text = "\n".join(f"• `{cmd}`" for cmd in cta_commands)
    embed.add_field(
        name="Get Started",
        value=commands_text,
        inline=False,
    )

    return embed


def loading_embed(task_description: str) -> discord.Embed:
    """
    Create a loading embed while processing.

    Args:
        task_description: Description of what's being processed

    Returns:
        discord.Embed: Loading-styled embed
    """
    return _base_embed(
        "⏳ Processing...",
        task_description,
        NEUTRAL,
    )


def confirmation_embed(
    action_description: str,
    consequence: str,
) -> discord.Embed:
    """
    Create a confirmation embed showing what will happen.

    Args:
        action_description: What action the user is about to perform
        consequence: What will happen as a result

    Returns:
        discord.Embed: Confirmation-styled embed
    """
    embed = _base_embed(
        "⚠️ Confirm Action",
        action_description,
        WARNING,
    )

    embed.add_field(
        name="This will:",
        value=consequence,
        inline=False,
    )

    return embed


def leaderboard_embed(
    title: str,
    entries: List[Dict[str, Any]],
    page: int,
    total_pages: int,
    user_rank: Optional[int] = None,
) -> discord.Embed:
    """
    Create a leaderboard embed with pagination info.

    Args:
        title: Leaderboard title (e.g., "Daily XP Leaderboard")
        entries: List of dicts with 'rank', 'username', 'value' keys
        page: Current page number (1-indexed)
        total_pages: Total number of pages
        user_rank: Optional user's rank to highlight

    Returns:
        discord.Embed: Leaderboard-styled embed
    """
    # Build leaderboard text
    lb_text = ""
    for entry in entries:
        rank = entry.get("rank", 0)
        username = entry.get("username", "Unknown")
        value = entry.get("value", 0)

        # Medal for top 3
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")
        lb_text += f"{medal} **{username}**: `{value:,}`\n"

    if not lb_text:
        lb_text = "No data available"

    embed = _base_embed(title, lb_text, PRIZEPICKS_PRIMARY)

    # Add pagination
    embed.add_field(
        name="Page",
        value=f"{page} / {total_pages}",
        inline=True,
    )

    if user_rank:
        embed.add_field(
            name="Your Rank",
            value=f"#{user_rank}",
            inline=True,
        )

    return embed


def progress_bar(
    current: int,
    total: int,
    length: int = 10,
) -> str:
    """
    Create a progress bar string.

    Args:
        current: Current value
        total: Maximum value
        length: Length of progress bar (default 10)

    Returns:
        str: Progress bar like "████████░░ 80%"
    """
    # Clamp to 100% max
    percentage = min(100, int((current / total) * 100) if total > 0 else 0)
    filled = int(percentage / (100 / length))
    empty = length - filled

    bar = "█" * filled + "░" * empty

    # Add overflow indicator if over 100%
    overflow = " ⬆️" if current > total else ""

    return f"{bar} {percentage}%{overflow}"
