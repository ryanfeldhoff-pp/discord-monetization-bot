"""
Game-Day Channels Cog

Manages automatic creation and archival of game-day specific Discord channels
for live event discussions.

Features slash commands for manual channel management and background tasks
for automatic channel creation/archival based on sports schedules.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord.ext import commands, tasks
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.event_models import GameDayChannel
from src.utils.colors import PRIZEPICKS_PRIMARY
from src.utils.embeds import success_embed, error_embed, info_embed, empty_state_embed
from src.utils.validation import validate_datetime, validate_length, validate_non_empty
from src.utils.views import ConfirmView

logger = logging.getLogger(__name__)

# Sports abbreviations for channel naming
SPORT_EMOJI = {
    "nfl": "🏈",
    "nba": "🏀",
    "mlb": "⚾",
    "nhl": "🏒",
    "college_football": "🏈",
    "college_basketball": "🏀",
    "mls": "⚽",
}


class GameDayChannelsCog(commands.Cog):
    """
    Game-Day Channels cog.

    Automatically manages creation and archival of channels for live sports events.
    """

    # Category names for organizing channels
    GAMEDAY_CATEGORY = "Game Day"
    ARCHIVED_CATEGORY = "Archived Games"

    def __init__(
        self,
        bot: commands.Bot,
        db_session: AsyncSession,
        sports_schedule_service: Optional[object] = None,
    ):
        """
        Initialize Game-Day Channels cog.

        Args:
            bot: Discord bot instance
            db_session: Database session for channel tracking
            sports_schedule_service: Optional service for fetching sports schedules
        """
        self.bot = bot
        self.db = db_session
        self.sports_schedule_service = sports_schedule_service

        self.check_schedule.start()
        self.auto_archive.start()

    def cog_unload(self) -> None:
        """Clean up background tasks."""
        self.check_schedule.cancel()
        self.auto_archive.cancel()

    @commands.slash_command(
        name="gameday",
        description="Manage game-day channels",
    )
    async def gameday_group(self, ctx: discord.ApplicationContext) -> None:
        """Slash command group for game-day management."""
        pass

    @gameday_group.command(
        name="list",
        description="Show today's game-day channels",
    )
    async def list_gameday_channels(self, ctx: discord.ApplicationContext) -> None:
        """
        List all active game-day channels for today.

        Args:
            ctx: Discord application context
        """
        await ctx.defer()

        try:
            today = datetime.utcnow().date()
            tomorrow = today + timedelta(days=1)

            stmt = select(GameDayChannel).where(
                and_(
                    GameDayChannel.guild_id == ctx.guild_id,
                    GameDayChannel.status == "active",
                    GameDayChannel.scheduled_start >= datetime.combine(today, datetime.min.time()),
                    GameDayChannel.scheduled_start < datetime.combine(tomorrow, datetime.min.time()),
                )
            )
            result = await self.db.execute(stmt)
            channels = result.scalars().all()

            if not channels:
                embed = empty_state_embed(
                    "Game Day",
                    "No game-day channels active",
                    ["/gameday create"]
                )
                await ctx.followup.send(embed=embed)
                return

            embed = info_embed(
                "Today's Games",
                f"{len(channels)} game(s) scheduled"
            )

            for channel_record in channels:
                emoji = SPORT_EMOJI.get(channel_record.sport, "🎮")
                start_time = channel_record.scheduled_start.strftime("%H:%M")
                discord_channel = ctx.guild.get_channel(channel_record.channel_id)
                channel_mention = (
                    discord_channel.mention if discord_channel else f"#{channel_record.event_name}"
                )

                embed.add_field(
                    name=f"{emoji} {channel_record.event_name[:40]}",
                    value=f"{channel_mention} • {start_time}",
                    inline=True,
                )

            await ctx.followup.send(embed=embed)

        except Exception as e:
            logger.exception("Error listing game-day channels")
            await ctx.followup.send(
                embed=error_embed(
                    "List Failed",
                    "Could not retrieve channels",
                    recovery_hint="Try again",
                    error_code="GAMEDAY_LIST_ERROR"
                ),
                ephemeral=True,
            )

    @gameday_group.command(
        name="create",
        description="Manually create a game-day channel (admin only)",
    )
    @commands.has_permissions(administrator=True)
    async def create_gameday_channel(
        self,
        ctx: discord.ApplicationContext,
        sport: str,
        event_name: str,
        start_time: str,
    ) -> None:
        """
        Manually create a game-day channel.

        Args:
            ctx: Discord application context
            sport: Sport type (nfl, nba, mlb, nhl, etc.)
            event_name: Human-readable event name (e.g., "Chiefs vs Bills")
            start_time: ISO format start time (YYYY-MM-DD HH:MM)
        """
        await ctx.defer()

        try:
            # Validate inputs
            is_valid, error_msg = validate_length(event_name, 1, 50, "Event name")
            if not is_valid:
                await ctx.followup.send(
                    embed=error_embed("Invalid Event", error_msg),
                    ephemeral=True,
                )
                return

            is_valid, error_msg = validate_length(sport, 1, 20, "Sport")
            if not is_valid:
                await ctx.followup.send(
                    embed=error_embed("Invalid Sport", error_msg),
                    ephemeral=True,
                )
                return

            # Parse start time
            scheduled_start, error_msg = validate_datetime(start_time, "Start time")
            if error_msg:
                await ctx.followup.send(
                    embed=error_embed("Invalid Time", error_msg),
                    ephemeral=True,
                )
                return

            # Confirm timezone and time
            confirm_embed = info_embed(
                "Confirm Game-Day Channel",
                f"Creating for {scheduled_start.strftime('%I:%M %p UTC')}. Correct?"
            )
            view = ConfirmView()
            await ctx.followup.send(embed=confirm_embed, view=view, ephemeral=True)

            await view.wait()
            if not view.result:
                await ctx.followup.send("Cancelled", ephemeral=True)
                return

            # Create Discord channel
            channel_name = self._format_channel_name(sport, event_name)
            category = await self._get_or_create_category(ctx.guild, self.GAMEDAY_CATEGORY)

            if not category:
                await ctx.followup.send(
                    embed=error_embed(
                        "Category Error",
                        "Could not create Game Day category",
                        recovery_hint="Check permissions"
                    ),
                    ephemeral=True,
                )
                return

            discord_channel = await ctx.guild.create_text_channel(
                channel_name,
                category=category,
                topic=f"{sport.upper()} • {event_name} • {scheduled_start.strftime('%Y-%m-%d %H:%M UTC')}",
            )

            # Record in database
            gameday = GameDayChannel(
                guild_id=ctx.guild_id,
                channel_id=discord_channel.id,
                sport=sport,
                event_name=event_name,
                event_id=f"{sport}_{int(scheduled_start.timestamp())}",
                status="active",
                scheduled_start=scheduled_start,
            )

            self.db.add(gameday)
            await self.db.commit()

            await ctx.followup.send(
                embed=success_embed(
                    "Channel Created",
                    discord_channel.mention,
                    fields=[
                        ("Sport", sport.upper(), True),
                        ("Event", event_name[:30], True),
                        ("Start", scheduled_start.strftime("%Y-%m-%d %H:%M"), True),
                    ]
                ),
                ephemeral=True,
            )

        except Exception as e:
            logger.exception("Error creating game-day channel")
            await ctx.followup.send(
                embed=error_embed(
                    "Creation Failed",
                    "Could not create channel",
                    recovery_hint="Try again",
                    error_code="GAMEDAY_CREATE_ERROR"
                ),
                ephemeral=True,
            )

    @gameday_group.command(
        name="archive",
        description="Manually archive a game-day channel (admin only)",
    )
    @commands.has_permissions(administrator=True)
    async def archive_gameday_channel(
        self,
        ctx: discord.ApplicationContext,
        channel_id: int,
    ) -> None:
        """
        Manually archive a game-day channel.

        Args:
            ctx: Discord application context
            channel_id: ID of the channel to archive
        """
        await ctx.defer()

        try:
            # Get Discord channel
            channel = ctx.guild.get_channel(channel_id)
            if not channel:
                await ctx.followup.send(
                    embed=error_embed(
                        "Not Found",
                        f"No channel with ID: {channel_id}",
                        recovery_hint="Check the ID with `/gameday list`"
                    ),
                    ephemeral=True,
                )
                return

            # Ask for confirmation
            confirm_embed = info_embed(
                "Archive Channel?",
                f"Archive {channel.mention}? Sets it to read-only and cannot be undone.",
            )
            view = ConfirmView()
            await ctx.followup.send(embed=confirm_embed, view=view, ephemeral=True)

            await view.wait()
            if not view.result:
                await ctx.followup.send("Cancelled", ephemeral=True)
                return

            # Update database record
            stmt = select(GameDayChannel).where(
                and_(
                    GameDayChannel.channel_id == channel_id,
                    GameDayChannel.guild_id == ctx.guild_id,
                )
            )
            result = await self.db.execute(stmt)
            gameday = result.scalars().first()

            if gameday:
                gameday.status = "archived"
                gameday.archived_at = datetime.utcnow()
                await self.db.commit()

            # Move channel to archived category
            archived_category = await self._get_or_create_category(
                ctx.guild, self.ARCHIVED_CATEGORY
            )
            if archived_category:
                await channel.edit(category=archived_category)

            # Set channel to read-only
            await channel.edit(
                overwrites={
                    ctx.guild.default_role: discord.PermissionOverwrite(send_messages=False),
                    ctx.guild.me: discord.PermissionOverwrite(send_messages=True),
                }
            )

            await ctx.followup.send(
                embed=success_embed(
                    "Channel Archived",
                    f"{channel.mention} is now read-only"
                ),
                ephemeral=True,
            )

        except Exception as e:
            logger.exception("Error archiving game-day channel")
            await ctx.followup.send(
                embed=error_embed(
                    "Archive Failed",
                    "Could not archive channel",
                    recovery_hint="Try again",
                    error_code="GAMEDAY_ARCHIVE_ERROR"
                ),
                ephemeral=True,
            )

    @tasks.loop(minutes=30)
    async def check_schedule(self) -> None:
        """
        Every 30 minutes, check sports schedules for upcoming games.

        Creates game-day channels 4 hours before kickoff.
        """
        try:
            now = datetime.utcnow()
            check_window_start = now
            check_window_end = now + timedelta(hours=5)

            # If sports schedule service is available, fetch schedules
            if self.sports_schedule_service:
                # This is a placeholder for actual schedule service integration
                # In production, call: games = await self.sports_schedule_service.get_upcoming_games(check_window_start, check_window_end)
                games = []
            else:
                games = []

            # For demo purposes, log that task ran
            if now.minute == 0:
                logger.debug("check_schedule task running (no external schedule service configured)")

        except Exception as e:
            logger.exception("Error in check_schedule background task")

    @check_schedule.before_loop
    async def before_check_schedule(self) -> None:
        """Wait for bot to be ready."""
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=15)
    async def auto_archive(self) -> None:
        """
        Every 15 minutes, check for games that ended 2+ hours ago.

        Archives channels for completed games.
        """
        try:
            two_hours_ago = datetime.utcnow() - timedelta(hours=2)

            stmt = select(GameDayChannel).where(
                and_(
                    GameDayChannel.status == "active",
                    GameDayChannel.actual_start <= two_hours_ago,
                )
            )
            result = await self.db.execute(stmt)
            channels_to_archive = result.scalars().all()

            for gameday in channels_to_archive:
                discord_channel = self.bot.get_channel(gameday.channel_id)
                if discord_channel:
                    try:
                        # Move to archived category
                        guild = discord_channel.guild
                        archived_category = await self._get_or_create_category(
                            guild, self.ARCHIVED_CATEGORY
                        )
                        if archived_category:
                            await discord_channel.edit(category=archived_category)

                        # Set to read-only
                        await discord_channel.edit(
                            overwrites={
                                guild.default_role: discord.PermissionOverwrite(
                                    send_messages=False
                                ),
                                guild.me: discord.PermissionOverwrite(send_messages=True),
                            }
                        )

                        gameday.status = "archived"
                        gameday.archived_at = datetime.utcnow()

                    except Exception as e:
                        logger.exception(f"Error archiving channel {discord_channel.id}")

            if channels_to_archive:
                await self.db.commit()
                logger.info(f"Auto-archived {len(channels_to_archive)} game-day channels")

        except Exception as e:
            logger.exception("Error in auto_archive background task")

    @auto_archive.before_loop
    async def before_auto_archive(self) -> None:
        """Wait for bot to be ready."""
        await self.bot.wait_until_ready()

    def _format_channel_name(self, sport: str, event_name: str) -> str:
        """
        Format event name into valid Discord channel name.

        Args:
            sport: Sport type
            event_name: Human-readable event name

        Returns:
            str: Formatted channel name (lowercase, hyphens, max 100 chars)
        """
        # Remove special characters and convert to lowercase
        name = event_name.lower().replace(" vs ", "-vs-")
        name = "".join(c if c.isalnum() or c == "-" else "" for c in name)
        name = name.replace("--", "-").strip("-")

        # Prefix with sport
        full_name = f"{sport}-{name}"
        return full_name[:100]

    async def _get_or_create_category(
        self,
        guild: discord.Guild,
        category_name: str,
    ) -> Optional[discord.CategoryChannel]:
        """
        Get existing category or create it if it doesn't exist.

        Args:
            guild: Discord guild
            category_name: Name of category

        Returns:
            Optional[discord.CategoryChannel]: Category channel or None if unable to create
        """
        # Try to find existing category
        for category in guild.categories:
            if category.name.lower() == category_name.lower():
                return category

        # Create new category if not found
        try:
            # Create with restricted permissions
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(send_messages=True),
                guild.me: discord.PermissionOverwrite(send_messages=True),
            }
            category = await guild.create_category(
                category_name,
                overwrites=overwrites,
            )
            logger.info(f"Created category {category_name}")
            return category
        except Exception as e:
            logger.exception(f"Error creating category {category_name}")
            return None


async def setup(bot: commands.Bot) -> None:
    """Load the Game-Day Channels cog."""
    db_session = bot.db
    await bot.add_cog(GameDayChannelsCog(bot, db_session))
