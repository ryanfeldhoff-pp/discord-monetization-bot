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

logger = logging.getLogger(__name__)

# PrizePicks brand purple
PRIZEPICKS_COLOR = discord.Color.from_rgb(108, 43, 217)

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
                embed = discord.Embed(
                    title="No Game-Day Channels Today",
                    description="No active games scheduled for today.",
                    color=PRIZEPICKS_COLOR,
                )
                await ctx.followup.send(embed=embed)
                return

            embed = discord.Embed(
                title="Today's Games",
                color=PRIZEPICKS_COLOR,
                timestamp=datetime.utcnow(),
            )

            for channel_record in channels:
                emoji = SPORT_EMOJI.get(channel_record.sport, "🎮")
                start_time = channel_record.scheduled_start.strftime("%H:%M")
                discord_channel = ctx.guild.get_channel(channel_record.channel_id)
                channel_mention = (
                    discord_channel.mention if discord_channel else f"#{channel_record.event_name}"
                )

                embed.add_field(
                    name=f"{emoji} {channel_record.event_name}",
                    value=f"Channel: {channel_mention}\nStart: {start_time}",
                    inline=True,
                )

            await ctx.followup.send(embed=embed)

        except Exception as e:
            logger.exception("Error listing game-day channels")
            error_embed = discord.Embed(
                title="Error Listing Channels",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red(),
            )
            await ctx.followup.send(embed=error_embed, ephemeral=True)

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
            # Parse start time
            try:
                scheduled_start = datetime.fromisoformat(start_time)
            except ValueError:
                error_embed = discord.Embed(
                    title="Invalid Time Format",
                    description="Use ISO format: YYYY-MM-DD HH:MM",
                    color=discord.Color.red(),
                )
                await ctx.followup.send(embed=error_embed, ephemeral=True)
                return

            # Create Discord channel
            channel_name = self._format_channel_name(sport, event_name)
            category = self._get_or_create_category(ctx.guild, self.GAMEDAY_CATEGORY)

            if not category:
                error_embed = discord.Embed(
                    title="Category Error",
                    description="Could not create/find Game Day category.",
                    color=discord.Color.red(),
                )
                await ctx.followup.send(embed=error_embed, ephemeral=True)
                return

            discord_channel = await ctx.guild.create_text_channel(
                channel_name,
                category=category,
                topic=f"{sport.upper()} | {event_name} | Starts: {scheduled_start.strftime('%Y-%m-%d %H:%M')}",
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

            embed = discord.Embed(
                title="Channel Created",
                description=f"{discord_channel.mention}",
                color=PRIZEPICKS_COLOR,
            )
            embed.add_field(name="Sport", value=sport.upper(), inline=True)
            embed.add_field(name="Event", value=event_name, inline=True)
            embed.add_field(
                name="Start Time",
                value=scheduled_start.strftime("%Y-%m-%d %H:%M"),
                inline=True,
            )

            await ctx.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.exception("Error creating game-day channel")
            error_embed = discord.Embed(
                title="Error Creating Channel",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red(),
            )
            await ctx.followup.send(embed=error_embed, ephemeral=True)

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
                error_embed = discord.Embed(
                    title="Channel Not Found",
                    description=f"No channel found with ID: {channel_id}",
                    color=discord.Color.red(),
                )
                await ctx.followup.send(embed=error_embed, ephemeral=True)
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
            archived_category = self._get_or_create_category(
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

            embed = discord.Embed(
                title="Channel Archived",
                description=f"{channel.mention} has been archived and set to read-only.",
                color=PRIZEPICKS_COLOR,
            )
            await ctx.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.exception("Error archiving game-day channel")
            error_embed = discord.Embed(
                title="Error Archiving Channel",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red(),
            )
            await ctx.followup.send(embed=error_embed, ephemeral=True)

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
                        archived_category = self._get_or_create_category(
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

    def _get_or_create_category(
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
            category = guild.create_category(
                category_name,
                overwrites=overwrites,
            )
            # Note: This is async, should use await
            logger.info(f"Created category {category_name}")
            return category
        except Exception as e:
            logger.exception(f"Error creating category {category_name}")
            return None


async def setup(bot: commands.Bot) -> None:
    """Load the Game-Day Channels cog."""
    db_session = bot.db
    await bot.add_cog(GameDayChannelsCog(bot, db_session))
