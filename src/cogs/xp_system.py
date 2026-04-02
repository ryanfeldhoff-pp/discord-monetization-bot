"""
XP System Cog

Handles message listening for XP awards, XP commands, and anti-spam logic.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict
from collections import defaultdict

import discord
from discord.ext import commands, tasks

from src.services.xp_manager import XPManager
from src.utils.colors import get_tier_color
from src.utils.embeds import (
    success_embed,
    error_embed,
    info_embed,
    empty_state_embed,
    leaderboard_embed,
    progress_bar,
)
from src.utils.pagination import PaginatedView

logger = logging.getLogger(__name__)


class XPSystem(commands.Cog):
    """
    XP System cog for managing user experience points.

    Features:
    - Message listener with anti-spam and daily caps
    - /xp — Show current XP and rank
    - /leaderboard — View leaderboard (daily, weekly, monthly, all-time)
    - Background task for XP decay and buffer flushing
    """

    # Anti-spam config
    MIN_MESSAGE_LENGTH = 10
    MIN_TIME_BETWEEN_AWARDS = 5  # seconds
    DAILY_XP_CAP = 500  # for messages only

    def __init__(self, bot: commands.Bot, xp_manager: XPManager):
        """
        Initialize XP System cog.

        Args:
            bot: Discord bot instance
            xp_manager: XPManager service instance
        """
        self.bot = bot
        self.xp_manager = xp_manager

        # Track last XP award time per user
        self._last_award_time: Dict[int, datetime] = {}
        # Track message history for duplicate detection
        self._message_history: Dict[int, list] = defaultdict(list)

        self.flush_xp_buffer.start()
        self.process_xp_decay.start()

    def cog_unload(self):
        """Clean up background tasks."""
        self.flush_xp_buffer.cancel()
        self.process_xp_decay.cancel()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        Listen for messages and award XP.

        Anti-spam measures:
        - Minimum 10 characters
        - No duplicate messages
        - 5 second cooldown between awards
        - Daily cap of 500 XP from messages

        Args:
            message: Discord message object
        """
        # Ignore bot messages and DMs
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        current_time = datetime.utcnow()

        # Anti-spam: message length
        if len(message.content) < self.MIN_MESSAGE_LENGTH:
            return

        # Anti-spam: time since last award
        last_award = self._last_award_time.get(user_id)
        if last_award:
            time_diff = (current_time - last_award).total_seconds()
            if time_diff < self.MIN_TIME_BETWEEN_AWARDS:
                # Send ephemeral cooldown feedback
                try:
                    seconds_left = int(self.MIN_TIME_BETWEEN_AWARDS - time_diff)
                    embed = info_embed(
                        "XP Cooldown",
                        f"You just earned XP! Next eligible in {seconds_left} seconds"
                    )
                    await message.author.send(embed=embed, delete_after=10)
                except discord.Forbidden:
                    pass
                return

        # Anti-spam: duplicate detection
        message_hash = hash(message.content.lower())
        history = self._message_history[user_id]

        # Keep only recent messages (last minute)
        cutoff = current_time - timedelta(minutes=1)
        history = [
            (msg_hash, msg_time)
            for msg_hash, msg_time in history
            if msg_time > cutoff
        ]
        self._message_history[user_id] = history

        if any(msg_hash == message_hash for msg_hash, _ in history):
            return

        # Record this message
        history.append((message_hash, current_time))

        # Award XP
        success, msg = await self.xp_manager.award_xp(
            user_id=user_id,
            amount=self.xp_manager.XP_VALUES["message"],
            source="message",
            metadata={
                "guild_id": message.guild.id,
                "channel_id": message.channel.id,
                "message_id": message.id,
            },
        )

        if success:
            self._last_award_time[user_id] = current_time
            logger.debug(f"Awarded XP to user {user_id}: {msg}")

            # Send success feedback
            try:
                embed = success_embed(
                    "XP Awarded",
                    f"✅ {self.xp_manager.XP_VALUES['message']} XP awarded for sharing entry"
                )
                await message.author.send(embed=embed, delete_after=15)
            except discord.Forbidden:
                pass

    @commands.slash_command(
        name="xp",
        description="Show your current XP, rank, and progress to next tier"
    )
    async def xp_command(self, ctx: discord.ApplicationContext) -> None:
        """
        Show user's XP balance, rank, and tier progress.

        Returns an embed with:
        - Current XP balance
        - Lifetime XP earned
        - Current tier and progress to next tier
        - Leaderboard rank and percentile
        """
        await ctx.defer()

        try:
            user_id = ctx.author.id
            xp_data = await self.xp_manager.get_xp(user_id)

            # Check if user has no XP
            if not xp_data or xp_data["balance"] == 0:
                embed = empty_state_embed(
                    "XP System",
                    "XP is earned by chatting and completing activities in the community!",
                    ["/xp view", "/leaderboard"]
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            rank_data = await self.xp_manager.get_rank(user_id)
            current_tier = xp_data["tier"]
            current_xp = xp_data["balance"]

            # Calculate progress to next tier
            tier_keys = ["bronze", "silver", "gold", "diamond"]
            current_tier_idx = tier_keys.index(current_tier)
            current_threshold = self.xp_manager.TIER_THRESHOLDS[current_tier]

            if current_tier == "diamond":
                progress_text = "Reached Diamond tier!"
                bar = progress_bar(100, 100)
            else:
                next_tier = tier_keys[current_tier_idx + 1]
                next_threshold = self.xp_manager.TIER_THRESHOLDS[next_tier]
                progress = current_xp - current_threshold
                needed = next_threshold - current_threshold
                bar = progress_bar(progress, needed)
                progress_text = f"{progress:,} / {needed:,} XP to {next_tier.capitalize()}"

            # Build embed using utility function
            tier_color = get_tier_color(current_tier)
            embed = info_embed(
                f"XP Profile - {ctx.author.name}",
                f"**{current_tier.upper()}** Tier",
                [
                    ("Current XP", f"**{current_xp:,}**", True),
                    ("Lifetime XP", f"**{xp_data['lifetime']:,}**", True),
                    ("Rank", f"**#{rank_data['rank']}** ({rank_data['percentile']:.1f}th percentile)", False),
                    ("Progress", f"{bar}\n{progress_text}", False),
                ]
            )
            embed.color = tier_color
            embed.set_thumbnail(url=ctx.author.avatar.url)

            await ctx.respond(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in xp command: {e}")
            embed = error_embed(
                "XP Lookup Failed",
                "Could not retrieve your XP data",
                recovery_hint="Please try again in a moment",
                error_code="XP_FETCH_ERROR"
            )
            await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(
        name="leaderboard",
        description="View the XP leaderboard"
    )
    @discord.option(
        name="period",
        description="Time period for leaderboard",
        choices=["daily", "weekly", "monthly", "alltime"],
        default="alltime",
    )
    @discord.option(
        name="limit",
        description="Number of top users to show",
        min_value=5,
        max_value=50,
        default=10,
    )
    async def leaderboard_command(
        self,
        ctx: discord.ApplicationContext,
        period: str = "alltime",
        limit: int = 10,
    ) -> None:
        """
        Display the XP leaderboard for a period with pagination.

        Args:
            period: "daily", "weekly", "monthly", or "alltime"
            limit: Number of top users to show (5-50)
        """
        await ctx.defer()

        try:
            lb_data = await self.xp_manager.get_leaderboard(
                period=period,
                limit=limit,
                user_id=ctx.author.id,
            )

            leaderboard = lb_data["leaderboard"]
            if not leaderboard:
                embed = empty_state_embed(
                    "XP Leaderboard",
                    f"No leaderboard data available for {period}",
                    ["/xp view", "/leaderboard"]
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            # Build leaderboard entries - sort by XP DESC, last earned ASC for tiebreaker
            entries = []
            for entry in leaderboard:
                try:
                    user = await self.bot.fetch_user(entry["user_id"])
                    user_name = user.name
                except discord.NotFound:
                    user_name = f"Unknown User ({entry['user_id']})"

                entries.append({
                    "rank": entry["rank"],
                    "username": user_name,
                    "value": entry["xp"],
                    "user_id": entry["user_id"],
                })

            # Build period display
            period_display = {
                "daily": "Daily",
                "weekly": "Weekly",
                "monthly": "Monthly",
                "alltime": "All-Time",
            }

            # Get user position
            user_pos = lb_data.get("user_position")

            # Create embed using leaderboard_embed utility
            embed = leaderboard_embed(
                f"{period_display[period]} XP Leaderboard",
                entries,
                page=1,
                total_pages=1,
                user_rank=user_pos["rank"] if user_pos else None
            )

            # Create paginated view with jump to rank callback
            async def on_jump_to_rank(interaction: discord.Interaction) -> None:
                if user_pos and user_pos["rank"] > 0:
                    await interaction.response.send_message(
                        f"📍 Your rank: **#{user_pos['rank']}** with **{user_pos.get('xp', 0):,}** XP",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "You don't have a ranking yet. Start earning XP!",
                        ephemeral=True
                    )

            view = PaginatedView([embed], on_jump_to_rank=on_jump_to_rank)

            await ctx.respond(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Error in leaderboard command: {e}")
            embed = error_embed(
                "Leaderboard Lookup Failed",
                "Could not retrieve leaderboard data",
                recovery_hint="Please try again in a moment",
                error_code="LEADERBOARD_FETCH_ERROR"
            )
            await ctx.respond(embed=embed, ephemeral=True)

    @tasks.loop(minutes=5)
    async def flush_xp_buffer(self) -> None:
        """
        Flush in-memory XP buffer to database every 5 minutes.

        This prevents constant database writes while still persisting
        XP data regularly.
        """
        try:
            updated_count = await self.xp_manager.flush_xp_buffer()
            if updated_count > 0:
                logger.info(f"Flushed XP buffer: {updated_count} users updated")
        except Exception as e:
            logger.error(f"Error flushing XP buffer: {e}")

    @flush_xp_buffer.before_loop
    async def before_flush(self) -> None:
        """Wait for bot to be ready before starting flush task."""
        await self.bot.wait_until_ready()

    @tasks.loop(hours=24)
    async def process_xp_decay(self) -> None:
        """
        Process XP decay for inactive users daily.

        Decays XP by 10% per week after 30 days of inactivity.
        """
        try:
            affected_count = await self.xp_manager.process_decay()
            logger.info(f"XP decay processed: {affected_count} users affected")
        except Exception as e:
            logger.error(f"Error processing XP decay: {e}")

    @process_xp_decay.before_loop
    async def before_decay(self) -> None:
        """Wait for bot to be ready before starting decay task."""
        await self.bot.wait_until_ready()



def setup(bot: commands.Bot, xp_manager: XPManager) -> None:
    """Setup function for bot to load this cog."""
    bot.add_cog(XPSystem(bot, xp_manager))
