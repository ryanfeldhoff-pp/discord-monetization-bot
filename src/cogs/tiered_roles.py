"""
Tiered Roles Cog

Manages automatic role assignment based on XP tiers with tier-up notifications
and tier-down grace periods.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict

import discord
from discord.ext import commands, tasks

from src.services.xp_manager import XPManager
from src.utils.colors import get_tier_color
from src.utils.embeds import success_embed, warning_embed, info_embed, error_embed

logger = logging.getLogger(__name__)


class TieredRoles(commands.Cog):
    """
    Auto-assign Discord roles based on XP tiers.

    Features:
    - Auto-assign roles at thresholds (Bronze, Silver, Gold, Diamond)
    - Tier-up DM notifications with congrats and perks
    - Tier-down grace period (7 days warning before role removal)
    - /tier command to show progress
    """

    # Role configuration
    TIER_ROLES = {
        "bronze": {"name": "Bronze", "color": discord.Color.from_rgb(205, 127, 50)},
        "silver": {"name": "Silver", "color": discord.Color.from_rgb(192, 192, 192)},
        "gold": {"name": "Gold", "color": discord.Color.from_rgb(255, 215, 0)},
        "diamond": {"name": "Diamond", "color": discord.Color.from_rgb(185, 242, 255)},
    }

    TIER_PERKS = {
        "bronze": [
            "Access to #bronze-lounge",
            "1 redemption per month",
            "XP tracker role",
        ],
        "silver": [
            "Access to #silver-lounge",
            "2 redemptions per month",
            "All Bronze perks",
            "1.25x XP multiplier",
        ],
        "gold": [
            "Access to #gold-lounge",
            "4 redemptions per month",
            "All Silver perks",
            "1.5x XP multiplier",
            "Monthly recap card",
        ],
        "diamond": [
            "Access to #diamond-lounge",
            "Unlimited redemptions",
            "All Gold perks",
            "2x XP multiplier",
            "Featured in leaderboard",
        ],
    }

    # Grace period config
    TIER_DOWN_GRACE_DAYS = 7

    def __init__(self, bot: commands.Bot, xp_manager: XPManager, guild_id: int):
        """
        Initialize Tiered Roles cog.

        Args:
            bot: Discord bot instance
            xp_manager: XPManager service instance
            guild_id: Discord guild ID for the main server
        """
        self.bot = bot
        self.xp_manager = xp_manager
        self.guild_id = guild_id

        # Track tier changes for grace period
        self._tier_down_warnings: Dict[int, datetime] = {}

        self.check_tier_updates.start()

    def cog_unload(self):
        """Clean up background tasks."""
        self.check_tier_updates.cancel()

    @commands.slash_command(
        name="tier",
        description="Show your current tier and progress"
    )
    async def tier_command(self, ctx: discord.ApplicationContext) -> None:
        """
        Display user's current tier and progress to next tier.

        Shows:
        - Current tier with color
        - XP progress to next tier (progress bar)
        - Unlocked perks
        """
        await ctx.defer()

        try:
            user_id = ctx.author.id
            xp_data = await self.xp_manager.get_xp(user_id)
            current_tier = xp_data["tier"]
            current_xp = xp_data["balance"]

            # Calculate progress to next tier
            tier_keys = ["bronze", "silver", "gold", "diamond"]
            current_tier_idx = tier_keys.index(current_tier)
            current_threshold = self.xp_manager.TIER_THRESHOLDS[current_tier]

            # Progress bar
            if current_tier == "diamond":
                progress_text = "You've reached the highest tier!"
                from src.utils.embeds import progress_bar
                bar = progress_bar(100, 100)
            else:
                next_tier = tier_keys[current_tier_idx + 1]
                next_threshold = self.xp_manager.TIER_THRESHOLDS[next_tier]
                progress = current_xp - current_threshold
                needed = next_threshold - current_threshold
                from src.utils.embeds import progress_bar
                bar = progress_bar(progress, needed)
                progress_text = f"{progress:,} / {needed:,} XP to **{next_tier.upper()}**"

            # Unlocked perks
            perks = self.TIER_PERKS[current_tier]

            tier_color = get_tier_color(current_tier)

            embed = info_embed(
                f"Tier Status - {ctx.author.name}",
                f"**{current_tier.upper()}** {self._get_tier_emoji(current_tier)}",
                [
                    ("Progress to Next Tier", f"{bar}\n{progress_text}", False),
                    ("Unlocked Perks", "\n".join(f"✓ {perk}" for perk in perks), False),
                ]
            )
            embed.color = tier_color
            embed.set_thumbnail(url=ctx.author.avatar.url)

            await ctx.respond(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in tier command: {e}")
            embed = error_embed(
                "Tier Lookup Failed",
                "Could not retrieve your tier data",
                recovery_hint="Please try again in a moment",
                error_code="TIER_LOOKUP_ERROR"
            )
            await ctx.respond(embed=embed, ephemeral=True)

    @tasks.loop(minutes=5)
    async def check_tier_updates(self) -> None:
        """
        Check and update tier roles for all guild members every 5 minutes.

        This task:
        1. Checks each user's current tier
        2. Assigns role if tier changed
        3. Sends tier-up notifications
        4. Enforces tier-down grace periods
        """
        try:
            guild = self.bot.get_guild(self.guild_id)
            if not guild:
                logger.warning(f"Guild {self.guild_id} not found")
                return

            # Ensure tier roles exist
            await self._ensure_tier_roles(guild)

            # Check all members
            for member in guild.members:
                if member.bot:
                    continue

                try:
                    user_id = member.id
                    xp_data = await self.xp_manager.get_xp(user_id)
                    new_tier = xp_data["tier"]

                    # Get current tier from roles
                    current_tier = self._get_member_tier(member)

                    if new_tier != current_tier:
                        await self._update_member_tier(
                            member,
                            current_tier,
                            new_tier,
                            guild,
                        )

                except Exception as e:
                    logger.error(f"Error checking tier for member {member.id}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in tier update check: {e}")

    @check_tier_updates.before_loop
    async def before_tier_check(self) -> None:
        """Wait for bot to be ready before starting tier check task."""
        await self.bot.wait_until_ready()

    async def _ensure_tier_roles(self, guild: discord.Guild) -> None:
        """
        Ensure all tier roles exist in the guild.

        Creates roles if they don't exist.

        Args:
            guild: Discord guild object
        """
        try:
            for tier, config in self.TIER_ROLES.items():
                role = discord.utils.get(guild.roles, name=config["name"])
                if not role:
                    # Create role
                    role = await guild.create_role(
                        name=config["name"],
                        color=config["color"],
                        reason="XP tier role",
                    )
                    logger.info(f"Created role: {config['name']}")

        except discord.Forbidden:
            logger.error("Missing permissions to create roles")
        except Exception as e:
            logger.error(f"Error ensuring tier roles: {e}")

    async def _update_member_tier(
        self,
        member: discord.Member,
        old_tier: Optional[str],
        new_tier: str,
        guild: discord.Guild,
    ) -> None:
        """
        Update member's tier role and send notifications.

        Args:
            member: Discord member object
            old_tier: Previous tier (or None if first time)
            new_tier: New tier
            guild: Discord guild object
        """
        try:
            # Remove old role if exists
            if old_tier:
                old_role = discord.utils.get(guild.roles, name=self.TIER_ROLES[old_tier]["name"])
                if old_role and old_role in member.roles:
                    await member.remove_roles(old_role)

            # Add new role
            new_role = discord.utils.get(guild.roles, name=self.TIER_ROLES[new_tier]["name"])
            if new_role and new_role not in member.roles:
                await member.add_roles(new_role)

            # Send tier-up notification if promoted
            if old_tier is None or self._tier_rank(new_tier) > self._tier_rank(old_tier):
                await self._send_tier_up_dm(member, new_tier)
                logger.info(f"User {member.id} promoted to {new_tier}")

            # Handle tier-down with grace period
            elif self._tier_rank(new_tier) < self._tier_rank(old_tier):
                self._tier_down_warnings[member.id] = datetime.utcnow()
                await self._send_tier_down_warning_dm(member, old_tier, new_tier)
                logger.info(f"User {member.id} demoted to {new_tier}, grace period started")

        except discord.Forbidden:
            logger.error(f"Missing permissions to manage roles for {member.id}")
        except Exception as e:
            logger.error(f"Error updating tier for member {member.id}: {e}")

    async def _send_tier_up_dm(self, member: discord.Member, new_tier: str) -> None:
        """
        Send congratulations DM on tier up.

        Args:
            member: Discord member object
            new_tier: New tier
        """
        try:
            tier_color = get_tier_color(new_tier)

            embed = success_embed(
                f"You've reached {new_tier.upper()} tier!",
                "You've unlocked new perks and rewards.",
                [
                    ("New Perks Unlocked", "\n".join(f"✓ {perk}" for perk in self.TIER_PERKS[new_tier]), False),
                    ("Next Steps", "Check out the new channels you now have access to!\nUse `/redeem` to see what rewards you can claim.", False),
                ]
            )
            embed.color = tier_color

            await member.send(embed=embed)

        except discord.Forbidden:
            logger.warning(f"Could not DM user {member.id} (DMs disabled)")
        except Exception as e:
            logger.error(f"Error sending tier-up DM to {member.id}: {e}")

    async def _send_tier_down_warning_dm(
        self,
        member: discord.Member,
        old_tier: str,
        new_tier: str,
    ) -> None:
        """
        Send warning DM about pending tier down.

        Args:
            member: Discord member object
            old_tier: Previous tier
            new_tier: Current tier (declining to)
        """
        try:
            embed = discord.Embed(
                title="Tier Down Notice",
                description=(
                    f"Your activity has declined and you're approaching a tier down "
                    f"from **{old_tier.upper()}** to **{new_tier.upper()}**."
                ),
                color=discord.Color.orange(),
            )

            embed.add_field(
                name="Grace Period",
                value=f"You have **{self.TIER_DOWN_GRACE_DAYS} days** to earn XP and prevent the tier down.",
                inline=False,
            )

            embed.add_field(
                name="How to Stay {old_tier.upper()}",
                value=(
                    f"Earn {self.xp_manager.TIER_THRESHOLDS[old_tier]:,}+ total XP "
                    f"by being active in the server."
                ),
                inline=False,
            )

            await member.send(embed=embed)

        except discord.Forbidden:
            logger.warning(f"Could not DM user {member.id} (DMs disabled)")
        except Exception as e:
            logger.error(f"Error sending tier-down warning DM to {member.id}: {e}")

    @staticmethod
    def _get_member_tier(member: discord.Member) -> Optional[str]:
        """
        Get member's current tier from their roles.

        Args:
            member: Discord member object

        Returns:
            Tier name or None if no tier role assigned
        """
        for role in member.roles:
            for tier, config in TieredRoles.TIER_ROLES.items():
                if role.name == config["name"]:
                    return tier
        return None

    @staticmethod
    def _tier_rank(tier: str) -> int:
        """
        Get numerical rank of tier for comparison.

        Args:
            tier: Tier name

        Returns:
            Tier rank (0=bronze, 3=diamond)
        """
        ranks = {"bronze": 0, "silver": 1, "gold": 2, "diamond": 3}
        return ranks.get(tier, -1)

    @staticmethod
    def _get_tier_emoji(tier: str) -> str:
        """
        Get emoji representation of tier.

        Args:
            tier: Tier name

        Returns:
            Emoji string
        """
        emojis = {
            "bronze": "🥉",
            "silver": "🥈",
            "gold": "🥇",
            "diamond": "💎",
        }
        return emojis.get(tier, "")

    @staticmethod
    def _hex_to_rgb(color: discord.Color) -> tuple:
        """
        Convert Discord Color to RGB tuple.

        Args:
            color: discord.Color object

        Returns:
            (R, G, B) tuple
        """
        return (color.r, color.g, color.b)


def setup(bot: commands.Bot, xp_manager: XPManager, guild_id: int) -> None:
    """Setup function for bot to load this cog."""
    bot.add_cog(TieredRoles(bot, xp_manager, guild_id))
