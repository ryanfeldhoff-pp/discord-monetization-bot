"""
Referral Challenges Cog (Pillar 4)

Community-wide challenges with progress bars and group rewards.
E.g., "500 Discord FTDs this month → everyone gets a free entry!"
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord.ext import commands, tasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.referral_manager import ReferralManager
from src.services.xp_manager import XPManager

logger = logging.getLogger(__name__)


class ReferralChallengesCog(commands.Cog):
    """
    Community challenges cog for group referral goals.

    Features:
    - /challenge active — View active challenges with progress bar
    - /challenge history — Past challenges
    - /challenge create — Create challenge (admin)
    - Background task: update progress bar message every 15 minutes
    """

    def __init__(
        self,
        bot: commands.Bot,
        referral_manager: ReferralManager,
        xp_manager: XPManager,
    ):
        self.bot = bot
        self.referral_manager = referral_manager
        self.xp_manager = xp_manager
        self.update_challenge_progress.start()

    def cog_unload(self):
        self.update_challenge_progress.cancel()

    challenge_group = discord.SlashCommandGroup("challenge", "Community challenges")

    @challenge_group.command(name="active", description="View active challenges")
    async def challenge_active(self, ctx: discord.ApplicationContext) -> None:
        """Show active community challenges with progress bars."""
        await ctx.defer()

        try:
            challenges = await self.referral_manager.get_active_challenges()

            embed = discord.Embed(
                title="🎯 Active Community Challenges",
                color=0x8B5CF6,
            )

            if challenges:
                for ch in challenges:
                    pct = ch["progress_pct"]
                    bar_filled = int(pct / 5)
                    bar = "█" * bar_filled + "░" * (20 - bar_filled)

                    embed.add_field(
                        name=f"🎯 {ch['title']}",
                        value=(
                            f"{ch.get('description', '')}\n"
                            f"`{bar}` **{pct:.1f}%**\n"
                            f"Progress: **{ch['current']:,}** / {ch['target']:,}\n"
                            f"Reward: {ch['reward']}\n"
                            f"Ends: <t:{int(datetime.fromisoformat(ch['ends_at']).timestamp())}:R>"
                        ),
                        inline=False,
                    )
            else:
                embed.description = "No active challenges right now. Check back soon!"

            await ctx.respond(embed=embed)

        except Exception as e:
            logger.error(f"Error showing active challenges: {e}")
            await ctx.respond("Failed to load challenges.", ephemeral=True)

    @challenge_group.command(name="history", description="View past challenges")
    async def challenge_history(self, ctx: discord.ApplicationContext) -> None:
        """Show completed and expired challenges."""
        await ctx.defer()

        try:
            # Fetch completed challenges from DB
            from src.models.referral_models import CommunityChallenge
            stmt = (
                select(CommunityChallenge)
                .where(CommunityChallenge.status.in_(["completed", "failed"]))
                .order_by(CommunityChallenge.completed_at.desc())
                .limit(10)
            )
            result = await self.referral_manager.db.execute(stmt)
            past = result.scalars().all()

            embed = discord.Embed(
                title="📜 Challenge History",
                color=0x6B7280,
            )

            if past:
                for ch in past:
                    status_emoji = "✅" if ch.status == "completed" else "❌"
                    embed.add_field(
                        name=f"{status_emoji} {ch.title}",
                        value=(
                            f"Result: {ch.current_value:,} / {ch.target_value:,}\n"
                            f"Reward: {ch.reward_description}"
                        ),
                        inline=False,
                    )
            else:
                embed.description = "No challenge history yet."

            await ctx.respond(embed=embed)

        except Exception as e:
            logger.error(f"Error showing challenge history: {e}")
            await ctx.respond("Failed to load history.", ephemeral=True)

    @challenge_group.command(name="create", description="Create a community challenge (admin)")
    @discord.option(name="title", description="Challenge title", required=True)
    @discord.option(name="target", description="Target value (e.g., 500 FTDs)", required=True, type=int)
    @discord.option(name="reward", description="Reward description", required=True)
    @discord.option(name="duration_days", description="Duration in days (default 30)", required=False, default=30)
    @discord.option(
        name="challenge_type",
        description="What to track",
        choices=["ftd_count", "referral_count", "entry_count"],
        required=False,
        default="ftd_count",
    )
    @commands.has_permissions(administrator=True)
    async def challenge_create(
        self,
        ctx: discord.ApplicationContext,
        title: str,
        target: int,
        reward: str,
        duration_days: int = 30,
        challenge_type: str = "ftd_count",
    ) -> None:
        """Create a new community challenge (admin only)."""
        await ctx.defer(ephemeral=True)

        try:
            starts_at = datetime.utcnow()
            ends_at = starts_at + timedelta(days=duration_days)

            challenge = await self.referral_manager.create_challenge(
                title=title,
                description=f"Community goal: reach {target:,} {challenge_type.replace('_', ' ')}!",
                challenge_type=challenge_type,
                target_value=target,
                reward_description=reward,
                reward_type="free_entry",
                reward_value=500,  # $5 in cents
                starts_at=starts_at,
                ends_at=ends_at,
                created_by=ctx.author.id,
            )

            if challenge:
                embed = discord.Embed(
                    title="✅ Challenge Created",
                    description=(
                        f"**{title}**\n"
                        f"Target: {target:,} {challenge_type.replace('_', ' ')}\n"
                        f"Reward: {reward}\n"
                        f"Ends: <t:{int(ends_at.timestamp())}:R>"
                    ),
                    color=0x10B981,
                )
                await ctx.respond(embed=embed, ephemeral=True)
            else:
                await ctx.respond("Failed to create challenge.", ephemeral=True)

        except Exception as e:
            logger.error(f"Error creating challenge: {e}")
            await ctx.respond("Error creating challenge.", ephemeral=True)

    @tasks.loop(minutes=15)
    async def update_challenge_progress(self) -> None:
        """Update challenge progress bar messages."""
        try:
            challenges = await self.referral_manager.get_active_challenges()

            for ch in challenges:
                # TODO: If challenge has a pinned message_id, update the embed
                # This requires storing message_id on CommunityChallenge
                pass

        except Exception as e:
            logger.error(f"Error updating challenge progress: {e}")

    @update_challenge_progress.before_loop
    async def before_progress_update(self) -> None:
        await self.bot.wait_until_ready()


def setup(bot: commands.Bot) -> None:
    pass  # Loaded via bot.add_cog() in main.py
