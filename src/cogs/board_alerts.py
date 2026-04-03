"""
Board Drop Notification Bot Cog.

Monitors PrizePicks projections API for new drops and line movements,
sends formatted alerts to subscribed users in sport-specific channels.
"""

import json
import logging
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands, tasks

from src.models.database import Database, Subscription
from src.services.analytics import AnalyticsService
from src.services.prizepicks_api import PrizepicksAPIClient
from src.utils.embeds import info_embed, error_embed, empty_state_embed, success_embed
from src.utils.views import UnsubscribeView

logger = logging.getLogger(__name__)

# Polling interval (seconds)
POLL_INTERVAL = 60

# Threshold for line movement alerts (percentage)
LINE_MOVEMENT_THRESHOLD = 5

# Sports-to-channel mapping
SPORTS_CHANNELS = {
    "NFL": "nfl-alerts",
    "NBA": "nba-alerts",
    "NHL": "nhl-alerts",
    "MLB": "mlb-alerts",
    "COLLEGE_FOOTBALL": "cfb-alerts",
    "COLLEGE_BASKETBALL": "cbb-alerts",
    "SOCCER": "soccer-alerts",
    "MMA": "mma-alerts",
}


class BoardAlertsCog(commands.Cog):
    """Cog for board drop alerts."""

    def __init__(self, bot: commands.Bot):
        """Initialize the cog."""
        self.bot = bot
        self.prizepicks_client: PrizepicksAPIClient = bot.prizepicks_client
        self.analytics: Optional[AnalyticsService] = bot.analytics
        self.db: Optional[Database] = None
        self.projection_snapshots: dict = {}
        self.alert_loop.start()

    async def cog_load(self) -> None:
        """Initialize cog resources."""
        self.db = await Database.create()
        logger.info("BoardAlertsCog loaded")

    async def cog_unload(self) -> None:
        """Clean up cog resources."""
        self.alert_loop.cancel()
        if self.db:
            await self.db.close()

    @commands.slash_command(
        name="subscribe",
        description="Subscribe to board drop alerts for a sport",
    )
    async def subscribe_alerts(
        self,
        ctx: discord.ApplicationContext,
        sport: discord.Option(
            str,
            description="Sport to subscribe to",
            choices=list(SPORTS_CHANNELS.keys()),
        ),
    ) -> None:
        """
        Subscribe to board drop alerts.

        Args:
            ctx: Discord application context
            sport: Sport to subscribe to
        """
        try:
            if not self.db:
                embed = error_embed(
                    "Database Error",
                    "Database not available",
                    recovery_hint="Please try again",
                    error_code="DB_UNAVAILABLE"
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            # Check if already subscribed
            existing = await self.db.get_subscription(ctx.author.id, sport)
            if existing:
                embed = info_embed(
                    "Already Subscribed",
                    f"You're already subscribed to {sport} alerts!",
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            # Create subscription
            await self.db.create_subscription(
                discord_user_id=ctx.author.id,
                sport=sport,
                quiet_hours_start=None,
                quiet_hours_end=None,
            )

            # Emit analytics event
            if self.analytics:
                await self.analytics.emit_event(
                    "subscription_created",
                    {
                        "discord_user_id": ctx.author.id,
                        "sport": sport,
                        "guild_id": ctx.guild.id,
                        "timestamp": discord.utils.utcnow().isoformat(),
                    },
                )

            embed = success_embed(
                f"{sport} Alerts Enabled",
                "You'll receive notifications when new boards drop.",
            )
            await ctx.respond(embed=embed, ephemeral=True)
            logger.info(f"User {ctx.author.id} subscribed to {sport}")

        except Exception as e:
            logger.error(f"Error in subscribe command: {e}", exc_info=True)
            embed = error_embed(
                "Subscription Failed",
                "An error occurred while subscribing",
                recovery_hint="Please try again in a moment",
                error_code="SUBSCRIBE_ERROR"
            )
            await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(
        name="unsubscribe",
        description="Unsubscribe from board drop alerts",
    )
    async def unsubscribe_alerts(
        self,
        ctx: discord.ApplicationContext,
        sport: discord.Option(
            str,
            description="Sport to unsubscribe from",
            choices=list(SPORTS_CHANNELS.keys()),
        ),
    ) -> None:
        """
        Unsubscribe from board drop alerts.

        Args:
            ctx: Discord application context
            sport: Sport to unsubscribe from
        """
        try:
            if not self.db:
                embed = error_embed(
                    "Database Error",
                    "Database not available",
                    recovery_hint="Please try again",
                    error_code="DB_UNAVAILABLE"
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            # Check if subscribed
            subscription = await self.db.get_subscription(ctx.author.id, sport)
            if not subscription:
                embed = info_embed(
                    "Not Subscribed",
                    f"You're not subscribed to {sport} alerts.",
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            # Delete subscription
            await self.db.delete_subscription(ctx.author.id, sport)

            embed = success_embed(
                f"{sport} Alerts Disabled",
                "You've been unsubscribed from these alerts."
            )
            await ctx.respond(embed=embed, ephemeral=True)
            logger.info(f"User {ctx.author.id} unsubscribed from {sport}")

        except Exception as e:
            logger.error(f"Error in unsubscribe command: {e}", exc_info=True)
            embed = error_embed(
                "Unsubscribe Failed",
                "An error occurred while unsubscribing",
                recovery_hint="Please try again in a moment",
                error_code="UNSUBSCRIBE_ERROR"
            )
            await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(
        name="mysubs",
        description="View your active subscriptions",
    )
    async def list_subscriptions(self, ctx: discord.ApplicationContext) -> None:
        """
        List user's active subscriptions.

        Args:
            ctx: Discord application context
        """
        try:
            if not self.db:
                embed = error_embed(
                    "Database Error",
                    "Database not available",
                    recovery_hint="Please try again",
                    error_code="DB_UNAVAILABLE"
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            subscriptions = await self.db.get_user_subscriptions(ctx.author.id)

            if not subscriptions:
                embed = empty_state_embed(
                    "Your Subscriptions",
                    "You're not subscribed to any sports yet",
                    ["/subscribe", "/mysubs"]
                )
            else:
                subs_text = "\n".join(
                    [f"• {sub.sport}" for sub in subscriptions]
                )
                embed = info_embed(
                    "Your Subscriptions",
                    subs_text,
                )

            await ctx.respond(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in mysubs command: {e}", exc_info=True)
            embed = error_embed(
                "Subscription Lookup Failed",
                "An error occurred while retrieving your subscriptions",
                recovery_hint="Please try again in a moment",
                error_code="SUBS_LIST_ERROR"
            )
            await ctx.respond(embed=embed, ephemeral=True)

    @tasks.loop(seconds=POLL_INTERVAL)
    async def alert_loop(self) -> None:
        """
        Main polling loop for board changes.

        Runs every POLL_INTERVAL seconds to:
        1. Fetch current projections
        2. Detect new projections
        3. Detect line movements
        4. Send alerts to subscribers
        """
        try:
            if not self.db:
                return

            # Fetch current projections
            # TODO: Confirm /projections endpoint parameters with backend team
            projections = await self.prizepicks_client.get_projections()

            if not projections:
                logger.warning("Failed to fetch projections")
                return

            # Group by sport
            by_sport = {}
            for proj in projections:
                sport = proj.get("sport", "UNKNOWN")
                if sport not in by_sport:
                    by_sport[sport] = []
                by_sport[sport].append(proj)

            # Detect changes and send alerts
            for sport, sport_projections in by_sport.items():
                await self._check_sport_changes(sport, sport_projections)

        except Exception as e:
            logger.error(f"Error in alert loop: {e}", exc_info=True)

    @alert_loop.before_loop
    async def before_alert_loop(self) -> None:
        """Wait for bot to be ready."""
        await self.bot.wait_until_ready()

    async def _check_sport_changes(self, sport: str, projections: list) -> None:
        """
        Check for changes in sport projections.

        Args:
            sport: Sport name
            projections: List of current projections
        """
        try:
            snapshot_key = f"sport_{sport}"

            # Get previous snapshot
            previous_snapshot = self.projection_snapshots.get(snapshot_key, {})
            previous_projections = json.loads(
                previous_snapshot.get("data", "[]")
            ) if previous_snapshot else []

            # Store current snapshot
            self.projection_snapshots[snapshot_key] = {
                "data": json.dumps(projections),
                "timestamp": discord.utils.utcnow().isoformat(),
            }

            # Detect new projections
            new_projs = self._detect_new_projections(previous_projections, projections)

            # Detect line movements
            moved_projs = self._detect_line_movements(previous_projections, projections)

            # Get subscribers
            subscribers = await self.db.get_sport_subscribers(sport)

            if not subscribers:
                return

            # Send alerts
            for subscriber in subscribers:
                # Check quiet hours
                if self._is_in_quiet_hours(subscriber):
                    continue

                # Send alert via DM
                try:
                    user = await self.bot.fetch_user(subscriber.discord_user_id)
                    if not user:
                        continue

                    # Create alert embed
                    fields = []

                    if new_projs:
                        new_text = "\n".join(
                            [f"• {p['player_name']} {p['stat_type']}" for p in new_projs[:5]]
                        )
                        fields.append((f"New Props ({len(new_projs)})", new_text, False))

                    if moved_projs:
                        moved_text = "\n".join(
                            [
                                f"• {p['player_name']} {p['stat_type']}: "
                                f"{p['old_line']} → {p['new_line']}"
                                for p in moved_projs[:5]
                            ]
                        )
                        fields.append((f"Line Movements ({len(moved_projs)})", moved_text, False))

                    embed = info_embed(
                        f"{sport} Board Update",
                        "New projections and line movements detected",
                        fields
                    )

                    # Add unsubscribe button
                    view = UnsubscribeView(subscriber.discord_user_id, sport)

                    # Add footer with subscription info
                    embed.add_field(
                        name="Manage Subscriptions",
                        value=f"You're subscribed to {sport}. Use `/alerts manage` to adjust",
                        inline=False
                    )

                    await user.send(embed=embed, view=view)

                    # Emit analytics event
                    if self.analytics:
                        await self.analytics.emit_event(
                            "board_alert_sent",
                            {
                                "discord_user_id": subscriber.discord_user_id,
                                "sport": sport,
                                "new_count": len(new_projs),
                                "moved_count": len(moved_projs),
                                "timestamp": discord.utils.utcnow().isoformat(),
                            },
                        )

                except discord.NotFound:
                    logger.warning(f"User {subscriber.discord_user_id} not found")
                except Exception as e:
                    logger.error(f"Error sending alert: {e}")

        except Exception as e:
            logger.error(f"Error checking sport changes: {e}", exc_info=True)

    def _detect_new_projections(
        self,
        previous: list,
        current: list,
    ) -> list:
        """
        Detect newly added projections.

        Args:
            previous: Previous projections
            current: Current projections

        Returns:
            list: New projections
        """
        previous_ids = {p.get("id") for p in previous}
        return [p for p in current if p.get("id") not in previous_ids]

    def _detect_line_movements(
        self,
        previous: list,
        current: list,
    ) -> list:
        """
        Detect significant line movements.

        Args:
            previous: Previous projections
            current: Current projections

        Returns:
            list: Projections with significant movement
        """
        previous_map = {p.get("id"): p for p in previous}
        moved = []

        for curr in current:
            proj_id = curr.get("id")
            prev = previous_map.get(proj_id)

            if not prev:
                continue

            old_line = float(prev.get("line", 0))
            new_line = float(curr.get("line", 0))

            if old_line == 0:
                continue

            movement_pct = abs((new_line - old_line) / old_line * 100)

            if movement_pct >= LINE_MOVEMENT_THRESHOLD:
                moved.append({
                    "id": proj_id,
                    "player_name": curr.get("player_name"),
                    "stat_type": curr.get("stat_type"),
                    "old_line": old_line,
                    "new_line": new_line,
                    "movement_pct": movement_pct,
                })

        return moved

    def _is_in_quiet_hours(self, subscription: Subscription) -> bool:
        """
        Check if current time is within quiet hours.

        Args:
            subscription: User subscription

        Returns:
            bool: True if in quiet hours
        """
        if not subscription.quiet_hours_start or not subscription.quiet_hours_end:
            return False

        now = datetime.now().time()
        start = subscription.quiet_hours_start
        end = subscription.quiet_hours_end

        if start <= end:
            return start <= now <= end
        else:
            return now >= start or now <= end


async def setup(bot: commands.Bot) -> None:
    """Load the cog."""
    await bot.add_cog(BoardAlertsCog(bot))
