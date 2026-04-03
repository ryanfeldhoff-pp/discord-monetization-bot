"""
Referral Tracking Cog (Pillar 4)

Manages referral code generation, stats viewing, and leaderboards.
Auto-generates referral codes when users link their accounts.
"""

import logging

import discord
from discord.ext import commands

from src.services.referral_manager import ReferralManager

logger = logging.getLogger(__name__)


class ReferralTrackingCog(commands.Cog):
    """
    Referral tracking cog for the ambassador/referral system.

    Features:
    - /referral code — Generate or view your referral code
    - /referral stats — View referral performance
    - /referral leaderboard — Top referrers
    - /referral link — Get shareable referral link
    - Auto-generate code on account link
    """

    def __init__(self, bot: commands.Bot, referral_manager: ReferralManager):
        self.bot = bot
        self.referral_manager = referral_manager

    referral_group = discord.SlashCommandGroup("referral", "Referral program")

    @referral_group.command(name="code", description="View or generate your referral code")
    async def referral_code(self, ctx: discord.ApplicationContext) -> None:
        """Get user's referral code, creating one if needed."""
        await ctx.defer(ephemeral=True)

        try:
            data = await self.referral_manager.get_or_create_code(ctx.author.id)

            if not data:
                await ctx.respond("Failed to generate referral code. Please try again.", ephemeral=True)
                return

            embed = discord.Embed(
                title="🔗 Your Referral Code",
                color=0x8B5CF6,
            )
            embed.add_field(name="Code", value=f"**`{data['code']}`**", inline=True)
            embed.add_field(name="Signups", value=str(data.get("total_signups", 0)), inline=True)
            embed.add_field(name="FTDs", value=str(data.get("total_ftds", 0)), inline=True)

            if data.get("ambassador_tier"):
                tier_display = data["ambassador_tier"].replace("_", " ").title()
                embed.add_field(name="Ambassador Tier", value=f"⭐ {tier_display}", inline=True)

            embed.add_field(
                name="Share Link",
                value=data.get("referral_url", "Link not available"),
                inline=False,
            )

            embed.set_footer(text="Share your code to earn rewards when friends sign up and deposit!")
            await ctx.respond(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in referral code command: {e}")
            await ctx.respond("Error retrieving referral code.", ephemeral=True)

    @referral_group.command(name="stats", description="View your referral performance")
    async def referral_stats(self, ctx: discord.ApplicationContext) -> None:
        """Show detailed referral stats."""
        await ctx.defer(ephemeral=True)

        try:
            stats = await self.referral_manager.get_referral_stats(ctx.author.id)

            if not stats:
                await ctx.respond("No referral data found. Use `/referral code` to get started!", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"📊 Referral Stats — {ctx.author.name}",
                color=0x8B5CF6,
            )
            embed.add_field(name="Total Signups", value=str(stats.get("total_signups", 0)), inline=True)
            embed.add_field(name="Total FTDs", value=str(stats.get("total_ftds", 0)), inline=True)
            embed.add_field(
                name="Total Earned",
                value=f"${stats.get('total_earned_cents', 0) / 100:.2f}",
                inline=True,
            )

            # Conversion rate
            signups = stats.get("total_signups", 0)
            ftds = stats.get("total_ftds", 0)
            conv_rate = f"{(ftds / signups * 100):.1f}%" if signups > 0 else "—"
            embed.add_field(name="Conversion Rate", value=conv_rate, inline=True)

            # Ambassador tier
            tier = stats.get("ambassador_tier")
            if tier:
                tier_display = tier.replace("_", " ").title()
                embed.add_field(name="Ambassador Tier", value=f"⭐ {tier_display}", inline=True)
            else:
                embed.add_field(name="Ambassador Tier", value="Not yet qualified (5 FTDs needed)", inline=True)

            # Recent conversions
            recent = stats.get("recent_conversions", [])
            if recent:
                lines = []
                for c in recent[:5]:
                    emoji = "💰" if c["type"] == "ftd" else "📝"
                    reward = f" (+${c['reward_cents']/100:.2f})" if c["reward_cents"] > 0 else ""
                    lines.append(f"{emoji} {c['type'].upper()}{reward} via {c.get('source', 'link')}")
                embed.add_field(name="Recent Activity", value="\n".join(lines), inline=False)

            await ctx.respond(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in referral stats command: {e}")
            await ctx.respond("Error retrieving referral stats.", ephemeral=True)

    @referral_group.command(name="leaderboard", description="Top referrers")
    async def referral_leaderboard(self, ctx: discord.ApplicationContext) -> None:
        """Show top referrers."""
        await ctx.defer()

        try:
            lb = await self.referral_manager.get_referral_leaderboard(limit=10)

            embed = discord.Embed(
                title="🏆 Top Referrers",
                description="Ranked by first-time deposits generated",
                color=0x8B5CF6,
            )

            if lb:
                lines = []
                medals = {1: "🥇", 2: "🥈", 3: "🥉"}
                for entry in lb:
                    prefix = medals.get(entry["rank"], f"#{entry['rank']}")
                    try:
                        user = await self.bot.fetch_user(entry["user_id"])
                        name = user.name
                    except discord.NotFound:
                        name = f"User {entry['user_id']}"

                    tier_badge = ""
                    if entry.get("tier"):
                        tier_badge = f" ⭐{entry['tier'].replace('_', ' ').title()}"

                    lines.append(
                        f"{prefix} **{name}** — {entry['ftds']} FTDs, "
                        f"{entry['signups']} signups{tier_badge}"
                    )
                embed.add_field(name="Rankings", value="\n".join(lines), inline=False)
            else:
                embed.description = "No referrals yet. Be the first!"

            embed.set_footer(text="Use /referral code to get your referral link!")
            await ctx.respond(embed=embed)

        except Exception as e:
            logger.error(f"Error in referral leaderboard: {e}")
            await ctx.respond("Failed to load leaderboard.", ephemeral=True)

    @referral_group.command(name="link", description="Get your shareable referral link")
    async def referral_link(self, ctx: discord.ApplicationContext) -> None:
        """Get a ready-to-share referral link."""
        await ctx.defer(ephemeral=True)

        try:
            data = await self.referral_manager.get_or_create_code(ctx.author.id)

            if not data or not data.get("referral_url"):
                await ctx.respond("Failed to generate referral link.", ephemeral=True)
                return

            embed = discord.Embed(
                title="🔗 Your Referral Link",
                description=(
                    f"Share this link with friends:\n\n"
                    f"**{data['referral_url']}**\n\n"
                    f"Code: `{data['code']}`\n\n"
                    "You'll earn **$25+** for each friend who makes a first deposit!"
                ),
                color=0x10B981,
            )
            await ctx.respond(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in referral link command: {e}")
            await ctx.respond("Error generating link.", ephemeral=True)


def setup(bot: commands.Bot) -> None:
    pass  # Loaded via bot.add_cog() in main.py
