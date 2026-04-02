"""
Referral Challenges Cog

Handles community-wide referral challenges with FTD tracking and rewards.
"""

import logging
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord.ext import commands, tasks

from src.models.referral_models import ReferralChallenge
from src.services.referral_manager import ReferralManager
from src.services.xp_manager import XPManager
from src.utils.colors import PRIZEPICKS_PRIMARY, SUCCESS, ERROR, WARNING
from src.utils.embeds import (
    success_embed,
    error_embed,
    info_embed,
    empty_state_embed,
    loading_embed,
    progress_bar,
)
from src.utils.validation import validate_positive_int, validate_range
from src.utils.error_handler import ValidationError

logger = logging.getLogger(__name__)


class ChallengeProgressEmbed:
    """Helper class to generate challenge progress embeds."""

    @staticmethod
    def create_progress_embed(
        challenge: dict,
        guild_id: int,
    ) -> discord.Embed:
        """
        Create challenge progress embed with progress bar.

        Args:
            challenge: Challenge data dict
            guild_id: Guild ID for context

        Returns:
            discord.Embed: Formatted embed
        """
        title = challenge.get("title", "Referral Challenge")
        current = challenge.get("current_count", 0)
        target = challenge.get("target_count", 0)
        status = challenge.get("status", "active")
        ends_at = challenge.get("ends_at")
        reward_config = challenge.get("reward_config", {})

        # Calculate progress bar with overflow indicator
        bar = progress_bar(current, target, length=10)

        # Status
        status_emoji = {
            "active": "🟢",
            "upcoming": "🟡",
            "completed": "✅",
            "failed": "❌",
        }

        # Time remaining
        time_str = ""
        if ends_at:
            time_left = ends_at - datetime.utcnow()
            if time_left.total_seconds() > 0:
                days = time_left.days
                hours = time_left.seconds // 3600
                time_str = f"{days}d {hours}h remaining"
            else:
                time_str = "Challenge ended"

        # Rewards
        reward_text = "Rewards:\n"
        if reward_config:
            if "free_entries" in reward_config:
                reward_text += f"• {reward_config['free_entries']} Free Entries\n"
            if "xp_bonus" in reward_config:
                reward_text += f"• {reward_config['xp_bonus']:,} XP Bonus\n"
            if "special_role" in reward_config:
                reward_text += f"• Special Role Badge\n"
        else:
            reward_text = "TBD"

        embed = info_embed(
            title,
            "Community referral challenge in progress",
            fields=[
                ("Progress", bar, False),
                ("Target", f"**{current:,} / {target:,}** FTDs", True),
                ("Status", f"{status_emoji.get(status, '⚪')} {status.title()}", True),
                ("Time Remaining", time_str or "N/A", True),
                ("Rewards for Completion", reward_text.strip(), False),
            ],
        )

        return embed


class ChallengeCompletedEmbed:
    """Helper class for challenge completion embeds."""

    @staticmethod
    def create_completed_embed(challenge: dict) -> discord.Embed:
        """
        Create celebration embed for completed challenge.

        Args:
            challenge: Challenge data dict

        Returns:
            discord.Embed: Formatted embed
        """
        current = challenge.get("current_count", 0)
        target = challenge.get("target_count", 0)

        reward_config = challenge.get("reward_config", {})
        reward_text = "Rewards Distributed:\n"
        if reward_config:
            if "free_entries" in reward_config:
                reward_text += f"• {reward_config['free_entries']} Free Entries per user\n"
            if "xp_bonus" in reward_config:
                reward_text += f"• {reward_config['xp_bonus']:,} XP Bonus per user\n"
        else:
            reward_text = "All participants rewarded!"

        embed = success_embed(
            "Challenge Complete!",
            f"The community reached the goal for: **{challenge.get('title')}**",
            fields=[
                ("Final Count", f"**{current:,} / {target:,}** FTDs", False),
                ("What You Earned", reward_text.strip(), False),
            ],
        )

        return embed


class ReferralChallengesCog(commands.Cog):
    """
    Community-wide referral challenges cog.

    Features:
    - View active and past challenges
    - Real-time FTD progress tracking
    - Automatic milestone announcements
    - Reward distribution
    """

    def __init__(
        self,
        bot: commands.Bot,
        referral_manager: ReferralManager,
        xp_manager: XPManager,
    ):
        """
        Initialize Referral Challenges cog.

        Args:
            bot: Discord bot instance
            referral_manager: ReferralManager service instance
            xp_manager: XPManager service instance
        """
        self.bot = bot
        self.referral_manager = referral_manager
        self.xp_manager = xp_manager

        self.update_challenge_progress.start()
        self.check_milestones.start()

    def cog_unload(self) -> None:
        """Clean up background tasks."""
        self.update_challenge_progress.cancel()
        self.check_milestones.cancel()

    @commands.slash_command(
        name="challenge",
        description="View and manage referral challenges",
    )
    @discord.option(
        name="action",
        description="What to do",
        choices=["active", "history", "create"],
        default="active",
    )
    async def challenge_command(
        self,
        ctx: discord.ApplicationContext,
        action: str = "active",
    ) -> None:
        """
        Manage referral challenges.

        Args:
            ctx: Discord application context
            action: Subcommand ("active", "history", or "create")
        """
        await ctx.defer()

        try:
            if action == "active":
                await self._show_active_challenges(ctx)
            elif action == "history":
                await self._show_challenge_history(ctx)
            elif action == "create":
                # Admin only - delegate to admin command
                await ctx.respond(
                    "Use `/challenge_create` to create new challenges (admin only).",
                    ephemeral=True,
                )
            else:
                await ctx.respond(
                    "Invalid action.",
                    ephemeral=True,
                )

        except Exception as e:
            logger.error(f"Error in challenge command: {e}", exc_info=True)
            await ctx.respond(
                "An error occurred. Please try again later.",
                ephemeral=True,
            )

    @commands.slash_command(
        name="challenge_create",
        description="Create a new referral challenge (admin only)",
    )
    @discord.default_member_permissions(manage_messages=True)
    async def challenge_create_command(
        self,
        ctx: discord.ApplicationContext,
        title: str,
        target: int,
        reward_type: str,
        days_duration: int = 7,
    ) -> None:
        """
        Create a new referral challenge with validation.

        Args:
            ctx: Discord application context
            title: Challenge title
            target: Target FTD count
            reward_type: Type of reward ("entries", "xp", "both")
            days_duration: Duration in days
        """
        await ctx.defer()

        try:
            # Validate inputs
            if not title or not title.strip():
                embed = error_embed(
                    "Invalid Title",
                    "Challenge title cannot be empty",
                    recovery_hint="Provide a descriptive challenge title",
                    error_code="INVALID_TITLE",
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            parsed_target, target_error = validate_positive_int(str(target), "Target FTDs")
            if target_error:
                embed = error_embed(
                    "Invalid Target",
                    target_error,
                    recovery_hint="Target must be a positive number",
                    error_code="INVALID_TARGET",
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            is_valid, duration_error = validate_range(
                days_duration, 1, 365, "Duration"
            )
            if not is_valid:
                embed = error_embed(
                    "Invalid Duration",
                    duration_error,
                    recovery_hint="Duration must be between 1 and 365 days",
                    error_code="INVALID_DURATION",
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            # Build reward config
            reward_config = {}
            if reward_type in ["entries", "both"]:
                reward_config["free_entries"] = max(5, parsed_target // 10)
            if reward_type in ["xp", "both"]:
                reward_config["xp_bonus"] = max(500, parsed_target * 50)

            # Create challenge
            now = datetime.utcnow()
            challenge_data = {
                "guild_id": ctx.guild.id,
                "title": title,
                "challenge_type": "ftd_milestone",
                "target_count": parsed_target,
                "reward_config_json": json.dumps(reward_config),
                "status": "active",
                "starts_at": now,
                "ends_at": now + timedelta(days=days_duration),
            }

            created = await self.referral_manager.create_challenge(challenge_data)

            if created:
                embed = success_embed(
                    "Challenge Created!",
                    f"**{title}** has been set up",
                    fields=[
                        ("Target", f"{parsed_target:,} FTDs", True),
                        ("Duration", f"{days_duration} days", True),
                        ("Rewards", ", ".join(k for k in reward_config.keys()), False),
                    ],
                )
                await ctx.respond(embed=embed)
                logger.info(f"Created challenge: {title} in guild {ctx.guild.id}")
            else:
                embed = error_embed(
                    "Creation Failed",
                    "Could not create the challenge.",
                    recovery_hint="Check your input and try again",
                    error_code="CHALLENGE_CREATE_FAILED",
                )
                await ctx.respond(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error creating challenge: {e}", exc_info=True)
            embed = error_embed(
                "Error",
                "An unexpected error occurred while creating the challenge.",
                recovery_hint="Please try again in a moment",
                error_code="CHALLENGE_CREATE_ERROR",
            )
            await ctx.respond(embed=embed, ephemeral=True)

    async def _show_active_challenges(
        self,
        ctx: discord.ApplicationContext,
    ) -> None:
        """
        Show currently active challenges.

        Args:
            ctx: Discord application context
        """
        try:
            challenges = await self.referral_manager.get_active_challenges(
                guild_id=ctx.guild.id
            )

            if not challenges:
                embed = empty_state_embed(
                    "Challenges",
                    "No active referral challenges right now.",
                    ["/challenge active", "/challenge history"],
                )
                await ctx.respond(embed=embed)
                return

            # Show up to 5 active challenges
            for challenge in challenges[:5]:
                embed = ChallengeProgressEmbed.create_progress_embed(
                    challenge,
                    ctx.guild.id,
                )
                await ctx.send(embed=embed)

            logger.info(
                f"Displayed {len(challenges[:5])} active challenges "
                f"for guild {ctx.guild.id}"
            )

        except Exception as e:
            logger.error(f"Error showing active challenges: {e}", exc_info=True)
            embed = error_embed(
                "Error",
                "Could not retrieve challenges.",
                recovery_hint="Please try again in a moment",
                error_code="CHALLENGES_RETRIEVAL_ERROR",
            )
            await ctx.respond(embed=embed, ephemeral=True)

    async def _show_challenge_history(
        self,
        ctx: discord.ApplicationContext,
    ) -> None:
        """
        Show past challenges and results.

        Args:
            ctx: Discord application context
        """
        try:
            challenges = await self.referral_manager.get_past_challenges(
                guild_id=ctx.guild.id,
                limit=10,
            )

            if not challenges:
                embed = empty_state_embed(
                    "Challenge History",
                    "No completed challenges yet.",
                    ["/challenge active", "/challenge_create"],
                )
                await ctx.respond(embed=embed)
                return

            history_text = ""
            for challenge in challenges[:10]:
                title = challenge.get("title", "Challenge")
                status = challenge.get("status", "unknown")
                current = challenge.get("current_count", 0)
                target = challenge.get("target_count", 0)

                status_emoji = {
                    "completed": "✅",
                    "failed": "❌",
                    "active": "🟢",
                }

                history_text += (
                    f"{status_emoji.get(status, '⚪')} **{title}**\n"
                    f"{current:,} / {target:,} FTDs\n\n"
                )

            embed = info_embed(
                "Challenge History",
                "Past referral challenges and results",
                fields=[
                    ("Past Challenges", history_text.strip(), False),
                ],
            )

            await ctx.respond(embed=embed)

        except Exception as e:
            logger.error(f"Error showing challenge history: {e}", exc_info=True)
            embed = error_embed(
                "Error",
                "Could not retrieve challenge history.",
                recovery_hint="Please try again in a moment",
                error_code="HISTORY_RETRIEVAL_ERROR",
            )
            await ctx.respond(embed=embed, ephemeral=True)

    @tasks.loop(minutes=10)
    async def update_challenge_progress(self) -> None:
        """
        Update FTD counts for active challenges every 10 minutes.

        Queries current FTD counts and updates challenge progress in database.
        """
        try:
            challenges = await self.referral_manager.get_all_active_challenges()

            for challenge in challenges:
                # Get current FTD count
                ftd_count = await self.referral_manager.get_challenge_ftd_count(
                    challenge_id=challenge.get("id")
                )

                # Update challenge
                await self.referral_manager.update_challenge_progress(
                    challenge_id=challenge.get("id"),
                    new_count=ftd_count,
                )

            if challenges:
                logger.debug(f"Updated progress for {len(challenges)} challenges")

        except Exception as e:
            logger.error(f"Error updating challenge progress: {e}", exc_info=True)

    @update_challenge_progress.before_loop
    async def before_update_progress(self) -> None:
        """Wait for bot to be ready before starting task."""
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=10)
    async def check_milestones(self) -> None:
        """
        Check if any challenges just hit their target milestone.

        When milestone is hit:
        1. Announce in channel
        2. Distribute rewards to all linked members
        """
        try:
            challenges = await self.referral_manager.get_challenges_at_milestone()

            for challenge in challenges:
                # Mark as completed
                await self.referral_manager.mark_challenge_completed(
                    challenge_id=challenge.get("id")
                )

                # Announce
                guild_id = challenge.get("guild_id")
                guild = self.bot.get_guild(guild_id)
                if guild:
                    # Find general or announcements channel
                    channel = discord.utils.find(
                        lambda c: c.name in ["general", "announcements"],
                        guild.text_channels,
                    )
                    if channel:
                        embed = ChallengeCompletedEmbed.create_completed_embed(
                            challenge
                        )
                        await channel.send(embed=embed)

                # Distribute rewards (rate limited to 500 users/min)
                reward_config = challenge.get("reward_config", {})
                await self._distribute_rewards(guild_id, reward_config)

                logger.info(
                    f"Challenge {challenge.get('id')} hit milestone "
                    f"and rewards were distributed"
                )

        except Exception as e:
            logger.error(f"Error checking milestones: {e}", exc_info=True)

    @check_milestones.before_loop
    async def before_check_milestones(self) -> None:
        """Wait for bot to be ready before starting task."""
        await self.bot.wait_until_ready()

    async def _distribute_rewards(
        self,
        guild_id: int,
        reward_config: dict,
    ) -> None:
        """
        Distribute rewards to all linked members with progress updates.

        Rate limited at 500 users/minute to avoid API overload.

        Args:
            guild_id: Guild ID
            reward_config: Reward configuration dict
        """
        try:
            # Get all linked members
            linked_members = await self.referral_manager.get_linked_members(guild_id)

            if not linked_members:
                return

            # Distribute rewards
            xp_bonus = reward_config.get("xp_bonus", 0)
            free_entries = reward_config.get("free_entries", 0)

            # Rate limit: 500 users per minute
            batch_size = 500
            delay_per_batch = 60  # seconds
            total_members = len(linked_members)

            # Try to find a guild channel to post progress updates
            guild = self.bot.get_guild(guild_id)
            progress_channel = None
            if guild:
                progress_channel = discord.utils.find(
                    lambda c: c.name in ["general", "announcements"],
                    guild.text_channels,
                )

            for idx, member_id in enumerate(linked_members):
                if idx > 0 and idx % batch_size == 0:
                    # Post progress update
                    if progress_channel:
                        progress = int((idx / total_members) * 100)
                        embed = loading_embed(
                            f"Distributing rewards... {idx}/{total_members} ({progress}%)"
                        )
                        await progress_channel.send(embed=embed)

                    # Wait before next batch
                    await asyncio.sleep(delay_per_batch)

                # Award XP if applicable
                if xp_bonus > 0:
                    await self.xp_manager.award_xp(
                        user_id=member_id,
                        amount=xp_bonus,
                        source="challenge_reward",
                        metadata={
                            "guild_id": guild_id,
                            "challenge_id": guild_id,
                        },
                    )

            logger.info(
                f"Distributed rewards to {len(linked_members)} users in guild {guild_id}"
            )

        except Exception as e:
            logger.error(f"Error distributing rewards: {e}", exc_info=True)


async def setup(bot: commands.Bot) -> None:
    """Load the cog."""
    referral_manager = bot.referral_manager
    xp_manager = bot.xp_manager
    await bot.add_cog(
        ReferralChallengesCog(bot, referral_manager, xp_manager)
    )
