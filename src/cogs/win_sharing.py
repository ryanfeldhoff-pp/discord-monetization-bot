"""
Win Sharing Cog

Handles win sharing with referral CTAs and post-win DM notifications.
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands, tasks

from src.models.referral_models import WinShareLog
from src.services.referral_manager import ReferralManager
from src.services.xp_manager import XPManager
from src.utils.colors import PRIZEPICKS_PRIMARY, SUCCESS, INFO
from src.utils.embeds import (
    success_embed,
    error_embed,
    info_embed,
    empty_state_embed,
)
from src.utils.views import UnsubscribeView

logger = logging.getLogger(__name__)


class WinShareView(discord.ui.View):
    """View with win share action buttons."""

    def __init__(self, win_data: dict, referral_code: str, user_id: int):
        """
        Initialize win share view.

        Args:
            win_data: Dictionary with win details
            referral_code: User's referral code
            user_id: Discord user ID
        """
        super().__init__()
        self.win_data = win_data
        self.referral_code = referral_code
        self.user_id = user_id

    @discord.ui.button(
        label="Share to Channel",
        style=discord.ButtonStyle.primary,
        custom_id="share_channel",
        emoji="📢",
    )
    async def share_channel(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ) -> None:
        """Share win to channel."""
        try:
            if interaction.user.id != self.user_id:
                await interaction.response.defer()
                return

            # Create win share embed
            embed = WinShareEmbed.create_share_embed(
                self.win_data,
                self.referral_code,
                interaction.user,
            )

            # Send to channel
            await interaction.channel.send(embed=embed)

            # Track share
            embed_response = success_embed(
                "Win Shared",
                "Your entry is visible in this channel!",
            )
            await interaction.response.send_message(
                embed=embed_response,
                ephemeral=True,
            )

            logger.info(
                f"User {self.user_id} shared win to channel "
                f"{interaction.channel.id}"
            )

        except Exception as e:
            logger.error(f"Error sharing to channel: {e}", exc_info=True)
            embed_response = error_embed(
                "Sharing Failed",
                "Could not share your win. Please try again.",
                recovery_hint="Check that you have permission to post",
                error_code="SHARE_FAILED",
            )
            await interaction.response.send_message(
                embed=embed_response,
                ephemeral=True,
            )

    @discord.ui.button(
        label="Share to Social",
        style=discord.ButtonStyle.secondary,
        custom_id="share_social",
        emoji="🔗",
    )
    async def share_social(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ) -> None:
        """Get social share link."""
        try:
            if interaction.user.id != self.user_id:
                await interaction.response.defer()
                return

            win_amount = self.win_data.get("amount", 0)
            referral_code = self.referral_code

            # Create social share text
            social_text = (
                f"Just won ${win_amount / 100:.2f} on PrizePicks! 🏆\n\n"
                f"Join me and use code: {referral_code}\n"
                f"https://prizepicks.com"
            )

            embed = info_embed(
                "Social Share Text",
                "Copy this to share on social media:",
                fields=[
                    ("Share Template", f"```\n{social_text}\n```", False),
                ],
            )

            await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
            )

            logger.info(f"User {self.user_id} prepared social share")

        except Exception as e:
            logger.error(f"Error preparing social share: {e}", exc_info=True)
            embed_response = error_embed(
                "Preparation Failed",
                "Could not prepare social share template.",
                recovery_hint="Please try again in a moment",
                error_code="SOCIAL_SHARE_ERROR",
            )
            await interaction.response.send_message(
                embed=embed_response,
                ephemeral=True,
            )


class WinShareEmbed:
    """Helper class to generate win share embeds."""

    @staticmethod
    def create_share_embed(
        win_data: dict,
        referral_code: str,
        user: discord.User,
    ) -> discord.Embed:
        """
        Create branded win share embed with referral CTA.

        Args:
            win_data: Dictionary with win details
            referral_code: User's referral code
            user: Discord user who won

        Returns:
            discord.Embed: Formatted embed
        """
        win_amount = win_data.get("amount", 0)
        picks = win_data.get("picks", [])
        entry_id = win_data.get("entry_id", "")
        is_verified = win_data.get("is_verified", True)

        # Picks preview (keep short for mobile)
        picks_text = "\n".join([f"• {pick}" for pick in picks[:3]])
        if len(picks) > 3:
            picks_text += f"\n• +{len(picks) - 3} more"

        # Verification flag
        verification_note = "" if is_verified else "\n⚠️ Unverified | Verify with /link"

        embed = success_embed(
            f"{user.name} Won!",
            f"Just hit a win on PrizePicks!{verification_note}",
            fields=[
                ("Amount Won", f"**${win_amount / 100:.2f}**", True),
                ("Picks", f"**{len(picks)}**", True),
                ("Entry Picks", picks_text or "No picks to display", False),
                ("Want to Win Too?", f"Use code: ```\n{referral_code}\n```", False),
            ],
        )

        embed.set_thumbnail(url=user.avatar.url if user.avatar else "")

        return embed


class PostWinDMView(discord.ui.View):
    """View for post-win DM with share button."""

    def __init__(self, user_id: int, referral_code: str, win_data: dict):
        """
        Initialize post-win DM view.

        Args:
            user_id: Discord user ID
            referral_code: User's referral code
            win_data: Win data dictionary
        """
        super().__init__()
        self.user_id = user_id
        self.referral_code = referral_code
        self.win_data = win_data

    @discord.ui.button(
        label="Share Your Win",
        style=discord.ButtonStyle.primary,
        custom_id="share_win_button",
        emoji="🚀",
    )
    async def share_win(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ) -> None:
        """
        Open dialog to share win.

        Args:
            button: Button that was clicked
            interaction: Interaction context
        """
        try:
            if interaction.user.id != self.user_id:
                await interaction.response.defer()
                return

            # Create sharing view
            view = WinShareView(
                self.win_data,
                self.referral_code,
                self.user_id,
            )

            embed = info_embed(
                "Share Your Win",
                "How would you like to share with the community?",
            )

            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True,
            )

        except Exception as e:
            logger.error(f"Error in share win button: {e}", exc_info=True)
            embed_response = error_embed(
                "Dialog Failed",
                "Could not open share dialog.",
                recovery_hint="Please try again in a moment",
                error_code="DIALOG_ERROR",
            )
            await interaction.response.send_message(
                embed=embed_response,
                ephemeral=True,
            )


class WinSharingCog(commands.Cog):
    """
    Win sharing cog with referral CTAs and post-win DMs.

    Features:
    - Manual win sharing to channel
    - Post-win DM notifications
    - Win share performance tracking
    - Ambassador badges on shares
    """

    def __init__(
        self,
        bot: commands.Bot,
        referral_manager: ReferralManager,
        xp_manager: XPManager,
    ):
        """
        Initialize Win Sharing cog.

        Args:
            bot: Discord bot instance
            referral_manager: ReferralManager service instance
            xp_manager: XPManager service instance
        """
        self.bot = bot
        self.referral_manager = referral_manager
        self.xp_manager = xp_manager

        self.process_win_events.start()

    def cog_unload(self) -> None:
        """Clean up background tasks."""
        self.process_win_events.cancel()

    @commands.slash_command(
        name="share",
        description="Share wins and manage win sharing settings",
    )
    @discord.option(
        name="action",
        description="What to do",
        choices=["win", "stats", "settings"],
        default="win",
    )
    async def share_command(
        self,
        ctx: discord.ApplicationContext,
        action: str = "win",
    ) -> None:
        """
        Share wins or manage sharing settings.

        Args:
            ctx: Discord application context
            action: Subcommand ("win", "stats", or "settings")
        """
        await ctx.defer()

        try:
            user_id = ctx.author.id

            if action == "win":
                await self._show_share_win_dialog(ctx, user_id)
            elif action == "stats":
                await self._show_share_stats(ctx, user_id)
            elif action == "settings":
                await self._show_share_settings(ctx, user_id)
            else:
                await ctx.respond(
                    "Invalid action.",
                    ephemeral=True,
                )

        except Exception as e:
            logger.error(f"Error in share command: {e}", exc_info=True)
            await ctx.respond(
                "An error occurred. Please try again.",
                ephemeral=True,
            )

    async def _show_share_win_dialog(
        self,
        ctx: discord.ApplicationContext,
        user_id: int,
    ) -> None:
        """
        Show dialog to share latest win with verification check.

        Args:
            ctx: Discord application context
            user_id: Discord user ID
        """
        try:
            # Get latest win for user
            latest_win = await self.referral_manager.get_latest_win(user_id)

            if not latest_win:
                embed = empty_state_embed(
                    "Wins",
                    "You don't have any recent wins to share.",
                    ["/share stats", "/referral code"],
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            # Check if account is linked/verified
            referral_data = (
                await self.referral_manager.get_or_create_referral_code(user_id)
            )
            is_verified = referral_data is not None
            referral_code = referral_data.get("code", "UNKNOWN") if referral_data else "UNKNOWN"

            if not is_verified:
                embed = error_embed(
                    "Account Not Linked",
                    "You need to link your PrizePicks account to share wins.",
                    recovery_hint="Use /link to connect your account",
                    error_code="ACCOUNT_NOT_LINKED",
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            # Create view
            view = WinShareView(latest_win, referral_code, user_id)

            # Create embed
            win_amount = latest_win.get("amount", 0)
            picks = latest_win.get("picks", [])

            embed = info_embed(
                "Share Your Win",
                "Choose how you'd like to share with the community",
                fields=[
                    ("Win Amount", f"**${win_amount / 100:.2f}**", True),
                    ("Picks", f"**{len(picks)}**", True),
                    ("Your Code", f"```\n{referral_code}\n```", False),
                ],
            )

            await ctx.respond(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Error showing share dialog: {e}", exc_info=True)
            embed = error_embed(
                "Error",
                "Could not retrieve your latest win.",
                recovery_hint="Please try again in a moment",
                error_code="WIN_RETRIEVAL_ERROR",
            )
            await ctx.respond(embed=embed, ephemeral=True)

    async def _show_share_stats(
        self,
        ctx: discord.ApplicationContext,
        user_id: int,
    ) -> None:
        """
        Show win share performance stats.

        Args:
            ctx: Discord application context
            user_id: Discord user ID
        """
        try:
            stats = await self.referral_manager.get_win_share_stats(user_id)

            if not stats or stats.get("total_shares", 0) == 0:
                embed = empty_state_embed(
                    "Win Shares",
                    "You haven't shared any wins yet.",
                    ["/share win", "/referral code"],
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            total_shares = stats.get("total_shares", 0)
            total_clicks = stats.get("total_clicks", 0)
            total_conversions = stats.get("total_conversions", 0)

            # Click-through rate
            ctr = (
                (total_clicks / total_shares * 100) if total_shares > 0 else 0
            )

            # Conversion rate
            cr = (
                (total_conversions / total_clicks * 100)
                if total_clicks > 0
                else 0
            )

            embed = info_embed(
                "Your Win Share Performance",
                "How your shared wins are performing",
                fields=[
                    ("Total Shares", f"**{total_shares}**", True),
                    ("Total Clicks", f"**{total_clicks}**", True),
                    ("Conversions", f"**{total_conversions}**", True),
                    ("Click-Through Rate", f"**{ctr:.1f}%**", False),
                    ("Conversion Rate", f"**{cr:.1f}%**", False),
                ],
            )

            await ctx.respond(embed=embed)

        except Exception as e:
            logger.error(f"Error showing share stats: {e}", exc_info=True)
            embed = error_embed(
                "Error",
                "Could not retrieve your stats.",
                recovery_hint="Please try again in a moment",
                error_code="STATS_RETRIEVAL_ERROR",
            )
            await ctx.respond(embed=embed, ephemeral=True)

    async def _show_share_settings(
        self,
        ctx: discord.ApplicationContext,
        user_id: int,
    ) -> None:
        """
        Show win share settings.

        Args:
            ctx: Discord application context
            user_id: Discord user ID
        """
        try:
            settings = (
                await self.referral_manager.get_win_share_settings(user_id)
            )
            dm_notifications_enabled = settings.get(
                "dm_notifications_enabled", True
            )

            embed = discord.Embed(
                title="Win Share Settings",
                description="Manage how you receive win notifications",
                color=PRIZEPICKS_PURPLE,
                timestamp=datetime.utcnow(),
            )

            dm_status = "✅ Enabled" if dm_notifications_enabled else "❌ Disabled"
            embed.add_field(
                name="Post-Win DM Notifications",
                value=dm_status,
                inline=False,
            )

            embed.add_field(
                name="What This Does",
                value=(
                    "When enabled, you'll receive a DM immediately after winning "
                    "with an option to share your win with the community."
                ),
                inline=False,
            )

            # Toggle button
            view = discord.ui.View()
            button_label = "Disable" if dm_notifications_enabled else "Enable"
            button_style = (
                discord.ButtonStyle.danger
                if dm_notifications_enabled
                else discord.ButtonStyle.success
            )

            async def toggle_callback(interaction: discord.Interaction) -> None:
                if interaction.user.id != user_id:
                    await interaction.response.defer()
                    return

                new_state = not dm_notifications_enabled
                await self.referral_manager.set_win_share_settings(
                    user_id,
                    dm_notifications_enabled=new_state,
                )

                await interaction.response.send_message(
                    f"Post-win DM notifications "
                    f"{'enabled' if new_state else 'disabled'}!",
                    ephemeral=True,
                )

            button = discord.ui.Button(
                label=button_label,
                style=button_style,
                custom_id="toggle_dm_notifications",
            )
            button.callback = toggle_callback
            view.add_item(button)

            embed.set_footer(text="PrizePicks Community")
            await ctx.respond(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Error showing settings: {e}", exc_info=True)
            await ctx.respond(
                "Error loading settings.",
                ephemeral=True,
            )

    @tasks.loop(minutes=1)
    async def process_win_events(self) -> None:
        """
        Process win events from webhook queue every minute.

        Checks for new win events and sends post-win DMs if enabled.
        """
        try:
            # Get pending win events
            pending_wins = (
                await self.referral_manager.get_pending_win_events()
            )

            for win_event in pending_wins:
                user_id = win_event.get("discord_user_id")
                win_data = win_event.get("win_data")

                # Check if user has DM notifications enabled
                settings = (
                    await self.referral_manager.get_win_share_settings(user_id)
                )
                if not settings.get("dm_notifications_enabled", True):
                    # Mark as processed without sending DM
                    await self.referral_manager.mark_win_event_processed(
                        win_event.get("id")
                    )
                    continue

                # Get user and send DM
                try:
                    user = await self.bot.fetch_user(user_id)
                    if user:
                        # Get referral code
                        referral_data = (
                            await self.referral_manager.get_or_create_referral_code(
                                user_id
                            )
                        )
                        referral_code = referral_data.get("code", "UNKNOWN")

                        # Create DM embed
                        win_amount = win_data.get("amount", 0)
                        picks = win_data.get("picks", [])

                        embed = success_embed(
                            "You Won on PrizePicks!",
                            "Congratulations on your win!",
                            fields=[
                                ("Amount Won", f"**${win_amount / 100:.2f}**", True),
                                ("Picks", f"**{len(picks)}**", True),
                                ("Your Code", f"```\n{referral_code}\n```", False),
                            ],
                        )

                        # Create view with unsubscribe option
                        view = PostWinDMView(user_id, referral_code, win_data)
                        unsubscribe_view = UnsubscribeView(user_id, "win_alerts")

                        # Combine views or send separately
                        await user.send(embed=embed, view=view)
                        await user.send(view=unsubscribe_view)

                        logger.info(f"Sent post-win DM to user {user_id}")

                except discord.NotFound:
                    logger.warning(f"Could not find user {user_id} for DM")

                # Mark as processed
                await self.referral_manager.mark_win_event_processed(
                    win_event.get("id")
                )

            if pending_wins:
                logger.debug(f"Processed {len(pending_wins)} win events")

        except Exception as e:
            logger.error(f"Error processing win events: {e}", exc_info=True)

    @process_win_events.before_loop
    async def before_process_wins(self) -> None:
        """Wait for bot to be ready before starting task."""
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    """Load the cog."""
    referral_manager = bot.referral_manager
    xp_manager = bot.xp_manager
    await bot.add_cog(
        WinSharingCog(bot, referral_manager, xp_manager)
    )
