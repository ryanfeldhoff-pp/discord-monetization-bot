"""
Game-Day Channels Cog (Pillar 3)

Auto-creates and archives game-day discussion channels based on sports schedules.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List

import discord
from discord.ext import commands, tasks
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.event_models import GameDayChannel

logger = logging.getLogger(__name__)


class GameDayChannelsCog(commands.Cog):
    """
    Game-Day Channels cog for auto-managed event channels.

    Features:
    - Auto-create channels 4 hours before game start (e.g., #nfl-chiefs-vs-bills)
    - Auto-archive channels 2 hours after game end
    - /gameday list — Today's game-day channels
    - /gameday create — Manually create a channel (admin)
    - /gameday archive — Manually archive a channel (admin)
    - Background task: poll sports schedule API every 30 minutes
    """

    CHANNEL_PREFIX = "🏟️"
    CREATE_HOURS_BEFORE = 4
    ARCHIVE_HOURS_AFTER = 2

    def __init__(
        self,
        bot: commands.Bot,
        db_session: AsyncSession,
        sports_schedule_service=None,  # TODO: implement schedule service
    ):
        self.bot = bot
        self.db = db_session
        self.schedule_service = sports_schedule_service
        self.manage_gameday_channels.start()

    def cog_unload(self):
        self.manage_gameday_channels.cancel()

    gameday_group = discord.SlashCommandGroup("gameday", "Game-day channels")

    @gameday_group.command(name="list", description="Today's game-day channels")
    async def gameday_list(self, ctx: discord.ApplicationContext) -> None:
        """List today's game-day channels."""
        await ctx.defer()

        try:
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)

            stmt = select(GameDayChannel).where(
                and_(
                    GameDayChannel.start_time >= today_start,
                    GameDayChannel.start_time < today_end,
                )
            ).order_by(GameDayChannel.start_time)

            result = await self.db.execute(stmt)
            channels = result.scalars().all()

            embed = discord.Embed(
                title="🏟️ Today's Game-Day Channels",
                color=0x8B5CF6,
            )

            if channels:
                for ch in channels:
                    status_emoji = {"scheduled": "🔜", "active": "🟢", "archived": "📦"}.get(ch.status, "❓")
                    embed.add_field(
                        name=f"{status_emoji} {ch.event_name}",
                        value=(
                            f"Sport: {ch.sport}\n"
                            f"Start: <t:{int(ch.start_time.timestamp())}:t>\n"
                            f"Channel: <#{ch.channel_id}>"
                        ),
                        inline=True,
                    )
            else:
                embed.description = "No game-day channels scheduled for today."

            await ctx.respond(embed=embed)

        except Exception as e:
            logger.error(f"Error listing gameday channels: {e}")
            await ctx.respond("Failed to load game-day channels.", ephemeral=True)

    @gameday_group.command(name="create", description="Create a game-day channel (admin)")
    @discord.option(name="sport", description="Sport (NFL, NBA, MLB, etc.)", required=True)
    @discord.option(name="event_name", description="Event name (e.g., Chiefs vs Bills)", required=True)
    @discord.option(name="hours_until_start", description="Hours until game starts", required=False, default=4)
    @commands.has_permissions(manage_channels=True)
    async def gameday_create(
        self,
        ctx: discord.ApplicationContext,
        sport: str,
        event_name: str,
        hours_until_start: int = 4,
    ) -> None:
        """Manually create a game-day channel."""
        await ctx.defer(ephemeral=True)

        try:
            guild = ctx.guild
            channel_name = f"{sport.lower()}-{event_name.lower().replace(' ', '-').replace('vs', 'vs')}"
            channel_name = channel_name[:100]  # Discord limit

            # Find or create category
            category = discord.utils.get(guild.categories, name="Game Day")
            if not category:
                category = await guild.create_category("Game Day")

            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                topic=f"🏟️ {sport.upper()} — {event_name} | Auto-archives after the game",
            )

            start_time = datetime.utcnow() + timedelta(hours=hours_until_start)

            gameday = GameDayChannel(
                channel_id=channel.id,
                sport=sport.upper(),
                event_name=event_name,
                start_time=start_time,
                status="active",
            )
            self.db.add(gameday)
            await self.db.flush()

            # Post welcome message
            welcome = discord.Embed(
                title=f"🏟️ {event_name}",
                description=(
                    f"**{sport.upper()}** game-day discussion!\n\n"
                    f"Game starts <t:{int(start_time.timestamp())}:R>\n"
                    "Share your picks, reactions, and more here."
                ),
                color=0x8B5CF6,
            )
            await channel.send(embed=welcome)

            await ctx.respond(
                f"✅ Created <#{channel.id}> for **{event_name}**",
                ephemeral=True,
            )
            logger.info(f"Created gameday channel #{channel.id} for {event_name}")

        except Exception as e:
            logger.error(f"Error creating gameday channel: {e}")
            await ctx.respond("Failed to create channel.", ephemeral=True)

    @gameday_group.command(name="archive", description="Archive a game-day channel (admin)")
    @discord.option(name="channel", description="Channel to archive", type=discord.TextChannel, required=True)
    @commands.has_permissions(manage_channels=True)
    async def gameday_archive(self, ctx: discord.ApplicationContext, channel: discord.TextChannel) -> None:
        """Manually archive a game-day channel."""
        await ctx.defer(ephemeral=True)

        try:
            # Update database record
            stmt = select(GameDayChannel).where(GameDayChannel.channel_id == channel.id)
            result = await self.db.execute(stmt)
            gameday = result.scalar_one_or_none()

            if gameday:
                gameday.status = "archived"
                gameday.archived_at = datetime.utcnow()
                await self.db.flush()

            # Move to archive category or delete
            archive_category = discord.utils.get(ctx.guild.categories, name="Archived Games")
            if not archive_category:
                archive_category = await ctx.guild.create_category("Archived Games")

            await channel.edit(
                category=archive_category,
                overwrites={
                    ctx.guild.default_role: discord.PermissionOverwrite(send_messages=False),
                },
            )

            await ctx.respond(f"✅ Archived {channel.mention}", ephemeral=True)
            logger.info(f"Archived gameday channel #{channel.id}")

        except Exception as e:
            logger.error(f"Error archiving channel: {e}")
            await ctx.respond("Failed to archive channel.", ephemeral=True)

    @tasks.loop(minutes=30)
    async def manage_gameday_channels(self) -> None:
        """Background task: create upcoming and archive expired game-day channels."""
        try:
            now = datetime.utcnow()

            # Auto-archive: channels where game ended 2+ hours ago
            stmt = select(GameDayChannel).where(
                and_(
                    GameDayChannel.status == "active",
                    GameDayChannel.end_time.isnot(None),
                    GameDayChannel.end_time <= now - timedelta(hours=self.ARCHIVE_HOURS_AFTER),
                )
            )
            result = await self.db.execute(stmt)
            to_archive = result.scalars().all()

            for gameday in to_archive:
                try:
                    for guild in self.bot.guilds:
                        channel = guild.get_channel(gameday.channel_id)
                        if channel:
                            archive_cat = discord.utils.get(guild.categories, name="Archived Games")
                            if not archive_cat:
                                archive_cat = await guild.create_category("Archived Games")
                            await channel.edit(
                                category=archive_cat,
                                overwrites={
                                    guild.default_role: discord.PermissionOverwrite(send_messages=False),
                                },
                            )
                    gameday.status = "archived"
                    gameday.archived_at = now
                    logger.info(f"Auto-archived gameday channel #{gameday.channel_id}")
                except Exception as e:
                    logger.error(f"Error auto-archiving channel {gameday.channel_id}: {e}")

            if to_archive:
                await self.db.flush()

            # TODO: Auto-create channels from sports schedule API
            # When schedule_service is available:
            # 1. Fetch today's games from /api/schedule
            # 2. For games starting within CREATE_HOURS_BEFORE hours
            # 3. Check if channel already exists
            # 4. Create channel and DB record

        except Exception as e:
            logger.error(f"Error in gameday channel management: {e}")

    @manage_gameday_channels.before_loop
    async def before_manage(self) -> None:
        await self.bot.wait_until_ready()


def setup(bot: commands.Bot) -> None:
    pass  # Loaded via bot.add_cog() in main.py
