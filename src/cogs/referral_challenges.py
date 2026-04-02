"""
Referral Challenges Cog

Handles community-wide referral challenges with FTD tracking and rewards.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord.ext import commands, tasks

from src.models.referral_models import ReferralChallenge
from src.services.referral_manager import ReferralManager
from src.services.xp_manager import XPManager

logger = logging.getLogger(__name__)

# PrizePicks brand color
PRIZEPICKS_PURPLE = 0x6C2BD9


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
        starts_at = challenge.get("starts_at")
        ends_at = challenge.get("ends_at")
        reward_config = challenge.get("reward_config", {})

        # Calculate progress
        percentage = min(100, int((current / target * 100) if target > 0 else 0))
        filled = int(percentage / 10)
        progress_bar = "▓" * filled + "░" * (10 - filled)

        embed = discord.Embed(
            title=title,
            description=f"Community referral challenge in progress",
            color=PRIZEPICKS_PURPLE,
            timestamp=datetime.utcnow(),
        )

        # Progress
        embed.add_field(
            name="Progress",
            value=f"{progress_bar} {percentage}%",
            inline=False,
        )

        # Target
        embed.add_field(
            name="Target",
            value=f"**{current:,} / {target:,}** FTDs",
            inline=True,
        )

        # Status
        status_emoji = {
            "active": "🟢",
            "upcoming": "🟡",
            "completed": "✅",
            "failed": "❌",
        }
        embed.add_field(
            name="Status",
            value=f"{status_emoji.get(status, '⚪')} {status.title()}",
            inline=True,
        )

        # Time remaining
        if ends_at:
            time_left = ends_at - datetime.utcnow()
            days = time_left.days
            hours = time_left.seconds // 3600
            time_str = f"{days}d {hours}h remaining"
            embed.add_field(
                name="Time Remaining",
                value=time_str,
                inline=True,
            )

        # Rewards
        if reward_config:
            reward_text = "Rewards:\n"
            if "free_entries" in reward_config:
                reward_text += f"• {reward_config['free_entries']} Free Entries\n"
            if "xp_bonus" in reward_config:
                reward_text += f"• {reward_config['xp_bonus']:,} XP Bonus\n"
            if "special_role" in reward_config:
                reward_text += f"• Special Role Badge\n"

            embed.add_field(
                name="Rewards for Completion",
                value=reward_text.strip(),
                inline=False,
            )

        embed.set_footer(text="PrizePicks Community")

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
        embed = discord.Embed(
            title="🎉 Challenge Complete! 🎉",
            description=f"The community reached the goal for:\n**{challenge.get('title')}**",
            color=discord.Color.green(),
            timestamp=datetime.utcnow(),
        )

        current = challenge.get("current_count", 0)
        target = challenge.get("target_count", 0)

        embed.add_field(
            name="Final Count",
            value=f"**{current:,} / {target:,}** FTDs",
            inline=False,
        )

        reward_config = challenge.get("reward_config", {})
        if reward_config:
            reward_text = "Rewards Distributed:\n"
            if "free_entries" in reward_config:
                reward_text += f"• {reward_config['free_entries']} Free Entries per user\n"
            if "xp_bonus" in reward_config:
                reward_text += f"• {reward_config['xp_bonus']:,} XP Bonus per user\n"

            embed.add_field(
                name="What You Earned",
                value=reward_text.strip(),
                inline=False,
            )

        embed.set_footer(text="PrizePicks Community")

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
        Create a new referral challenge.

        Args:
            ctx: Discord application context
            title: Challenge title
            target: Target FTD count
            reward_type: Type of reward ("entries", "xp", "both")
            days_duration: Duration in days
        """
        await ctx.defer()

        try:
            # Build reward config
            reward_config = {}
            if reward_type in ["entries", "both"]:
                reward_config["free_entries"] = max(5, target // 10)
            if reward_type in ["xp", "both"]:
                reward_config["xp_bonus"] = max(500, target * 50)

            # Create challenge
            now = datetime.utcnow()
            challenge_data = {
                "guild_id": ctx.guild.id,
                "title": title,
                "challenge_type": "ftd_milestone",
                "target_count": target,
                "reward_config_json": json.dumps(reward_config),
                "status": "active",
                "starts_at": now,
                "ends_at": now + timedelta(days=days_duration),
            }

            created = await self.referral_manager.create_challenge(challenge_data)

            if created:
                embed = discord.Embed(
                    title="Challenge Created!",
                    description=f"**{title}** has been set up",
                    color=PRIZEPICKS_PURPLE,
                )
                embed.add_field(
                    name="Target",
                    value=f"{target:,} FTDs",
                    inline=True,
                )
                embed.add_field(
                    name="Duration",
                    value=f"{days_duration} days",
                    inline=True,
                )

                await ctx.respond(embed=embed)
                logger.info(f"Created challenge: {title} in guild {ctx.guild.id}")
            else:
                await ctx.respond(
                    "Failed to create challenge.",
                    ephemeral=True,
                )

        except Exception as e:
            logger.error(f"Error creating challenge: {e}", exc_info=True)
            await ctx.respond(
                "Error creating challenge. Please try again.",
                ephemeral=True,
            )

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
                embed = discord.Embed(
                    title="No Active Challenges",
                    description="Check back soon for exciting referral challenges!",
                    color=PRIZEPICKS_PURPLE,
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
            await ctx.respond(
                "Error retrieving challenges.",
                ephemeral=True,
            )

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
                embed = discord.Embed(
                    title="No Challenge History",
                    description="No completed challenges yet.",
                    color=PRIZEPICKS_PURPLE,
                )
                await ctx.respond(embed=embed)
                return

            embed = discord.Embed(
                title="Challenge History",
                description="Past referral challenges and results",
                color=PRIZEPICKS_PURPLE,
                timestamp=datetime.utcnow(),
            )

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

                embed.add_field(
                    name=f"{status_emoji.get(status, '⚪')} {title}",
                    value=f"{current:,} / {target:,} FTDs",
                    inline=False,
                )

            embed.set_footer(text="PrizePicks Community")
            await ctx.respond(embed=embed)

        except Exception as e:
            logger.error(f"Error showing challenge history: {e}", exc_info=True)
            await ctx.respond(
                "Error retrieving history.",
                ephemeral=True,
            )

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
        Distribute rewards to all linked members.

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

            for idx, member_id in enumerate(linked_members):
                if idx > 0 and idx % batch_size == 0:
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
