"""
Promo Redemption Cog

Handles XP-to-promo code redemptions with monthly limits per tier.
"""

import logging
import json
from datetime import datetime
from typing import Optional, Dict, List

import discord
from discord.ext import commands
from sqlalchemy import select, and_

from src.services.xp_manager import XPManager
from src.models.xp_models import Redemption, RedemptionCounter, AccountLink

logger = logging.getLogger(__name__)


class PromoRedemption(commands.Cog):
    """
    XP-to-Promo code redemption system.

    Features:
    - /redeem â Browse and redeem items
    - /redeem history â View past redemptions
    - Atomic transactions with rollback
    - Monthly limits per tier
    - Requires linked PrizePicks account
    """

    # Redemption catalog
    CATALOG = {
        "discount_code": {
            "name": "Exclusive Discount Code",
            "description": "Use at checkout for exclusive savings",
            "xp_cost": 1000,
            "type": "code",  # or "credit"
        },
        "free_entry_5": {
            "name": "Free Entry ($5)",
            "description": "$5 free entry credited to PrizePicks account",
            "xp_cost": 2000,
            "type": "credit",
        },
        "deposit_match_25": {
            "name": "25% Deposit Match",
            "description": "25% match on your next deposit",
            "xp_cost": 5000,
            "type": "credit",
        },
    }

    def __init__(self, bot: commands.Bot, xp_manager: XPManager, db_session):
        """
        Initialize Promo Redemption cog.

        Args:
            bot: Discord bot instance
            xp_manager: XPManager service instance
            db_session: Async SQLAlchemy session
        """
        self.bot = bot
        self.xp_manager = xp_manager
        self.db = db_session

    @commands.slash_command(
        name="redeem",
        description="Browse and redeem XP for rewards"
    )
    async def redeem_command(
        self,
        ctx: discord.ApplicationContext,
    ) -> None:
        """
        Interactive redeem command with options to view catalog or history.

        Shows current XP balance and available items.
        """
        await ctx.defer()

        try:
            user_id = ctx.author.id

            # Check if account is linked
            stmt = select(AccountLink).where(AccountLink.discord_user_id == user_id)
            result = await self.db.execute(stmt)
            account_link = result.scalar_one_or_none()

            if not account_link or not account_link.verified:
                await self._send_link_account_prompt(ctx)
                return

            xp_data = await self.xp_manager.get_xp(user_id)
            current_tier = xp_data["tier"]
            current_xp = xp_data["balance"]

            # Build catalog embed
            embed = discord.Embed(
                title="Redeem XP for Rewards",
                description=f"Your balance: **{current_xp:,} XP**",
                color=discord.Color.purple(),
                timestamp=datetime.utcnow(),
            )

            can_redeem, limit_msg = await self.xp_manager.can_redeem(user_id, current_tier)

            for item_id, item in self.CATALOG.items():
                affordable = current_xp >= item["xp_cost"]
                check = "â" if affordable else "â"
                status = "â Can redeem" if affordable else "â Not enough XP"

                value = (
                    f"{item['description']}\n"
                    f"**Cost:** {item['xp_cost']:,} XP\n"
                    f"**Status:** {status}"
                )

                embed.add_field(
                    name=f"{check} {item['name']}",
                    value=value,
                    inline=False,
                )

            embed.add_field(
                name="Monthly Limit",
                value=f"{limit_msg}",
                inline=False,
            )

            # Create view with redeem buttons
            view = RedeemView(
                self.catalog,
                self.xp_manager,
                self.db,
                user_id,
                current_tier,
                current_xp,
                can_redeem,
            )

            await ctx.respond(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Error in redeem command: {e}")
            await ctx.respond(
                "Error loading redemption catalog. Please try again later.",
                ephemeral=True,
            )

    @commands.slash_command(
        name="redeem_history",
        description="View your redemption history"
    )
    async def redeem_history_command(
        self,
        ctx: discord.ApplicationContext,
        limit: int = 10,
    ) -> None:
        """
        Display user's redemption history.

        Args:
            limit: Number of recent redemptions to show (default 10)
        """
        await ctx.defer()

        try:
            user_id = ctx.author.id

            stmt = (
                select(Redemption)
                .where(Redemption.discord_user_id == user_id)
                .order_by(Redemption.redeemed_at.desc())
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            redemptions = result.scalars().all()

            if not redemptions:
                await ctx.respond(
                    "You haven't redeemed any items yet.",
                    ephemeral=True,
                )
                return

            embed = discord.Embed(
                title="Your Redemption History",
                color=discord.Color.purple(),
                timestamp=datetime.utcnow(),
            )

            for redemption in redemptions:
                item = self.CATALOG.get(redemption.item_id, {})
                item_name = item.get("name", "Unknown Item")
                status_emoji = {
                    "completed": "â",
                    "pending": "â³",
                    "failed": "â",
                }
                status_str = status_emoji.get(redemption.status, "?")

                value = (
                    f"**Item:** {item_name}\n"
                    f"**Cost:** {redemption.xp_cost:,} XP\n"
                    f"**Status:** î {redemption.status.title()}\n"
                    f"**Date:** <t:{int(redemption.redeemed_at.timestamp())}:R>"
                )

                if redemption.promo_code:
                    value += f"\n**Code:** `{redemption.promo_code}`"

                embed.add_field(
                    name=f"{status_str} {item_name}",
                    value=value,
                    inline=False,
                )

            await ctx.respond(embed=embed)

        except Exception as e:
            logger.error(f"Error in redeem history command: {e}")
            await ctx.respond(
                "Error retrieving redemption history. Please try again later.",
                ephemeral=True,
            )

    async def _send_link_account_prompt(self, ctx: discord.ApplicationContext) -> None:
        """
        Send prompt to user to link their PrizePicks account.

        Args:
            ctx: Application context
        """
        embed = discord.Embed(
            title="Account Not Linked",
            description="You need to link your PrizePicks account to redeem rewards.",
            color=discord.Color.orange(),
        )

        embed.add_field(
            name="How to Link",
            value=(
                "Use `/link_account` to connect your PrizePicks account.\n"
                "This is a one-time setup to enable redemptions."
            ),
            inline=False,
        )

        await ctx.respond(embed=embed, ephemeral=True)

    async def _perform_redemption(
        self,
        user_id: int,
        item_id: str,
        current_tier: str,
    ) -> tuple[bool, str, Optional[str]]:
        """
        Atomically redeem an item (deduct XP and credit promo).

        Args:
            user_id: Discord user ID
            item_id: Item ID to redeem
            current_tier: User's tier

        Returns:
            Tuple of (success: bool, message: str, promo_code: optional)
        """
        if item_id not in self.CATALOG:
            return False, "Item not found", None

        try:
            item = self.CATALOG[item_id]
            xp_cost = item["xp_cost"]

            # Check monthly limit
            can_redeem, limit_msg = await self.xp_manager.can_redeem(user_id, current_tier)
            if not can_redeem:
                return False, f"Cannot redeem: {limit_msg}", None

            # Check XP balance
            xp_data = await self.xp_manager.get_xp(user_id)
            if xp_data["balance"] < xp_cost:
                return False, f"Insufficient XP (need {xp_cost:,})", None

            # TODO: Call PrizePicks promo engine API to generate code
            # For now, using placeholder
            promo_code = await self._generate_promo_code(item_id)

            # Atomic transaction: deduct XP and create redemption
            success, deduct_msg = await self.xp_manager.deduct_xp(
                user_id,
                xp_cost,
                f"redemption_{item_id}",
            )

            if not success:
                return False, deduct_msg, None

            # Create redemption record
            redemption = Redemption(
                discord_user_id=user_id,
                item_id=item_id,
                xp_cost=xp_cost,
                promo_code=promo_code,
                status="completed",
            )
            self.db.add(redemption)

            # Update monthly counter
            now = datetime.utcnow()
            stmt = select(RedemptionCounter).where(
                and_(
                    RedemptionCounter.discord_user_id == user_id,
                    RedemptionCounter.month == now.month,
                    RedemptionCounter.year == now.year,
                )
            )
            result = await self.db.execute(stmt)
            counter = result.scalar_one_or_none()

            if counter:
                counter.count += 1
            else:
                counter = RedemptionCounter(
                    discord_user_id=user_id,
                    month=now.month,
                    year=now.year,
                    count=1,
                )
                self.db.add(counter)

            await self.db.commit()

            logger.info(f"User {user_id} redeemed {item_id} for {xp_cost} XP")
            return True, f"Redeemed {item['name']}!", promo_code

        except Exception as e:
            logger.error(f"Error redeeming item for user {user_id}: {e}")
            await self.db.rollback()
            return False, "Redemption failed. Please try again.", None

    async def _generate_promo_code(self, item_id: str) -> str:
        """
        Generate or fetch promo code for item.

        TODO: Replace with actual PrizePicks API call.
        This is a placeholder that generates a dummy code.

        Args:
            item_id: Item ID

        Returns:
            Promo code string
        """
        # TODO: Call PrizePicks promo engine API
        # POST /api/promos/generate
        # {
        #   "type": "discount_code" | "entry_credit" | "deposit_match",
        #   "value": 1000 | 5 | 25,
        #   "discord_user_id": user_id
        # }
        # Returns: {"promo_code": "DISCORD2024ABC123"}

        import secrets
        return f"PP{item_id[:3].upper()}{secrets.token_hex(4).upper()}"

    @property
    def catalog(self):
        """Get redemption catalog."""
        return self.CATALOG


class RedeemView(discord.ui.View):
    """Interactive view for redemption UI."""

    def __init__(
        self,
        catalog: Dict,
        xp_manager: XPManager,
        db_session,
        user_id: int,
        current_tier: str,
        current_xp: int,
        can_redeem: bool,
    ):
        """Initialize redeem view."""
        super().__init__(timeout=300)
        self.catalog = catalog
        self.xp_manager = xp_manager
        self.db = db_session
        self.user_id = user_id
        self.current_tier = current_tier
        self.current_xp = current_xp
        self.can_redeem = can_redeem

        # Add redeem buttons for each item
        for item_id, item in catalog.items():
            affordable = current_xp >= item["xp_cost"]
            button = discord.ui.Button(
                label=f"Redeem ({item['xp_cost']:,})",
                style=discord.ButtonStyle.green if affordable else discord.ButtonStyle.gray,
                custom_id=f"redeem_{item_id}",
                disabled=not affordable or not can_redeem,
            )
            button.callback = lambda interaction, iid=item_id: self._redeem_callback(interaction, iid)
            self.add_item(button)

    async def _redeem_callback(
        self,
        interaction: discord.Interaction,
        item_id: str,
    ) -> None:
        """Handle redeem button click."""
        await interaction.response.defer(ephemeral=True)

        # Perform redemption
        cog = interaction.client.get_cog("PromoRedemption")
        success, message, promo_code = await cog._perform_redemption(
            self.user_id,
            item_id,
            self.current_tier,
        )

        if success:
            embed = discord.Embed(
                title="Redemption Successful!",
                description=message,
                color=discord.Color.green(),
            )

            if promo_code:
                embed.add_field(
                    name="Promo Code",
                    value=f"`{promo_code}`\n\n*Copy this code at checkout*",
                    inline=False,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(
                f"Redemption failed: {message}",
                ephemeral=True,
            )


def setup(bot: commands.Bot, xp_manager: XPManager, db_session) -> None:
    """Setup function for bot to load this cog."""
    bot.add_cog(PromoRedemption(bot, xp_manager, db_session))
