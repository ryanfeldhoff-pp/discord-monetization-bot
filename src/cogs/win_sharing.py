"""
Win Sharing Cog (Pillar 4)

Enables users to share wins with auto-attached referral links,
and manages post-win DM notifications with referral CTAs.
"""

import logging
from typing import Optional

import discord
from discord.ext import commands
from aiohttp import web

from src.services.referral_manager import ReferralManager
from src.services.xp_manager import XPManager

logger = logging.getLogger(__name__)


class ShareWinView(discord.ui.View):
    """Interactive view with Share Win button on win notifications."""

    def __init__(self, cog: "WinSharingCog", entry_id: str, win_amount_cents: int):
        super().__init__(timeout=3600)  # 1 hour
        self.cog = cog
        self.entry_id = entry_id
        self.win_amount_cents = win_amount_cents

    @discord.ui.button(label="🎉 Share Win", style=discord.ButtonStyle.success)
    async def share_win(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Handle share win button click."""
        await interaction.response.defer(ephemeral=True)

        result = await self.cog.referral_manager.record_win_share(
            discord_user_id=interaction.user.id,
            entry_id=self.entry_id,
            win_amount_cents=self.win_amount_cents,
            channel_id=interaction.channel_id,
        )

        if result:
            # Post win to the channel
            embed = discord.Embed(
                title="🎉 Winner Winner!",
                description=(
                    f"**{interaction.user.mention}** just won "
                    f"**${self.win_amount_cents / 100:.2f}**!\n\n"
                    f"Want to play? Use their referral link:\n"
                    f"**{result.get('referral_url', 'Link unavailable')}**"
                ),
                color=0x10B981,
            )
            embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else None)

            # Post to designated win-sharing channel or current channel
            from config.config import Config
            target_channel_id = Config.WIN_SHARING_CHANNEL_ID or interaction.channel_id
            channel = self.cog.bot.get_channel(target_channel_id)
            if channel:
                await channel.send(embed=embed)

            await interaction.followup.send(
                "✅ Win shared! Thanks for spreading the word. (+25 XP)", ephemeral=True
            )

            # Award XP for sharing
            await self.cog.xp_manager.award_xp(
                interaction.user.id,
                self.cog.xp_manager.XP_VALUES["entry_shared"],
                "win_shared",
                metadata={"entry_id": self.entry_id},
                ignore_daily_cap=True,
            )
        else:
            await interaction.followup.send("Failed to share win. Please try again.", ephemeral=True)


class WinSharingCog(commands.Cog):
    """
    Win sharing cog for referral-attributed win celebrations.

    Features:
    - /share win — Share your latest win with referral link
    - /share stats — Win sharing performance
    - /share settings — Toggle post-win DMs
    - Webhook listener for real-time win events from PrizePicks backend
    - Post-win DM with "Share Win" button + referral CTA
    """

    def __init__(
        self,
        bot: commands.Bot,
        referral_manager: ReferralManager,
        xp_manager: XPManager,
    ):
        self.bot = bot
        self.referral_manager = referral_manager
        self.xp_manager = xp_manager

    share_group = discord.SlashCommandGroup("share", "Win sharing")

    @share_group.command(name="win", description="Share your latest win")
    async def share_win(self, ctx: discord.ApplicationContext) -> None:
        """Share latest win with referral link attached."""
        await ctx.defer(ephemeral=True)

        try:
            # Get user's referral data
            ref_data = await self.referral_manager.get_or_create_code(ctx.author.id)

            # TODO: Fetch latest win from /api/users/{pp_user_id}/wins
            # For now, prompt user to share manually
            embed = discord.Embed(
                title="🎉 Share Your Win!",
                description=(
                    "Your referral link is auto-attached when you share.\n\n"
                    f"**Your Referral Link:**\n{ref_data.get('referral_url', 'Not available')}\n\n"
                    "When your friends sign up through your link, you earn **$25+** per FTD!\n\n"
                    "*Once backend integration is complete, your recent wins will "
                    "auto-populate here with a one-click share button.*"
                ),
                color=0x10B981,
            )
            embed.set_footer(text=f"Referral code: {ref_data.get('code', 'N/A')}")
            await ctx.respond(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in share win command: {e}")
            await ctx.respond("Error sharing win.", ephemeral=True)

    @share_group.command(name="stats", description="View win sharing performance")
    async def share_stats(self, ctx: discord.ApplicationContext) -> None:
        """Show win sharing stats."""
        await ctx.defer(ephemeral=True)

        try:
            from sqlalchemy import select, func
            from src.models.referral_models import WinShare

            stmt = select(
                func.count().label("total_shares"),
                func.sum(WinShare.tails_generated).label("total_tails"),
                func.sum(WinShare.referrals_generated).label("total_referrals"),
            ).where(WinShare.discord_user_id == ctx.author.id)

            result = await self.referral_manager.db.execute(stmt)
            row = result.one_or_none()

            embed = discord.Embed(
                title=f"📊 Win Sharing Stats — {ctx.author.name}",
                color=0x8B5CF6,
            )

            if row and row.total_shares:
                embed.add_field(name="Wins Shared", value=str(row.total_shares or 0), inline=True)
                embed.add_field(name="Tails Generated", value=str(row.total_tails or 0), inline=True)
                embed.add_field(name="Referrals Generated", value=str(row.total_referrals or 0), inline=True)
            else:
                embed.description = "No wins shared yet. Use `/share win` after your next W!"

            await ctx.respond(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in share stats: {e}")
            await ctx.respond("Error loading stats.", ephemeral=True)

    @share_group.command(name="settings", description="Toggle post-win DM notifications")
    @discord.option(
        name="dm",
        description="Enable or disable post-win DMs",
        choices=["on", "off"],
        required=True,
    )
    async def share_settings(self, ctx: discord.ApplicationContext, dm: str) -> None:
        """Toggle post-win DM notifications."""
        await ctx.defer(ephemeral=True)

        try:
            dm_enabled = dm == "on"
            success = await self.referral_manager.update_win_share_prefs(
                ctx.author.id, dm_enabled=dm_enabled
            )

            if success:
                state = "enabled" if dm_enabled else "disabled"
                await ctx.respond(f"✅ Post-win DMs **{state}**.", ephemeral=True)
            else:
                await ctx.respond("Failed to update settings.", ephemeral=True)

        except Exception as e:
            logger.error(f"Error updating share settings: {e}")
            await ctx.respond("Error updating settings.", ephemeral=True)

    async def handle_win_webhook(self, payload: dict) -> None:
        """
        Handle incoming win event webhook from PrizePicks backend.

        Expected payload:
        {
            "discord_user_id": 123456789,
            "entry_id": "abc123",
            "win_amount_cents": 5000,
            "picks": [{"player": "LeBron", "stat": "Points", "line": 27.5, "actual": 32}]
        }
        """
        try:
            user_id = payload.get("discord_user_id")
            entry_id = payload.get("entry_id")
            win_amount = payload.get("win_amount_cents", 0)

            if not user_id or not entry_id:
                logger.warning("Invalid win webhook payload")
                return

            # Check user's DM preferences
            prefs = await self.referral_manager.get_win_share_prefs(user_id)
            if not prefs.get("dm_enabled", True):
                return

            # Check minimum win amount
            if win_amount < prefs.get("min_win_amount_cents", 500):
                return

            # Send DM with share button
            try:
                user = await self.bot.fetch_user(user_id)
                if not user:
                    return

                embed = discord.Embed(
                    title="🎉 You Won!",
                    description=(
                        f"Congrats! You just won **${win_amount / 100:.2f}**!\n\n"
                        "Share your win with the community and earn referral bonuses!"
                    ),
                    color=0x10B981,
                )

                picks = payload.get("picks", [])
                if picks:
                    picks_text = "\n".join(
                        f"• {p['player']} — {p['stat']} {p.get('actual', '?')}/{p['line']}"
                        for p in picks[:5]
                    )
                    embed.add_field(name="Your Picks", value=picks_text, inline=False)

                view = ShareWinView(self, entry_id, win_amount)
                await user.send(embed=embed, view=view)

                logger.info(f"Sent win DM to user {user_id} for entry {entry_id}")

            except discord.Forbidden:
                logger.warning(f"Cannot DM user {user_id} (DMs disabled)")
            except Exception as e:
                logger.error(f"Error sending win DM: {e}")

        except Exception as e:
            logger.error(f"Error handling win webhook: {e}")


def setup(bot: commands.Bot) -> None:
    pass  # Loaded via bot.add_cog() in main.py
