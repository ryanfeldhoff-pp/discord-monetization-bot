"""
Referral Tracking Cog

Handles referral code generation, sharing, and performance tracking.
Core functionality for the Referral Amplifier system (Pillar 4).
"""

import logging
from datetime import datetime
from typing import Optional
import secrets
import qrcode
from io import BytesIO

import discord
from discord.ext import commands

from src.models.referral_models import ReferralCode
from src.services.referral_manager import ReferralManager

logger = logging.getLogger(__name__)

# PrizePicks brand color
PRIZEPICKS_PURPLE = 0x6C2BD9


class ReferralCodeEmbed:
    """Helper class to generate referral code embeds."""

    @staticmethod
    def create_code_embed(
        user: discord.User,
        code: str,
        referral_url: str,
        stats: dict,
        is_ambassador: bool = False,
    ) -> discord.Embed:
        """
        Create embed showing referral code and link.

        Args:
            user: Discord user
            code: Referral code
            referral_url: Full referral URL
            stats: Dictionary with referral stats
            is_ambassador: Whether user is an ambassador

        Returns:
            discord.Embed: Formatted embed
        """
        embed = discord.Embed(
            title="Your Referral Code" + (" (Ambassador)" if is_ambassador else ""),
            description=f"Share your code to earn rewards when friends sign up!",
            color=PRIZEPICKS_PURPLE,
            timestamp=datetime.utcnow(),
        )

        # Code and URL
        embed.add_field(
            name="Your Code",
            value=f"`{code}`",
            inline=False,
        )

        embed.add_field(
            name="Your Link",
            value=f"[{referral_url}]({referral_url})",
            inline=False,
        )

        # Stats
        embed.add_field(
            name="Total Referrals",
            value=f"**{stats.get('total_referrals', 0)}**",
            inline=True,
        )

        embed.add_field(
            name="FTDs",
            value=f"**{stats.get('total_ftds', 0)}**",
            inline=True,
        )

        embed.add_field(
            name="Earnings",
            value=f"**${stats.get('total_earnings', 0) / 100:.2f}**",
            inline=True,
        )

        # QR Code placeholder
        embed.add_field(
            name="QR Code",
            value="📱 Share your link in social media for easy scanning!",
            inline=False,
        )

        embed.set_thumbnail(url=user.avatar.url if user.avatar else "")
        embed.set_footer(text="PrizePicks Community")

        return embed


class ReferralStatsEmbed:
    """Helper class to generate referral stats embeds."""

    @staticmethod
    def create_stats_embed(user: discord.User, stats: dict) -> discord.Embed:
        """
        Create detailed stats embed with progress bars.

        Args:
            user: Discord user
            stats: Dictionary with referral stats

        Returns:
            discord.Embed: Formatted embed
        """
        embed = discord.Embed(
            title=f"Referral Stats - {user.name}",
            description="Your referral performance at a glance",
            color=PRIZEPICKS_PURPLE,
            timestamp=datetime.utcnow(),
        )

        total_refs = stats.get("total_referrals", 0)
        total_ftds = stats.get("total_ftds", 0)
        conversion_rate = (
            (total_ftds / total_refs * 100) if total_refs > 0 else 0
        )

        # Key metrics
        embed.add_field(
            name="Total Referrals",
            value=f"**{total_refs}**",
            inline=True,
        )

        embed.add_field(
            name="First-Time Depositors (FTDs)",
            value=f"**{total_ftds}**",
            inline=True,
        )

        embed.add_field(
            name="Conversion Rate",
            value=f"**{conversion_rate:.1f}%**",
            inline=True,
        )

        # Progress bars toward milestones
        milestones = [
            (5, "5 Referrals"),
            (10, "10 FTDs"),
            (25, "25 Referrals"),
            (50, "50 FTDs"),
        ]

        progress_text = ""
        for target, label in milestones:
            current = total_refs if "Referral" in label else total_ftds
            percentage = min(100, int((current / target) * 100))
            filled = int(percentage / 10)
            bar = "▓" * filled + "░" * (10 - filled)
            progress_text += f"{label}: {bar} {percentage}%\n"

        embed.add_field(
            name="Progress to Milestones",
            value=progress_text,
            inline=False,
        )

        # Earnings
        earnings = stats.get("total_earnings", 0)
        embed.add_field(
            name="Total Earnings",
            value=f"**${earnings / 100:.2f}**",
            inline=False,
        )

        embed.set_thumbnail(url=user.avatar.url if user.avatar else "")
        embed.set_footer(text="PrizePicks Community")

        return embed


class ReferralLeaderboardEmbed:
    """Helper class to generate leaderboard embeds."""

    @staticmethod
    def create_leaderboard_embed(
        leaderboard: list,
        period: str = "all-time",
    ) -> discord.Embed:
        """
        Create top referrers leaderboard embed.

        Args:
            leaderboard: List of top referrer dicts
            period: Time period for leaderboard

        Returns:
            discord.Embed: Formatted embed
        """
        embed = discord.Embed(
            title=f"Top Referrers - {period.title()}",
            description="Community's most active referral ambassadors",
            color=PRIZEPICKS_PURPLE,
            timestamp=datetime.utcnow(),
        )

        medals = ["🥇", "🥈", "🥉"]
        leaderboard_text = ""

        for idx, entry in enumerate(leaderboard[:25]):
            medal = medals[idx] if idx < 3 else f"#{idx + 1}"
            username = entry.get("username", f"User {entry.get('discord_user_id')}")
            ftds = entry.get("total_ftds", 0)
            earnings = entry.get("total_earnings", 0)

            leaderboard_text += (
                f"{medal} **{username}** - "
                f"{ftds} FTDs • ${earnings / 100:.2f}\n"
            )

        if leaderboard_text:
            embed.description = leaderboard_text
        else:
            embed.description = "No referral data yet. Be the first to start referring!"

        embed.set_footer(text="PrizePicks Community")

        return embed


class ReferralTrackingCog(commands.Cog):
    """
    Referral tracking and code management cog.

    Features:
    - Generate and manage referral codes
    - View referral performance
    - Community leaderboard
    - Shareable referral links
    """

    def __init__(self, bot: commands.Bot, referral_manager: ReferralManager):
        """
        Initialize Referral Tracking cog.

        Args:
            bot: Discord bot instance
            referral_manager: ReferralManager service instance
        """
        self.bot = bot
        self.referral_manager = referral_manager

    async def cog_load(self) -> None:
        """Initialize cog resources."""
        logger.info("ReferralTrackingCog loaded")

    async def cog_unload(self) -> None:
        """Clean up cog resources."""
        logger.info("ReferralTrackingCog unloaded")

    @commands.slash_command(
        name="referral",
        description="Manage your referral code and links",
    )
    @discord.option(
        name="action",
        description="What to do with your referral code",
        choices=["code", "stats", "leaderboard", "link"],
        default="code",
    )
    async def referral_command(
        self,
        ctx: discord.ApplicationContext,
        action: str = "code",
    ) -> None:
        """
        Manage referral codes and view performance.

        Args:
            ctx: Discord application context
            action: Subcommand ("code", "stats", "leaderboard", or "link")
        """
        await ctx.defer()

        try:
            user_id = ctx.author.id

            if action == "code":
                await self._show_referral_code(ctx, user_id)
            elif action == "stats":
                await self._show_referral_stats(ctx, user_id)
            elif action == "leaderboard":
                await self._show_leaderboard(ctx)
            elif action == "link":
                await self._show_referral_link(ctx, user_id)
            else:
                await ctx.respond(
                    "Invalid action. Please choose: code, stats, leaderboard, or link.",
                    ephemeral=True,
                )

        except Exception as e:
            logger.error(f"Error in referral command: {e}", exc_info=True)
            await ctx.respond(
                "An error occurred. Please try again later.",
                ephemeral=True,
            )

    async def _show_referral_code(
        self,
        ctx: discord.ApplicationContext,
        user_id: int,
    ) -> None:
        """
        Generate or display user's referral code.

        Args:
            ctx: Discord application context
            user_id: Discord user ID
        """
        try:
            # Check if code exists
            referral_data = await self.referral_manager.get_or_create_referral_code(
                user_id
            )

            if not referral_data:
                await ctx.respond(
                    "You need to link your PrizePicks account first to get a referral code.",
                    ephemeral=True,
                )
                return

            code = referral_data.get("code")
            url = referral_data.get("url")
            is_ambassador = referral_data.get("is_ambassador", False)

            # Get stats
            stats = await self.referral_manager.get_referral_stats(user_id)

            # Create and send embed
            embed = ReferralCodeEmbed.create_code_embed(
                ctx.author,
                code,
                url,
                stats,
                is_ambassador,
            )

            await ctx.respond(embed=embed)
            logger.info(f"Displayed referral code for user {user_id}")

        except Exception as e:
            logger.error(f"Error showing referral code: {e}", exc_info=True)
            await ctx.respond(
                "Error retrieving your referral code. Please try again.",
                ephemeral=True,
            )

    async def _show_referral_stats(
        self,
        ctx: discord.ApplicationContext,
        user_id: int,
    ) -> None:
        """
        Display user's referral performance stats.

        Args:
            ctx: Discord application context
            user_id: Discord user ID
        """
        try:
            stats = await self.referral_manager.get_referral_stats(user_id)

            if not stats or stats.get("total_referrals") == 0:
                embed = discord.Embed(
                    title="No Referral Data Yet",
                    description="Start sharing your referral code to earn rewards!",
                    color=PRIZEPICKS_PURPLE,
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            # Create and send embed
            embed = ReferralStatsEmbed.create_stats_embed(ctx.author, stats)
            await ctx.respond(embed=embed)
            logger.info(f"Displayed referral stats for user {user_id}")

        except Exception as e:
            logger.error(f"Error showing referral stats: {e}", exc_info=True)
            await ctx.respond(
                "Error retrieving your stats. Please try again.",
                ephemeral=True,
            )

    async def _show_leaderboard(
        self,
        ctx: discord.ApplicationContext,
    ) -> None:
        """
        Display top referrers leaderboard.

        Args:
            ctx: Discord application context
        """
        try:
            leaderboard = (
                await self.referral_manager.get_top_referrers(
                    limit=25,
                )
            )

            if not leaderboard:
                embed = discord.Embed(
                    title="Leaderboard",
                    description="No referral data available yet.",
                    color=PRIZEPICKS_PURPLE,
                )
                await ctx.respond(embed=embed)
                return

            # Create and send embed
            embed = ReferralLeaderboardEmbed.create_leaderboard_embed(
                leaderboard,
                period="all-time",
            )
            await ctx.respond(embed=embed)
            logger.info("Displayed referral leaderboard")

        except Exception as e:
            logger.error(f"Error showing leaderboard: {e}", exc_info=True)
            await ctx.respond(
                "Error retrieving leaderboard. Please try again.",
                ephemeral=True,
            )

    async def _show_referral_link(
        self,
        ctx: discord.ApplicationContext,
        user_id: int,
    ) -> None:
        """
        Display shareable referral link in copy-friendly format.

        Args:
            ctx: Discord application context
            user_id: Discord user ID
        """
        try:
            referral_data = await self.referral_manager.get_or_create_referral_code(
                user_id
            )

            if not referral_data:
                await ctx.respond(
                    "You need to link your PrizePicks account first.",
                    ephemeral=True,
                )
                return

            code = referral_data.get("code")
            url = referral_data.get("url")

            embed = discord.Embed(
                title="Your Referral Link",
                description="Click the button below or copy the link to share",
                color=PRIZEPICKS_PURPLE,
                timestamp=datetime.utcnow(),
            )

            # Display in code block for easy copying
            embed.add_field(
                name="Copy-Friendly Link",
                value=f"```\n{url}\n```",
                inline=False,
            )

            embed.add_field(
                name="Or Share Your Code",
                value=f"Code: `{code}`\nAsk friends to enter it during signup!",
                inline=False,
            )

            # Button for direct opening
            view = discord.ui.View()
            view.add_item(
                discord.ui.Button(
                    label="Open Link",
                    url=url,
                    style=discord.ButtonStyle.link,
                )
            )

            embed.set_footer(text="PrizePicks Community")
            await ctx.respond(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Error showing referral link: {e}", exc_info=True)
            await ctx.respond(
                "Error retrieving your link. Please try again.",
                ephemeral=True,
            )

    @commands.Cog.listener()
    async def on_account_linked(self, user_id: int, prizepicks_user_id: str) -> None:
        """
        Listen for account link events and auto-generate referral codes.

        Args:
            user_id: Discord user ID
            prizepicks_user_id: PrizePicks user ID
        """
        try:
            # Auto-generate referral code for newly linked users
            referral_data = await self.referral_manager.get_or_create_referral_code(
                user_id
            )
            logger.info(
                f"Auto-generated referral code for newly linked user {user_id}"
            )

        except Exception as e:
            logger.error(f"Error auto-generating referral code: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_tail_event(self, user_id: int, tail_data: dict) -> None:
        """
        Listen for tail events to track referral attribution.

        Args:
            user_id: User performing the tail
            tail_data: Tail event data including referral code if applicable
        """
        try:
            referral_code = tail_data.get("referral_code")
            if referral_code:
                # Track tail as referral conversion
                await self.referral_manager.track_conversion(
                    referral_code=referral_code,
                    referred_user_id=user_id,
                    conversion_type="entry_placed",
                    attribution_source="tail",
                    metadata=tail_data,
                )
                logger.info(
                    f"Tracked tail conversion for user {user_id} "
                    f"via code {referral_code}"
                )

        except Exception as e:
            logger.error(f"Error tracking tail event: {e}", exc_info=True)


async def setup(bot: commands.Bot) -> None:
    """Load the cog."""
    referral_manager = bot.referral_manager
    await bot.add_cog(ReferralTrackingCog(bot, referral_manager))
