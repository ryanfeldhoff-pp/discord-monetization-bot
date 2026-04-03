"""
Monthly Recap Cog

Generates and distributes monthly recap cards to all linked users.
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands, tasks
from sqlalchemy import select

from src.services.xp_manager import XPManager
from src.services.image_generator import RecapCardGenerator
from src.models.xp_models import RecapPreference, AccountLink
from src.utils.embeds import info_embed, error_embed, loading_embed, success_embed

logger = logging.getLogger(__name__)


class MonthlyRecap(commands.Cog):
    """
    Monthly recap card generation and distribution.

    Features:
    - Auto-generates recaps on 1st of each month
    - /recap — Manually trigger recap generation
    - /recap off — Opt out of automatic recaps
    - Shareable recap cards with referral links
    """

    def __init__(
        self,
        bot: commands.Bot,
        xp_manager: XPManager,
        db_session,
        prizepicks_api_client,
    ):
        """
        Initialize Monthly Recap cog.

        Args:
            bot: Discord bot instance
            xp_manager: XPManager service instance
            db_session: Async SQLAlchemy session
            prizepicks_api_client: PrizePicks API client
        """
        self.bot = bot
        self.xp_manager = xp_manager
        self.db = db_session
        self.pp_api = prizepicks_api_client

        # Initialize image generator
        self.image_generator = RecapCardGenerator()

        # Background task for monthly distribution
        self.distribute_monthly_recaps.start()

    def cog_unload(self):
        """Clean up background tasks."""
        self.distribute_monthly_recaps.cancel()

    @commands.slash_command(
        name="recap",
        description="View your monthly recap card"
    )
    async def recap_command(
        self,
        ctx: discord.ApplicationContext,
    ) -> None:
        """
        Generate and display user's recap card.

        Shows monthly stats with shareable options.
        """
        await ctx.defer()

        try:
            user_id = ctx.author.id

            # Send loading state
            loading_msg = await ctx.respond(embed=loading_embed("Generating your monthly recap..."))  # noqa: F841

            # Check if account is linked
            stmt = select(AccountLink).where(AccountLink.discord_user_id == user_id)
            result = await self.db.execute(stmt)
            account_link = result.scalar_one_or_none()

            if not account_link:
                embed = error_embed(
                    "Account Not Linked",
                    "Link your PrizePicks account to view recaps",
                    recovery_hint="Use `/link` to authorize your account",
                    error_code="NOT_LINKED"
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            # Generate recap data
            recap_data = await self._gather_recap_data(user_id, account_link)

            if not recap_data:
                embed = error_embed(
                    "Insufficient Data",
                    "Not enough activity to generate recap yet",
                    recovery_hint="Start chatting and making entries to generate your recap!",
                    error_code="INSUFFICIENT_DATA"
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            # Generate image
            recap_image = self.image_generator.generate_recap_card(**recap_data)

            # Create referral link
            referral_link = await self._generate_referral_link(user_id)

            # Get current month and year for context
            now = datetime.utcnow()
            month_year = now.strftime("%B %Y")

            # Create embed with share buttons
            embed = info_embed(
                "Your Monthly Recap",
                f"Here's your recap for {month_year}!",
            )

            embed.set_image(url="attachment://recap.png")

            # Create share view
            view = RecapShareView(recap_image, referral_link, ctx.author.name)

            await ctx.respond(
                embed=embed,
                file=discord.File(recap_image, "recap.png"),
                view=view,
            )

            # Update last recap timestamp
            stmt = select(RecapPreference).where(RecapPreference.discord_user_id == user_id)
            result = await self.db.execute(stmt)
            pref = result.scalar_one_or_none()

            if pref:
                pref.last_recap_at = datetime.utcnow()
            else:
                pref = RecapPreference(
                    discord_user_id=user_id,
                    last_recap_at=datetime.utcnow(),
                )
                self.db.add(pref)

            await self.db.commit()

        except Exception as e:
            logger.error(f"Error in recap command: {e}")
            embed = error_embed(
                "Recap Generation Failed",
                "An error occurred while generating your recap",
                recovery_hint="Please try again in a moment",
                error_code="RECAP_GEN_ERROR"
            )
            await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(
        name="recap_opt",
        description="Manage recap preferences"
    )
    @discord.option(
        name="action",
        description="Action to perform",
        choices=["on", "off"],
        default="on",
    )
    async def recap_opt_command(
        self,
        ctx: discord.ApplicationContext,
        action: str,
    ) -> None:
        """
        Toggle automatic monthly recap delivery.

        Args:
            action: "on" to enable, "off" to disable
        """
        await ctx.defer(ephemeral=True)

        try:
            user_id = ctx.author.id
            opted_out = action == "off"

            stmt = select(RecapPreference).where(RecapPreference.discord_user_id == user_id)
            result = await self.db.execute(stmt)
            pref = result.scalar_one_or_none()

            if pref:
                pref.opted_out = opted_out
            else:
                pref = RecapPreference(
                    discord_user_id=user_id,
                    opted_out=opted_out,
                )
                self.db.add(pref)

            await self.db.commit()

            if opted_out:
                embed = success_embed(
                    "Recaps Disabled",
                    "You won't receive automatic monthly recaps",
                )
            else:
                embed = success_embed(
                    "Recaps Enabled",
                    "You'll receive automatic monthly recaps on the 1st of each month",
                )

            await ctx.respond(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in recap opt command: {e}")
            embed = error_embed(
                "Preference Update Failed",
                "Error updating your recap preferences",
                recovery_hint="Please try again in a moment",
                error_code="PREF_UPDATE_ERROR"
            )
            await ctx.respond(embed=embed, ephemeral=True)

    @tasks.loop(hours=24)
    async def distribute_monthly_recaps(self) -> None:
        """
        Distribute monthly recaps to all opted-in users on 1st of month.

        This task runs daily but only processes on the 1st.
        Distribution is staggered (1000 users per minute) to avoid rate limits.
        """
        now = datetime.utcnow()
        if now.day != 1:
            return

        try:
            logger.info("Starting monthly recap distribution")

            # Get all linked users who haven't opted out
            stmt = select(AccountLink.discord_user_id).where(
                select(RecapPreference)
                .where(
                    (RecapPreference.discord_user_id == AccountLink.discord_user_id)
                    & (RecapPreference.opted_out == False)
                )
                .exists()
            )

            result = await self.db.execute(stmt)
            user_ids = result.scalars().all()

            if not user_ids:
                logger.info("No users to send recaps to")
                return

            logger.info(f"Sending recaps to {len(user_ids)} users")

            # Batch process users with rate limiting
            batch_size = 1000
            for i in range(0, len(user_ids), batch_size):
                batch = user_ids[i : i + batch_size]

                tasks = [
                    self._send_recap_to_user(user_id)
                    for user_id in batch
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

                # Rate limit: 1 batch per minute
                if i + batch_size < len(user_ids):
                    await asyncio.sleep(60)

            logger.info("Monthly recap distribution complete")

        except Exception as e:
            logger.error(f"Error in monthly recap distribution: {e}")

    @distribute_monthly_recaps.before_loop
    async def before_distribute(self) -> None:
        """Wait for bot to be ready before starting distribution."""
        await self.bot.wait_until_ready()

    async def _send_recap_to_user(self, user_id: int) -> None:
        """
        Send recap card to user via DM.

        Args:
            user_id: Discord user ID
        """
        try:
            user = await self.bot.fetch_user(user_id)

            # Get account link
            stmt = select(AccountLink).where(AccountLink.discord_user_id == user_id)
            result = await self.db.execute(stmt)
            account_link = result.scalar_one_or_none()

            if not account_link:
                return

            # Gather recap data
            recap_data = await self._gather_recap_data(user_id, account_link)

            if not recap_data:
                logger.debug(f"Insufficient data for recap for user {user_id}")
                return

            # Generate image
            recap_image = self.image_generator.generate_recap_card(**recap_data)

            # Create referral link
            referral_link = await self._generate_referral_link(user_id)  # noqa: F841

            # Create embed with month/year context
            month_year = datetime.utcnow().strftime("%B %Y")
            embed = info_embed(
                "Your Monthly Recap",
                f"Here's your recap for {month_year}!",
            )

            embed.set_image(url="attachment://recap.png")

            # Send DM
            await user.send(
                embed=embed,
                file=discord.File(recap_image, "recap.png"),
            )

            logger.debug(f"Sent recap to user {user_id}")

        except discord.Forbidden:
            logger.debug(f"Cannot send DM to user {user_id} (DMs disabled)")
        except discord.NotFound:
            logger.warning(f"User {user_id} not found")
        except Exception as e:
            logger.error(f"Error sending recap to user {user_id}: {e}")

    async def _gather_recap_data(
        self,
        user_id: int,
        account_link: AccountLink,
    ) -> Optional[dict]:
        """
        Gather all recap data from PrizePicks API and local database.

        Args:
            user_id: Discord user ID
            account_link: Account link record

        Returns:
            Dict with all recap data or None if insufficient data
        """
        try:
            # TODO: Call PrizePicks API to get:
            # - entries_placed
            # - win_rate
            # - biggest_win
            # - most_played_sport
            # - most_played_player

            # GET /api/users/{pp_user_id}/stats
            # Returns: {
            #   "entries_placed": 42,
            #   "win_rate": 0.55,
            #   "biggest_win": 150.00,
            #   "most_played": {
            #     "sport": "NFL",
            #     "player": "Patrick Mahomes"
            #   }
            # }

            pp_stats = await self.pp_api.get_user_stats(account_link.prizepicks_user_id)

            # Get Discord XP data
            xp_data = await self.xp_manager.get_xp(user_id)
            rank_data = await self.xp_manager.get_rank(user_id)

            # Count messages sent this month
            from sqlalchemy import func, and_
            from src.models.xp_models import XPTransaction

            month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
            stmt = select(func.count()).select_from(XPTransaction).where(
                and_(
                    XPTransaction.discord_user_id == user_id,
                    XPTransaction.timestamp >= month_start,
                    XPTransaction.source == "message",
                )
            )
            result = await self.db.execute(stmt)
            messages_sent = result.scalar() or 0

            return {
                "username": (await self.bot.fetch_user(user_id)).name,
                "entries_placed": pp_stats.get("entries_placed", 0),
                "win_rate": pp_stats.get("win_rate", 0) * 100,
                "biggest_win": pp_stats.get("biggest_win", 0),
                "most_played_sport": pp_stats.get("most_played", {}).get("sport", "N/A"),
                "most_played_player": pp_stats.get("most_played", {}).get("player", "N/A"),
                "xp_earned": xp_data["balance"],
                "messages_sent": messages_sent,
                "community_rank": rank_data["rank"],
                "referral_link": await self._generate_referral_link(user_id),
            }

        except Exception as e:
            logger.error(f"Error gathering recap data for user {user_id}: {e}")
            return None

    async def _generate_referral_link(self, user_id: int) -> str:
        """
        Generate referral link for user.

        TODO: Implement actual referral link generation.

        Args:
            user_id: Discord user ID

        Returns:
            Referral URL
        """
        # TODO: Call PrizePicks referral API
        # POST /api/referrals/generate
        # { "discord_user_id": user_id }
        # Returns: { "referral_url": "https://pp.com/ref/..." }

        return f"https://prizepicks.com/ref/{user_id}"


class RecapShareView(discord.ui.View):
    """View for recap sharing options."""

    def __init__(self, recap_image, referral_link: str, username: str):
        """Initialize recap share view."""
        super().__init__(timeout=300)
        self.recap_image = recap_image
        self.referral_link = referral_link
        self.username = username

    @discord.ui.button(
        label="Share to Channel",
        style=discord.ButtonStyle.gray,
        emoji="📢",
    )
    async def share_channel(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ) -> None:
        """Share recap to channel."""
        # TODO: Show channel selector
        await interaction.response.send_message(
            "Share to channel feature coming soon!",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Share to Social",
        style=discord.ButtonStyle.blurple,
        emoji="🔗",
    )
    async def share_social(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ) -> None:
        """Share to social media with referral link."""
        embed = info_embed(
            "Share Your Recap",
            f"Share this link with your friends:\n{self.referral_link}",
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )


def setup(
    bot: commands.Bot,
    xp_manager: XPManager,
    db_session,
    prizepicks_api_client,
) -> None:
    """Setup function for bot to load this cog."""
    bot.add_cog(MonthlyRecap(bot, xp_manager, db_session, prizepicks_api_client))
