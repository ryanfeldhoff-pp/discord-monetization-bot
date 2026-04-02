"""
Community Polls Cog

Manages community polls including weekly Taco Tuesday polls.
Features slash commands for poll creation, voting, and results,
plus background tasks for automatic Taco Tuesday polls and poll closing.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict

import discord
from discord.ext import commands, tasks
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.event_models import Poll
from src.services.xp_manager import XPManager
from src.utils.colors import PRIZEPICKS_PRIMARY
from src.utils.embeds import success_embed, error_embed, info_embed, empty_state_embed, progress_bar
from src.utils.validation import validate_length, validate_range
from src.utils.views import ConfirmView

logger = logging.getLogger(__name__)

# Taco Tuesday player pool (hardcoded for demo; could be fetched from PrizePicks API)
TACO_TUESDAY_PLAYERS = [
    "Mahomes",
    "Lamar Jackson",
    "Josh Allen",
    "Jalen Hurts",
]


class PollView(discord.ui.View):
    """Interactive view for voting on poll options."""

    def __init__(self, poll_id: int, options: List[str], cog: "PollsCog"):
        """
        Initialize poll view with voting buttons.

        Args:
            poll_id: ID of the poll
            options: List of option strings
            cog: Reference to PollsCog for vote processing
        """
        super().__init__(timeout=None)
        self.poll_id = poll_id
        self.options = options
        self.cog = cog

        # Create buttons for each option (max 4)
        option_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
        for idx, option in enumerate(options[:4]):
            button = discord.ui.Button(
                label=option[:20],
                emoji=option_emojis[idx],
                custom_id=f"poll_{poll_id}_{idx}",
                style=discord.ButtonStyle.primary,
            )
            button.callback = self._create_vote_callback(idx)
            self.add_item(button)

    async def _create_vote_callback(self, option_idx: int):
        """Create callback function for vote button."""

        async def callback(interaction: discord.Interaction) -> None:
            await self.cog.process_vote(interaction, self.poll_id, option_idx)

        return callback


class PollsCog(commands.Cog):
    """
    Community Polls cog.

    Manages poll creation, voting, results, and automatic Taco Tuesday polls.
    """

    def __init__(
        self,
        bot: commands.Bot,
        db_session: AsyncSession,
        xp_manager: XPManager,
    ):
        """
        Initialize Polls cog.

        Args:
            bot: Discord bot instance
            db_session: Database session for poll storage
            xp_manager: XP manager for awarding poll participation XP
        """
        self.bot = bot
        self.db = db_session
        self.xp_manager = xp_manager

        self.schedule_taco_tuesday.start()
        self.auto_close_polls.start()

    def cog_unload(self) -> None:
        """Clean up background tasks."""
        self.schedule_taco_tuesday.cancel()
        self.auto_close_polls.cancel()

    @commands.slash_command(
        name="poll",
        description="Create and manage community polls",
    )
    async def poll_group(self, ctx: discord.ApplicationContext) -> None:
        """Slash command group for polls."""
        pass

    @poll_group.command(
        name="list",
        description="Show active polls",
    )
    async def list_polls(self, ctx: discord.ApplicationContext) -> None:
        """
        List all active polls.

        Args:
            ctx: Discord application context
        """
        await ctx.defer()

        try:
            stmt = select(Poll).where(
                and_(
                    Poll.guild_id == ctx.guild_id,
                    Poll.status == "active",
                )
            )
            result = await self.db.execute(stmt)
            polls = result.scalars().all()

            if not polls:
                embed = empty_state_embed(
                    "Polls",
                    "No active polls right now",
                    ["/poll create", "/poll taco_tuesday"]
                )
                await ctx.followup.send(embed=embed)
                return

            embed = info_embed(
                "Active Polls",
                f"Viewing {len(polls)} poll(s)"
            )

            for poll in polls[:5]:
                options_data = json.loads(poll.options_json)
                votes_data = json.loads(poll.votes_json)
                option_count = len(options_data)
                total_votes = len(votes_data)

                embed.add_field(
                    name=f"• {poll.title[:40]}",
                    value=f"ID: `{poll.id}` • {option_count} options • {total_votes} votes",
                    inline=False,
                )

            await ctx.followup.send(embed=embed)

        except Exception as e:
            logger.exception("Error listing polls")
            await ctx.followup.send(
                embed=error_embed(
                    "List Failed",
                    "Could not retrieve polls",
                    recovery_hint="Try again",
                    error_code="POLL_LIST_ERROR"
                ),
                ephemeral=True,
            )

    @poll_group.command(
        name="create",
        description="Create a new community poll (admin/mod only)",
    )
    @commands.has_permissions(manage_messages=True)
    async def create_poll(
        self,
        ctx: discord.ApplicationContext,
        title: str,
        option1: str,
        option2: str,
        option3: Optional[str] = None,
        option4: Optional[str] = None,
        duration_hours: int = 168,
    ) -> None:
        """
        Create a new poll with up to 4 options.

        Args:
            ctx: Discord application context
            title: Poll title/question
            option1: First option
            option2: Second option
            option3: Optional third option
            option4: Optional fourth option
            duration_hours: How long poll stays open (default 7 days = 168 hours)
        """
        await ctx.defer()

        try:
            # Validate title length
            is_valid, error_msg = validate_length(title, 1, 100, "Poll title")
            if not is_valid:
                await ctx.followup.send(
                    embed=error_embed("Invalid Title", error_msg),
                    ephemeral=True,
                )
                return

            # Validate duration
            is_valid, error_msg = validate_range(duration_hours, 1, 2160, "Duration")
            if not is_valid:
                await ctx.followup.send(
                    embed=error_embed("Invalid Duration", error_msg),
                    ephemeral=True,
                )
                return

            # Build options list
            options = [option1, option2]
            if option3:
                options.append(option3)
            if option4:
                options.append(option4)

            # Validate options count
            if len(options) < 2 or len(options) > 4:
                await ctx.followup.send(
                    embed=error_embed(
                        "Invalid Options Count",
                        "Polls must have 2-4 options",
                        recovery_hint="Remove extra options or add more"
                    ),
                    ephemeral=True,
                )
                return

            # Create poll record
            poll = Poll(
                guild_id=ctx.guild_id,
                channel_id=ctx.channel_id,
                title=title,
                poll_type="community",
                options_json=json.dumps([{"text": opt, "votes": 0} for opt in options]),
                votes_json=json.dumps({}),
                status="active",
                created_by=ctx.author.id,
                closes_at=datetime.utcnow() + timedelta(hours=duration_hours),
            )

            self.db.add(poll)
            await self.db.flush()
            await self.db.commit()

            # Create message with voting view
            closes_in = f"{duration_hours} hours"
            if duration_hours == 168:
                closes_in = "7 days"
            elif duration_hours == 24:
                closes_in = "1 day"

            embed = info_embed(
                title,
                f"Created by {ctx.author.mention} • Closes in {closes_in}",
                fields=[
                    ("Options", "\n".join([f"• {opt}" for opt in options]), False),
                ]
            )

            view = PollView(poll.id, options, self)
            message = await ctx.respond(embed=embed, view=view)

            # Store message ID
            poll.message_id = message.id
            await self.db.commit()

            await ctx.followup.send(
                embed=success_embed("Poll Created", f"Poll ID: `{poll.id}`"),
                ephemeral=True,
            )

        except Exception as e:
            logger.exception("Error creating poll")
            await ctx.followup.send(
                embed=error_embed(
                    "Poll Creation Failed",
                    "An error occurred while creating the poll",
                    recovery_hint="Try again or contact support",
                    error_code="POLL_CREATE_ERROR"
                ),
                ephemeral=True,
            )

    @poll_group.command(
        name="taco_tuesday",
        description="Launch weekly Taco Tuesday poll (admin only)",
    )
    @commands.has_permissions(administrator=True)
    async def taco_tuesday_poll(self, ctx: discord.ApplicationContext) -> None:
        """
        Create a Taco Tuesday poll with this week's top players.

        Args:
            ctx: Discord application context
        """
        await ctx.defer()

        try:
            title = "🌮 Taco Tuesday: Best Stat Line This Week?"
            options = TACO_TUESDAY_PLAYERS[:4]

            # Create Taco Tuesday poll record
            poll = Poll(
                guild_id=ctx.guild_id,
                channel_id=ctx.channel_id,
                title=title,
                poll_type="taco_tuesday",
                options_json=json.dumps([{"text": opt, "votes": 0} for opt in options]),
                votes_json=json.dumps({}),
                status="active",
                created_by=ctx.author.id,
                closes_at=datetime.utcnow() + timedelta(days=1),
            )

            self.db.add(poll)
            await self.db.flush()
            await self.db.commit()

            # Create message with voting view
            embed = info_embed(
                title,
                "Vote on this week's top performer!",
                fields=[
                    ("Nominees", "\n".join([f"• {opt}" for opt in options]), False),
                ]
            )

            view = PollView(poll.id, options, self)
            message = await ctx.respond(embed=embed, view=view)

            # Store message ID
            poll.message_id = message.id
            await self.db.commit()

            await ctx.followup.send(
                embed=success_embed("Taco Tuesday", "Poll launched! 🌮"),
                ephemeral=True,
            )

        except Exception as e:
            logger.exception("Error creating Taco Tuesday poll")
            await ctx.followup.send(
                embed=error_embed(
                    "Poll Creation Failed",
                    "Failed to create Taco Tuesday poll",
                    recovery_hint="Try again later",
                    error_code="TACO_POLL_ERROR"
                ),
                ephemeral=True,
            )

    @poll_group.command(
        name="results",
        description="Show poll results with vote counts",
    )
    async def poll_results(
        self,
        ctx: discord.ApplicationContext,
        poll_id: int,
    ) -> None:
        """
        Display poll results with vote counts and bar chart.

        Args:
            ctx: Discord application context
            poll_id: ID of the poll to show results for
        """
        await ctx.defer()

        try:
            # Fetch poll
            stmt = select(Poll).where(Poll.id == poll_id)
            result = await self.db.execute(stmt)
            poll = result.scalars().first()

            if not poll:
                await ctx.followup.send(
                    embed=error_embed(
                        "Poll Not Found",
                        f"No poll found with ID: {poll_id}",
                        recovery_hint="Check the poll ID and try again"
                    ),
                    ephemeral=True,
                )
                return

            # Parse options and votes
            options = json.loads(poll.options_json)
            votes = json.loads(poll.votes_json)

            # Count votes per option
            vote_counts = [0] * len(options)
            for vote_option_idx in votes.values():
                if 0 <= vote_option_idx < len(vote_counts):
                    vote_counts[vote_option_idx] += 1

            total_votes = sum(vote_counts)

            # Build results embed
            embed = info_embed(
                f"Results: {poll.title[:50]}",
                f"Total votes: {total_votes}"
            )

            # Add vote bars for each option
            for idx, option in enumerate(options):
                count = vote_counts[idx]
                bar = progress_bar(count, max(total_votes, 1))
                embed.add_field(
                    name=f"{option.get('text', option)}",
                    value=f"{bar}\n`{count}` votes",
                    inline=False,
                )

            await ctx.followup.send(embed=embed)

        except Exception as e:
            logger.exception("Error fetching poll results")
            await ctx.followup.send(
                embed=error_embed(
                    "Results Fetch Failed",
                    "Could not retrieve poll results",
                    recovery_hint="Try again in a moment",
                    error_code="POLL_RESULTS_ERROR"
                ),
                ephemeral=True,
            )

    @poll_group.command(
        name="close",
        description="Close a poll early (admin only)",
    )
    @commands.has_permissions(administrator=True)
    async def close_poll(
        self,
        ctx: discord.ApplicationContext,
        poll_id: int,
    ) -> None:
        """
        Close a poll early, preventing further votes.

        Args:
            ctx: Discord application context
            poll_id: ID of the poll to close
        """
        await ctx.defer()

        try:
            # Fetch and update poll
            stmt = select(Poll).where(Poll.id == poll_id)
            result = await self.db.execute(stmt)
            poll = result.scalars().first()

            if not poll:
                await ctx.followup.send(
                    embed=error_embed(
                        "Poll Not Found",
                        f"No poll with ID: {poll_id}",
                        recovery_hint="Check the ID and try again"
                    ),
                    ephemeral=True,
                )
                return

            # Ask for confirmation
            view = ConfirmView()
            confirm_embed = info_embed(
                "Close Poll?",
                f"Close poll \"{poll.title[:40]}\"? Results will be final.",
            )
            await ctx.followup.send(embed=confirm_embed, view=view, ephemeral=True)

            await view.wait()
            if view.result:
                poll.status = "closed"
                poll.closed_at = datetime.utcnow()
                await self.db.commit()

                await ctx.followup.send(
                    embed=success_embed("Poll Closed", f"Poll {poll_id} is now closed"),
                    ephemeral=True,
                )
            else:
                await ctx.followup.send(
                    "Poll close cancelled",
                    ephemeral=True,
                )

        except Exception as e:
            logger.exception("Error closing poll")
            await ctx.followup.send(
                embed=error_embed(
                    "Close Failed",
                    "Could not close the poll",
                    recovery_hint="Try again",
                    error_code="POLL_CLOSE_ERROR"
                ),
                ephemeral=True,
            )

    async def process_vote(
        self,
        interaction: discord.Interaction,
        poll_id: int,
        option_idx: int,
    ) -> None:
        """
        Process a vote on a poll option.

        Args:
            interaction: Discord interaction from button press
            poll_id: ID of the poll
            option_idx: Index of the selected option
        """
        try:
            # Fetch poll
            stmt = select(Poll).where(Poll.id == poll_id)
            result = await self.db.execute(stmt)
            poll = result.scalars().first()

            if not poll:
                await interaction.response.send_message(
                    "Poll not found.",
                    ephemeral=True,
                )
                return

            if poll.status != "active":
                await interaction.response.send_message(
                    "This poll is no longer active.",
                    ephemeral=True,
                )
                return

            # Record vote
            votes = json.loads(poll.votes_json)
            votes[str(interaction.user.id)] = option_idx
            poll.votes_json = json.dumps(votes)
            await self.db.commit()

            # Award XP
            await self.xp_manager.award_xp(
                interaction.user.id,
                15,
                "poll_participation",
            )

            # Show confirmation
            options = json.loads(poll.options_json)
            selected_option = options[option_idx].get("text", "Unknown")

            embed = success_embed(
                "Vote Recorded",
                f"You voted for: **{selected_option}**"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.exception("Error processing poll vote")
            await interaction.response.send_message(
                embed=error_embed(
                    "Vote Failed",
                    "Could not record your vote",
                    recovery_hint="Try again",
                ),
                ephemeral=True,
            )

    @tasks.loop(hours=24)
    async def schedule_taco_tuesday(self) -> None:
        """
        Automatically create Taco Tuesday poll every Tuesday at 12pm ET.

        This task runs daily and checks if today is Tuesday at the target time.
        """
        try:
            now = datetime.utcnow()
            # Check if it's Tuesday (weekday 1) and around noon UTC (4pm UTC = 12pm ET)
            if now.weekday() == 1 and 15 <= now.hour < 16:
                # Get the main guild (assuming it's stored in bot)
                guild = self.bot.get_guild(
                    int(self.bot.config.get("MAIN_GUILD_ID", 0))
                    if hasattr(self.bot, "config")
                    else 0
                )
                if guild:
                    # Get announcement channel
                    channel = guild.get_channel(
                        int(self.bot.config.get("ANNOUNCEMENTS_CHANNEL_ID", 0))
                        if hasattr(self.bot, "config")
                        else 0
                    )
                    if channel:
                        title = "🌮 Taco Tuesday: Which player has the best stat line this week?"
                        options = TACO_TUESDAY_PLAYERS[:4]

                        poll = Poll(
                            guild_id=guild.id,
                            channel_id=channel.id,
                            title=title,
                            poll_type="taco_tuesday",
                            options_json=json.dumps(
                                [{"text": opt, "votes": 0} for opt in options]
                            ),
                            votes_json=json.dumps({}),
                            status="active",
                            created_by=self.bot.user.id,
                            closes_at=datetime.utcnow() + timedelta(days=1),
                        )

                        self.db.add(poll)
                        await self.db.flush()
                        await self.db.commit()

                        embed = discord.Embed(
                            title=title,
                            description="Vote on this week's top performer!",
                            color=PRIZEPICKS_COLOR,
                            timestamp=datetime.utcnow(),
                        )
                        embed.add_field(
                            name="Nominees",
                            value="\n".join([f"• {opt}" for opt in options]),
                            inline=False,
                        )

                        view = PollView(poll.id, options, self)
                        await channel.send(embed=embed, view=view)

        except Exception as e:
            logger.exception("Error in schedule_taco_tuesday background task")

    @schedule_taco_tuesday.before_loop
    async def before_schedule_taco_tuesday(self) -> None:
        """Wait for bot to be ready before starting task."""
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=30)
    async def auto_close_polls(self) -> None:
        """
        Automatically close polls that have reached their closes_at time.

        This task runs every 30 minutes and closes expired active polls.
        """
        try:
            stmt = select(Poll).where(
                and_(
                    Poll.status == "active",
                    Poll.closes_at <= datetime.utcnow(),
                )
            )
            result = await self.db.execute(stmt)
            expired_polls = result.scalars().all()

            for poll in expired_polls:
                poll.status = "closed"
                poll.closed_at = datetime.utcnow()

            if expired_polls:
                await self.db.commit()
                logger.info(f"Auto-closed {len(expired_polls)} expired polls")

        except Exception as e:
            logger.exception("Error in auto_close_polls background task")

    @auto_close_polls.before_loop
    async def before_auto_close_polls(self) -> None:
        """Wait for bot to be ready before starting task."""
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    """Load the Polls cog."""
    db_session = bot.db
    xp_manager = bot.xp_manager
    await bot.add_cog(PollsCog(bot, db_session, xp_manager))
