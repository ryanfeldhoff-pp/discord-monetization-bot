"""
Polls Cog (Pillar 3)

Community polling system including Taco Tuesday weekly polls,
custom admin polls, and bar-chart result visualization.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List

import discord
from discord.ext import commands, tasks
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.event_models import Poll, PollVote
from src.services.xp_manager import XPManager

logger = logging.getLogger(__name__)


class PollView(discord.ui.View):
    """Interactive view for poll voting buttons."""

    def __init__(self, poll_id: int, options: List[str], cog: "PollsCog"):
        super().__init__(timeout=None)
        self.poll_id = poll_id
        self.cog = cog

        for i, option in enumerate(options[:4]):  # Max 4 options
            button = discord.ui.Button(
                label=option[:80],
                style=discord.ButtonStyle.primary,
                custom_id=f"poll_{poll_id}_opt_{i}",
                row=i // 2,
            )
            button.callback = self._make_callback(i)
            self.add_item(button)

    def _make_callback(self, option_index: int):
        async def callback(interaction: discord.Interaction):
            await self.cog.handle_vote(interaction, self.poll_id, option_index)
        return callback


class PollsCog(commands.Cog):
    """
    Polls cog for community engagement.

    Features:
    - /poll create — Create custom poll with up to 4 options
    - /poll taco_tuesday — Launch weekly Taco Tuesday poll
    - /poll results — Show bar-chart results for a poll
    - /poll close — Close a poll early (admin only)
    - Auto-close polls at scheduled time
    - XP awards for poll participation
    """

    def __init__(self, bot: commands.Bot, db_session: AsyncSession, xp_manager: XPManager):
        self.bot = bot
        self.db = db_session
        self.xp_manager = xp_manager
        self.check_poll_expiry.start()

    def cog_unload(self):
        self.check_poll_expiry.cancel()

    poll_group = discord.SlashCommandGroup("poll", "Community polls")

    @poll_group.command(name="create", description="Create a new poll")
    @discord.option(name="title", description="Poll question", required=True)
    @discord.option(name="option1", description="First option", required=True)
    @discord.option(name="option2", description="Second option", required=True)
    @discord.option(name="option3", description="Third option (optional)", required=False)
    @discord.option(name="option4", description="Fourth option (optional)", required=False)
    @discord.option(name="duration_hours", description="Hours until poll closes (default: 24)", required=False, default=24)
    @commands.has_permissions(manage_messages=True)
    async def poll_create(
        self,
        ctx: discord.ApplicationContext,
        title: str,
        option1: str,
        option2: str,
        option3: str = None,
        option4: str = None,
        duration_hours: int = 24,
    ) -> None:
        """Create a custom poll with 2-4 options."""
        await ctx.defer()

        try:
            options = [o for o in [option1, option2, option3, option4] if o]
            closes_at = datetime.utcnow() + timedelta(hours=duration_hours)

            poll = Poll(
                title=title,
                poll_type="custom",
                options_json=json.dumps(options),
                channel_id=ctx.channel_id,
                created_by=ctx.author.id,
                closes_at=closes_at,
            )
            self.db.add(poll)
            await self.db.flush()

            # Build poll embed
            embed = discord.Embed(
                title=f"📊 {title}",
                description=f"Vote below! Poll closes <t:{int(closes_at.timestamp())}:R>",
                color=0x8B5CF6,
            )
            for i, opt in enumerate(options):
                embed.add_field(name=f"Option {i+1}", value=opt, inline=True)
            embed.set_footer(text=f"Poll #{poll.id} • 0 votes")

            view = PollView(poll.id, options, self)
            message = await ctx.respond(embed=embed, view=view)

            # Store message ID for later updates
            msg = await message.original_response()
            poll.message_id = msg.id
            await self.db.flush()

            logger.info(f"Poll #{poll.id} created by {ctx.author.id}: {title}")

        except Exception as e:
            logger.error(f"Error creating poll: {e}")
            await ctx.respond("Failed to create poll. Please try again.", ephemeral=True)

    @poll_group.command(name="taco_tuesday", description="Launch weekly Taco Tuesday poll")
    @commands.has_permissions(manage_messages=True)
    async def taco_tuesday(self, ctx: discord.ApplicationContext) -> None:
        """Launch a Taco Tuesday themed poll with projection-based options."""
        await ctx.defer()

        try:
            title = "🌮 Taco Tuesday — Best Stat Line Tonight?"
            options = [
                "Player A goes MORE on Points",
                "Player B goes LESS on Rebounds",
                "Player C goes MORE on Assists",
                "Player D goes LESS on Strikeouts",
            ]
            # TODO: Dynamically populate from /api/projections
            # For now, use placeholder options that can be overridden

            closes_at = datetime.utcnow() + timedelta(hours=12)

            poll = Poll(
                title=title,
                poll_type="taco_tuesday",
                options_json=json.dumps(options),
                channel_id=ctx.channel_id,
                created_by=ctx.author.id,
                closes_at=closes_at,
            )
            self.db.add(poll)
            await self.db.flush()

            embed = discord.Embed(
                title=title,
                description=(
                    "Vote for tonight's best stat line!\n"
                    f"Closes <t:{int(closes_at.timestamp())}:R>\n\n"
                    "🏆 Winner gets **15 XP** for participating!"
                ),
                color=0xF59E0B,
            )
            for i, opt in enumerate(options):
                embed.add_field(name=f"🌮 Option {i+1}", value=opt, inline=False)
            embed.set_footer(text=f"Poll #{poll.id} • 0 votes")

            view = PollView(poll.id, options, self)
            message = await ctx.respond(embed=embed, view=view)

            msg = await message.original_response()
            poll.message_id = msg.id
            await self.db.flush()

            logger.info(f"Taco Tuesday poll #{poll.id} created")

        except Exception as e:
            logger.error(f"Error creating Taco Tuesday poll: {e}")
            await ctx.respond("Failed to create Taco Tuesday poll.", ephemeral=True)

    @poll_group.command(name="results", description="Show poll results")
    @discord.option(name="poll_id", description="Poll ID number", required=True)
    async def poll_results(self, ctx: discord.ApplicationContext, poll_id: int) -> None:
        """Display bar chart results for a poll."""
        await ctx.defer()

        try:
            stmt = select(Poll).where(Poll.id == poll_id)
            result = await self.db.execute(stmt)
            poll = result.scalar_one_or_none()

            if not poll:
                await ctx.respond("Poll not found.", ephemeral=True)
                return

            options = json.loads(poll.options_json)

            # Count votes per option
            vote_counts = {}
            for i in range(len(options)):
                stmt = select(func.count()).select_from(PollVote).where(
                    and_(PollVote.poll_id == poll_id, PollVote.option_index == i)
                )
                result = await self.db.execute(stmt)
                vote_counts[i] = result.scalar()

            total_votes = sum(vote_counts.values())

            embed = discord.Embed(
                title=f"📊 Results: {poll.title}",
                description=f"**{total_votes}** total votes" + (" • Poll closed" if not poll.is_active else ""),
                color=0x8B5CF6 if poll.is_active else 0x6B7280,
            )

            for i, opt in enumerate(options):
                count = vote_counts.get(i, 0)
                pct = (count / total_votes * 100) if total_votes > 0 else 0
                bar_length = int(pct / 5)  # 20 char max bar
                bar = "█" * bar_length + "░" * (20 - bar_length)
                embed.add_field(
                    name=f"{opt}",
                    value=f"`{bar}` {count} ({pct:.1f}%)",
                    inline=False,
                )

            embed.set_footer(text=f"Poll #{poll_id}")
            await ctx.respond(embed=embed)

        except Exception as e:
            logger.error(f"Error showing poll results: {e}")
            await ctx.respond("Failed to load results.", ephemeral=True)

    @poll_group.command(name="close", description="Close a poll early")
    @discord.option(name="poll_id", description="Poll ID to close", required=True)
    @commands.has_permissions(manage_messages=True)
    async def poll_close(self, ctx: discord.ApplicationContext, poll_id: int) -> None:
        """Close a poll early (admin only)."""
        await ctx.defer()

        try:
            stmt = select(Poll).where(Poll.id == poll_id)
            result = await self.db.execute(stmt)
            poll = result.scalar_one_or_none()

            if not poll:
                await ctx.respond("Poll not found.", ephemeral=True)
                return

            if not poll.is_active:
                await ctx.respond("Poll is already closed.", ephemeral=True)
                return

            poll.is_active = False
            poll.closed_at = datetime.utcnow()
            await self.db.flush()

            await ctx.respond(f"✅ Poll #{poll_id} has been closed.")
            logger.info(f"Poll #{poll_id} closed by {ctx.author.id}")

        except Exception as e:
            logger.error(f"Error closing poll: {e}")
            await ctx.respond("Failed to close poll.", ephemeral=True)

    async def handle_vote(
        self, interaction: discord.Interaction, poll_id: int, option_index: int
    ) -> None:
        """Handle a vote button click."""
        try:
            user_id = interaction.user.id

            # Check if poll is still active
            stmt = select(Poll).where(Poll.id == poll_id)
            result = await self.db.execute(stmt)
            poll = result.scalar_one_or_none()

            if not poll or not poll.is_active:
                await interaction.response.send_message(
                    "This poll is closed.", ephemeral=True
                )
                return

            # Check for existing vote
            stmt = select(PollVote).where(
                and_(PollVote.poll_id == poll_id, PollVote.discord_user_id == user_id)
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

            options = json.loads(poll.options_json)

            if existing:
                # Update vote
                existing.option_index = option_index
                existing.voted_at = datetime.utcnow()
                await self.db.flush()
                await interaction.response.send_message(
                    f"Vote changed to: **{options[option_index]}**", ephemeral=True
                )
            else:
                # New vote
                vote = PollVote(
                    poll_id=poll_id,
                    discord_user_id=user_id,
                    option_index=option_index,
                )
                self.db.add(vote)
                await self.db.flush()

                # Award XP for first vote
                await self.xp_manager.award_xp(
                    user_id,
                    self.xp_manager.XP_VALUES["poll_participation"],
                    "poll_participation",
                    metadata={"poll_id": poll_id},
                    ignore_daily_cap=True,
                )

                await interaction.response.send_message(
                    f"Voted: **{options[option_index]}** (+{self.xp_manager.XP_VALUES['poll_participation']} XP!)",
                    ephemeral=True,
                )

            # Update vote count in footer
            stmt = select(func.count()).select_from(PollVote).where(PollVote.poll_id == poll_id)
            result = await self.db.execute(stmt)
            total = result.scalar()

            try:
                channel = self.bot.get_channel(poll.channel_id)
                if channel and poll.message_id:
                    msg = await channel.fetch_message(poll.message_id)
                    embed = msg.embeds[0]
                    embed.set_footer(text=f"Poll #{poll_id} • {total} votes")
                    await msg.edit(embed=embed)
            except Exception:
                pass  # Non-critical: footer update

        except Exception as e:
            logger.error(f"Error handling vote: {e}")
            await interaction.response.send_message(
                "Error recording vote. Please try again.", ephemeral=True
            )

    @tasks.loop(minutes=5)
    async def check_poll_expiry(self) -> None:
        """Auto-close expired polls."""
        try:
            stmt = select(Poll).where(
                and_(
                    Poll.is_active == True,
                    Poll.closes_at.isnot(None),
                    Poll.closes_at <= datetime.utcnow(),
                )
            )
            result = await self.db.execute(stmt)
            expired = result.scalars().all()

            for poll in expired:
                poll.is_active = False
                poll.closed_at = datetime.utcnow()
                logger.info(f"Auto-closed poll #{poll.id}")

            if expired:
                await self.db.flush()

        except Exception as e:
            logger.error(f"Error checking poll expiry: {e}")

    @check_poll_expiry.before_loop
    async def before_check_expiry(self) -> None:
        await self.bot.wait_until_ready()


def setup(bot: commands.Bot) -> None:
    """Setup function for bot to load this cog."""
    pass  # Loaded via bot.add_cog() in main.py
