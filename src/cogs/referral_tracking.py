"""
Referral Tracking Cog

Handles referral code generation, sharing, and performance tracking.
Core functionality for the Referral Amplifier system (Pillar 4).
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
import secrets
import qrcode
from io import BytesIO

import discord
from discord.ext import commands

from src.models.referral_models import ReferralCode
from src.services.referral_manager import ReferralManager
from src.utils.colors import PRIZEPICKS_PRIMARY, SUCCESS, INFO
from src.utils.embeds import (
    success_embed,
    error_embed,
    info_embed,
    empty_state_embed,
    leaderboard_embed,
    progress_bar,
)
from src.utils.pagination import PaginatedView
from src.utils.validation import validate_positive_int
from src.utils.error_handler import ValidationError, handle_error

logger = logging.getLogger(__name__)

# Cooldown tracking: user_id -> datetime of last code generation
_referral_code_cooldowns = {}


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
        title = "Your Referral Code" + (" (Ambassador)" if is_ambassador else "")
        embed = success_embed(
            title,
            "Share your code to earn rewards when friends sign up!",
            fields=[
                ("Your Code", f"```\n{code}\n```", False),
                ("Shareable Link", f"Share: {referral_url}", False),
                ("Total Referrals", f"**{stats.get('total_referrals', 0)}**", True),
                ("FTDs", f"**{stats.get('total_ftds', 0)}**", True),
                ("Earnings", f"**${stats.get('total_earnings', 0) / 100:.2f}**", True),
            ],
        )

        embed.set_thumbnail(url=user.avatar.url if user.avatar else "")

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
        total_refs = stats.get("total_referrals", 0)
        total_ftds = stats.get("total_ftds", 0)
        conversion_rate = (
            (total_ftds / total_refs * 100) if total_refs > 0 else 0
        )

        # Progress bars toward milestones
        milestones = [
            (5, "5 Referrals", total_refs),
            (10, "10 FTDs", total_ftds),
            (25, "25 Referrals", total_refs),
            (50, "50 FTDs", total_ftds),
        ]

        progress_text = ""
        for target, label, current in milestones:
            bar = progress_bar(current, target)
            progress_text += f"{label}: {bar}\n"

        earnings = stats.get("total_earnings", 0)

        embed = info_embed(
            f"Referral Stats - {user.name}",
            "Your referral performance at a glance",
            fields=[
                ("Total Referrals", f"**{total_refs}**", True),
                ("First-Time Depositors (FTDs)", f"**{total_ftds}**", True),
                ("Conversion Rate", f"**{conversion_rate:.1f}%**", True),
                ("Progress to Milestones", progress_text, False),
                ("Total Earnings", f"**${earnings / 100:.2f}**", False),
            ],
        )

        embed.set_thumbnail(url=user.avatar.url if user.avatar else "")

        return embed


class ReferralLeaderboardEmbed:
    """Helper class to generate leaderboard embeds."""

    @staticmethod
    def create_leaderboard_pages(
        leaderboard: list,
        period: str = "all-time",
        page_size: int = 10,
    ) -> list:
        """
        Create paginated leaderboard embeds (10 per page).

        Args:
            leaderboard: List of top referrer dicts
            period: Time period for leaderboard
            page_size: Number of entries per page

        Returns:
            list: List of discord.Embed objects
        """
        embeds = []
        total_pages = (len(leaderboard) + page_size - 1) // page_size

        for page_num in range(total_pages):
            start_idx = page_num * page_size
            end_idx = min(start_idx + page_size, len(leaderboard))
            page_entries = leaderboard[start_idx:end_idx]

            entries_list = []
            for idx, entry in enumerate(page_entries, start=start_idx + 1):
                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(idx, f"#{idx}")
                username = entry.get("username", f"User {entry.get('discord_user_id')}")
                ftds = entry.get("total_ftds", 0)
                earnings = entry.get("total_earnings", 0)

                entries_list.append({
                    "rank": idx,
                    "username": username,
                    "value": f"{ftds} FTDs • ${earnings / 100:.2f}",
                })

            embed = leaderboard_embed(
                title=f"Top Referrers - {period.title()}",
                entries=entries_list,
                page=page_num + 1,
                total_pages=total_pages,
            )

            embeds.append(embed)

        return embeds if embeds else [
            empty_state_embed(
                "Leaderboard",
                "No referral data yet. Be the first to start referring!",
                ["/referral code", "/referral stats"],
            )
        ]


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
        Generate or display user's referral code with cooldown.

        Args:
            ctx: Discord application context
            user_id: Discord user ID
        """
        try:
            # Check cooldown for new code generation
            now = datetime.utcnow()
            last_generation = _referral_code_cooldowns.get(user_id)

            if last_generation and (now - last_generation).days < 1:
                time_until_next = last_generation + timedelta(days=1)
                time_remaining = time_until_next - now
                hours = time_remaining.seconds // 3600
                minutes = (time_remaining.seconds % 3600) // 60

                embed = error_embed(
                    "Code Generation Cooldown",
                    f"You can generate a new code in {hours}h {minutes}m",
                    recovery_hint="Use your current code in the meantime!",
                    error_code="COOLDOWN_ACTIVE",
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            # Check if code exists
            referral_data = await self.referral_manager.get_or_create_referral_code(
                user_id
            )

            if not referral_data:
                embed = error_embed(
                    "Account Not Linked",
                    "You need to link your PrizePicks account first to get a referral code.",
                    recovery_hint="Use /link to connect your PrizePicks account",
                    error_code="ACCOUNT_NOT_LINKED",
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            code = referral_data.get("code")
            url = referral_data.get("url")
            is_ambassador = referral_data.get("is_ambassador", False)

            # Get stats
            stats = await self.referral_manager.get_referral_stats(user_id)

            # Update cooldown
            _referral_code_cooldowns[user_id] = now

            # Create and send embed
            embed = ReferralCodeEmbed.create_code_embed(
                ctx.author,
                code,
                url,
                stats,
                is_ambassador,
            )

            # Add accessibility labels to response
            await ctx.respond(
                content="Your referral code and link below (copy-friendly format)",
                embed=embed,
            )
            logger.info(f"Displayed referral code for user {user_id}")

        except Exception as e:
            logger.error(f"Error showing referral code: {e}", exc_info=True)
            embed = error_embed(
                "Error",
                "Could not retrieve your referral code.",
                recovery_hint="Please try again in a moment",
                error_code="CODE_RETRIEVAL_ERROR",
            )
            await ctx.respond(embed=embed, ephemeral=True)

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
                embed = empty_state_embed(
                    "Referrals",
                    "You haven't referred anyone yet!",
                    ["/referral code", "/referral link"],
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            # Create and send embed
            embed = ReferralStatsEmbed.create_stats_embed(ctx.author, stats)
            await ctx.respond(embed=embed)
            logger.info(f"Displayed referral stats for user {user_id}")

        except Exception as e:
            logger.error(f"Error showing referral stats: {e}", exc_info=True)
            embed = error_embed(
                "Error",
                "Could not retrieve your stats.",
                recovery_hint="Please try again in a moment",
                error_code="STATS_RETRIEVAL_ERROR",
            )
            await ctx.respond(embed=embed, ephemeral=True)

    async def _show_leaderboard(
        self,
        ctx: discord.ApplicationContext,
    ) -> None:
        """
        Display top referrers leaderboard with pagination and "Jump to my rank".

        Args:
            ctx: Discord application context
        """
        try:
            leaderboard = (
                await self.referral_manager.get_top_referrers(
                    limit=100,
                )
            )

            if not leaderboard:
                embed = empty_state_embed(
                    "Leaderboard",
                    "No referral data available yet.",
                    ["/referral code", "/referral stats"],
                )
                await ctx.respond(embed=embed)
                return

            # Create paginated embeds
            embeds = ReferralLeaderboardEmbed.create_leaderboard_pages(
                leaderboard,
                period="all-time",
                page_size=10,
            )

            # Find user's rank
            user_rank = None
            for idx, entry in enumerate(leaderboard, start=1):
                if entry.get("discord_user_id") == ctx.author.id:
                    user_rank = idx
                    break

            # Create pagination callback for "Jump to my rank"
            async def on_jump_to_rank(interaction: discord.Interaction) -> None:
                if user_rank:
                    page = (user_rank - 1) // 10
                    view.current_page = page
                    view._update_buttons()
                    await interaction.response.edit_message(
                        embed=embeds[page],
                        view=view,
                    )
                else:
                    await interaction.response.send_message(
                        "You're not on the leaderboard yet! Start referring to climb the ranks!",
                        ephemeral=True,
                    )

            # Create view with jump callback
            view = PaginatedView(embeds, on_jump_to_rank=on_jump_to_rank)

            await ctx.respond(embed=embeds[0], view=view)
            logger.info(f"Displayed referral leaderboard with {len(leaderboard)} entries")

        except Exception as e:
            logger.error(f"Error showing leaderboard: {e}", exc_info=True)
            embed = error_embed(
                "Error",
                "Could not retrieve the leaderboard.",
                recovery_hint="Please try again in a moment",
                error_code="LEADERBOARD_ERROR",
            )
            await ctx.respond(embed=embed, ephemeral=True)

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
                embed = error_embed(
                    "Account Not Linked",
                    "You need to link your PrizePicks account first.",
                    recovery_hint="Use /link to connect your PrizePicks account",
                    error_code="ACCOUNT_NOT_LINKED",
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            code = referral_data.get("code")
            url = referral_data.get("url")

            embed = info_embed(
                "Your Referral Link",
                "Copy below and share with friends!",
                fields=[
                    ("Copy-Friendly Link", f"```\n{url}\n```", False),
                    ("Share Your Code", f"Code: `{code}`\nAsk friends to enter it during signup!", False),
                ],
            )

            # Button for direct opening with accessibility label
            view = discord.ui.View()
            view.add_item(
                discord.ui.Button(
                    label="Open Link",
                    url=url,
                    style=discord.ButtonStyle.link,
                    emoji="🔗",
                    disabled=False,
                )
            )

            await ctx.respond(
                content="Click the button or copy the link below to share your referral",
                embed=embed,
                view=view,
            )

        except Exception as e:
            logger.error(f"Error showing referral link: {e}", exc_info=True)
            embed = error_embed(
                "Error",
                "Could not retrieve your link.",
                recovery_hint="Please try again in a moment",
                error_code="LINK_RETRIEVAL_ERROR",
            )
            await ctx.respond(embed=embed, ephemeral=True)

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
