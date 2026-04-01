"""
One-Tap Tail Bot Cog.

Detects PrizePicks entry URLs, creates embeds with entry details,
and provides one-tap entry tailing via deeplinks.
"""

import logging
import re
from typing import Optional

import discord
from discord.ext import commands

from src.services.analytics import AnalyticsService
from src.services.prizepicks_api import PrizepicksAPIClient
from src.utils.deeplinks import DeeplinkGenerator
from src.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# Regex pattern to detect PrizePicks entry URLs
ENTRY_URL_PATTERN = re.compile(r"https?://(?:www\.)?app\.prizepicks\.com/entry/([a-zA-Z0-9-_]+)")

# Rate limiting: 5 entries per 60 seconds per channel
RATE_LIMIT_ENTRIES = 5
RATE_LIMIT_WINDOW = 60


class TailView(discord.ui.View):
    """View for tail entry button."""

    def __init__(
        self,
        entry_id: str,
        discord_user_id: int,
        deeplink_url: str,
        analytics: Optional[AnalyticsService] = None,
    ):
        """Initialize the view."""
        super().__init__(timeout=3600)  # 1 hour timeout
        self.entry_id = entry_id
        self.discord_user_id = discord_user_id
        self.deeplink_url = deeplink_url
        self.analytics = analytics
        self.tail_count = 0

    @discord.ui.button(label="Tail This Entry", style=discord.ButtonStyle.primary)
    async def tail_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ) -> None:
        """Handle tail button click."""
        try:
            # Emit analytics event
            if self.analytics:
                await self.analytics.emit_event(
                    "tail_click",
                    {
                        "discord_user_id": interaction.user.id,
                        "entry_id": self.entry_id,
                        "channel_id": interaction.channel_id,
                        "guild_id": interaction.guild_id,
                        "timestamp": discord.utils.utcnow().isoformat(),
                    },
                )

            # Update tail count
            self.tail_count += 1
            button.label = f"Tail ({self.tail_count})"

            # Send ephemeral response with deeplink
            embed = discord.Embed(
                title="Opening PrizePicks",
                description="Click the button below to open this entry in PrizePicks",
                color=discord.Color.green(),
            )

            view = discord.ui.View()
            view.add_item(
                discord.ui.Button(
                    label="Open Entry",
                    url=self.deeplink_url,
                    style=discord.ButtonStyle.link,
                )
            )

            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True,
            )

            logger.info(
                f"Tail click for entry {self.entry_id} by user {interaction.user.id}"
            )

        except Exception as e:
            logger.error(f"Error handling tail button click: {e}", exc_info=True)
            await interaction.response.send_message(
                "An error occurred. Please try again.",
                ephemeral=True,
            )


class TailBotCog(commands.Cog):
    """Cog for tail bot functionality."""

    def __init__(self, bot: commands.Bot):
        """Initialize the cog."""
        self.bot = bot
        self.prizepicks_client: PrizepicksAPIClient = bot.prizepicks_client
        self.analytics: Optional[AnalyticsService] = bot.analytics
        self.rate_limiter = RateLimiter()
        self.deeplink_gen = DeeplinkGenerator()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        Listen for messages with PrizePicks entry URLs.

        Args:
            message: Discord message object
        """
        # Ignore bot messages
        if message.author.bot:
            return

        # Ignore DMs
        if not message.guild:
            return

        try:
            # Find entry URLs in message
            matches = ENTRY_URL_PATTERN.findall(message.content)

            if not matches:
                return

            # Check rate limit per channel
            channel_key = f"channel_{message.channel.id}"
            if not self.rate_limiter.is_allowed(
                channel_key,
                RATE_LIMIT_ENTRIES,
                RATE_LIMIT_WINDOW,
            ):
                logger.debug(f"Rate limit exceeded for channel {message.channel.id}")
                return

            # Process each entry
            for entry_id in matches:
                await self._process_entry(
                    entry_id,
                    message.channel,
                    message.author.id,
                    message,
                )

        except Exception as e:
            logger.error(f"Error in on_message: {e}", exc_info=True)

    async def _process_entry(
        self,
        entry_id: str,
        channel: discord.TextChannel,
        user_id: int,
        original_message: discord.Message,
    ) -> None:
        """
        Process and display a PrizePicks entry.

        Args:
            entry_id: PrizePicks entry ID
            channel: Discord channel to post embed to
            user_id: Discord user ID who posted the entry
            original_message: Original message containing the URL
        """
        try:
            # Fetch entry details from API
            entry_data = await self.prizepicks_client.get_entry(entry_id)

            if not entry_data:
                logger.warning(f"Could not fetch entry data for {entry_id}")
                return

            # Create embed with entry details
            embed = self._create_entry_embed(entry_data)

            # Generate deeplink
            deeplink_url = self.deeplink_gen.generate_entry_link(
                entry_id=entry_id,
                discord_user_id=user_id,
                source="discord",
            )

            # Create view with tail button
            view = TailView(
                entry_id=entry_id,
                discord_user_id=user_id,
                deeplink_url=deeplink_url,
                analytics=self.analytics,
            )

            # Send embed with button
            await channel.send(embed=embed, view=view)

            # Emit analytics event
            if self.analytics:
                await self.analytics.emit_event(
                    "tail_to_entry",
                    {
                        "discord_user_id": user_id,
                        "entry_id": entry_id,
                        "channel_id": channel.id,
                        "guild_id": channel.guild.id,
                        "timestamp": discord.utils.utcnow().isoformat(),
                    },
                )

            logger.info(f"Entry {entry_id} processed and posted to {channel.id}")

        except Exception as e:
            logger.error(f"Error processing entry {entry_id}: {e}", exc_info=True)

    def _create_entry_embed(self, entry_data: dict) -> discord.Embed:
        """
        Create Discord embed from entry data.

        Args:
            entry_data: Entry data from PrizePicks API

        Returns:
            discord.Embed: Formatted embed
        """
        embed = discord.Embed(
            title="PrizePicks Entry",
            description=entry_data.get("title", "Custom Entry"),
            color=discord.Color.purple(),
        )

        # Add entry details
        if "projections" in entry_data and entry_data["projections"]:
            projections = entry_data["projections"]
            props_summary = self._format_projections(projections)
            embed.add_field(
                name="Props",
                value=props_summary,
                inline=False,
            )

        if "line" in entry_data:
            embed.add_field(
                name="Line",
                value=f"${entry_data['line']}",
                inline=True,
            )

        if "payout" in entry_data:
            embed.add_field(
                name="Payout",
                value=f"${entry_data['payout']}",
                inline=True,
            )

        # Add timestamp
        embed.timestamp = discord.utils.utcnow()
        embed.set_footer(text="PrizePicks")

        return embed

    def _format_projections(self, projections: list) -> str:
        """
        Format projections list into readable string.

        Args:
            projections: List of projection objects

        Returns:
            str: Formatted projections
        """
        lines = []
        for proj in projections[:5]:  # Limit to first 5 for readability
            player_name = proj.get("player_name", "Unknown")
            stat_type = proj.get("stat_type", "")
            line = proj.get("line", "")
            projection = proj.get("projection", "OVER" if proj.get("is_over") else "UNDER")

            lines.append(f"{player_name} {stat_type} {line} - {projection}")

        if len(projections) > 5:
            lines.append(f"... and {len(projections) - 5} more")

        return "\n".join(lines) if lines else "No projections"


async def setup(bot: commands.Bot) -> None:
    """Load the cog."""
    await bot.add_cog(TailBotCog(bot))
