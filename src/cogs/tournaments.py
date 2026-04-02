"""
Tournaments Cog (Pillar 3)

Prediction tournament commands — enter, submit picks, view leaderboard.
Admin commands for creating and scoring tournaments.
"""

import logging
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks

from src.services.tournament_engine import TournamentEngine
from src.services.xp_manager import XPManager

logger = logging.getLogger(__name__)


class PredictionModal(discord.ui.Modal):
    """Modal for submitting tournament predictions."""

    def __init__(self, tournament_id: int, picks_required: int, cog: "TournamentsCog"):
        super().__init__(title="Submit Predictions")
        self.tournament_id = tournament_id
        self.cog = cog

        self.picks_input = discord.ui.InputText(
            label=f"Enter {picks_required} picks (one per line)",
            placeholder="Player Name MORE/LESS Stat Line\ne.g. LeBron James MORE 27.5 Points",
            style=discord.InputTextStyle.long,
            required=True,
        )
        self.add_item(self.picks_input)

    async def callback(self, interaction: discord.Interaction):
        """Parse and submit predictions."""
        lines = self.picks_input.value.strip().split("\n")
        predictions = []

        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Simple parsing: "Player MORE/LESS Line Stat"
            predictions.append({
                "raw": line,
                "projection_id": None,  # TODO: match against /api/projections
            })

        success, msg = await self.cog.engine.submit_predictions(
            self.tournament_id, interaction.user.id, predictions
        )

        if success:
            await interaction.response.send_message(
                f"✅ {msg}", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ {msg}", ephemeral=True
            )


class TournamentsCog(commands.Cog):
    """
    Tournaments cog for prediction competitions.

    Features:
    - /tournament list — Browse active and upcoming tournaments
    - /tournament enter — Enter a tournament (pays XP fee if applicable)
    - /tournament predict — Submit predictions via modal
    - /tournament leaderboard — View tournament standings
    - /tournament create — Create tournament (admin)
    - /tournament score — Trigger scoring (admin)
    - Background task: auto-open and auto-lock tournaments on schedule
    """

    def __init__(self, bot: commands.Bot, engine: TournamentEngine, xp_manager: XPManager):
        self.bot = bot
        self.engine = engine
        self.xp_manager = xp_manager
        self.check_tournament_lifecycle.start()

    def cog_unload(self):
        self.check_tournament_lifecycle.cancel()

    tournament_group = discord.SlashCommandGroup("tournament", "Prediction tournaments")

    @tournament_group.command(name="list", description="View active and upcoming tournaments")
    async def tournament_list(self, ctx: discord.ApplicationContext) -> None:
        """List active and upcoming tournaments."""
        await ctx.defer()

        try:
            active = await self.engine.list_tournaments(status="open")
            upcoming = await self.engine.list_tournaments(status="upcoming")

            embed = discord.Embed(
                title="🏆 Prediction Tournaments",
                color=0x8B5CF6,
            )

            if active:
                lines = []
                for t in active:
                    fee = f"{t['entry_fee_xp']} XP" if t['entry_fee_xp'] > 0 else "Free"
                    lines.append(f"**#{t['id']}** {t['title']} ({fee})")
                embed.add_field(
                    name="🟢 Open Now",
                    value="\n".join(lines) or "None",
                    inline=False,
                )
            else:
                embed.add_field(name="🟢 Open Now", value="No active tournaments", inline=False)

            if upcoming:
                lines = []
                for t in upcoming:
                    lines.append(f"**#{t['id']}** {t['title']} — Opens {t['opens_at']}")
                embed.add_field(
                    name="🔜 Upcoming",
                    value="\n".join(lines[:5]) or "None",
                    inline=False,
                )

            embed.set_footer(text="Use /tournament enter [id] to join!")
            await ctx.respond(embed=embed)

        except Exception as e:
            logger.error(f"Error listing tournaments: {e}")
            await ctx.respond("Failed to load tournaments.", ephemeral=True)

    @tournament_group.command(name="enter", description="Enter a tournament")
    @discord.option(name="tournament_id", description="Tournament ID to enter", required=True)
    async def tournament_enter(self, ctx: discord.ApplicationContext, tournament_id: int) -> None:
        """Enter a tournament."""
        await ctx.defer(ephemeral=True)

        try:
            success, msg = await self.engine.enter_tournament(tournament_id, ctx.author.id)

            if success:
                tournament = await self.engine.get_tournament(tournament_id)
                embed = discord.Embed(
                    title="✅ Entered Tournament!",
                    description=f"**{tournament['title']}**\n\n{msg}",
                    color=0x10B981,
                )
                embed.add_field(
                    name="Next Step",
                    value=f"Use `/tournament predict {tournament_id}` to submit your {tournament['picks_required']} picks!",
                    inline=False,
                )
                await ctx.respond(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="❌ Could Not Enter",
                    description=msg,
                    color=0xEF4444,
                )
                await ctx.respond(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error entering tournament: {e}")
            await ctx.respond("Failed to enter tournament.", ephemeral=True)

    @tournament_group.command(name="predict", description="Submit your predictions")
    @discord.option(name="tournament_id", description="Tournament ID", required=True)
    async def tournament_predict(self, ctx: discord.ApplicationContext, tournament_id: int) -> None:
        """Open prediction submission modal."""
        try:
            tournament = await self.engine.get_tournament(tournament_id)
            if not tournament:
                await ctx.respond("Tournament not found.", ephemeral=True)
                return

            if tournament["status"] != "open":
                await ctx.respond("Tournament is not accepting predictions.", ephemeral=True)
                return

            modal = PredictionModal(tournament_id, tournament["picks_required"], self)
            await ctx.send_modal(modal)

        except Exception as e:
            logger.error(f"Error opening prediction modal: {e}")
            await ctx.respond("Failed to open predictions.", ephemeral=True)

    @tournament_group.command(name="leaderboard", description="View tournament standings")
    @discord.option(name="tournament_id", description="Tournament ID", required=True)
    async def tournament_leaderboard(self, ctx: discord.ApplicationContext, tournament_id: int) -> None:
        """Display tournament leaderboard."""
        await ctx.defer()

        try:
            tournament = await self.engine.get_tournament(tournament_id)
            if not tournament:
                await ctx.respond("Tournament not found.", ephemeral=True)
                return

            lb = await self.engine.get_leaderboard(tournament_id, limit=15)

            embed = discord.Embed(
                title=f"🏆 {tournament['title']} — Leaderboard",
                description=f"Status: **{tournament['status'].upper()}** • {tournament['participants']} participants",
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
                    lines.append(f"{prefix} **{name}** — {entry['score']:.1f} pts")
                embed.add_field(name="Rankings", value="\n".join(lines), inline=False)
            else:
                embed.add_field(name="Rankings", value="No entries scored yet.", inline=False)

            await ctx.respond(embed=embed)

        except Exception as e:
            logger.error(f"Error showing tournament leaderboard: {e}")
            await ctx.respond("Failed to load leaderboard.", ephemeral=True)

    @tournament_group.command(name="create", description="Create a new tournament (admin)")
    @discord.option(name="title", description="Tournament title", required=True, input_type=str)
    @discord.option(name="sport", description="Sport filter (optional)", required=False, input_type=str, default=None)
    @discord.option(name="entry_fee_xp", description="XP entry fee (0=free)", required=False, input_type=int, default=0)
    @discord.option(name="picks_required", description="Number of picks (default 5)", required=False, input_type=int, default=5)
    @discord.option(name="duration_hours", description="Hours until lock (default 48)", required=False, input_type=int, default=48)
    @commands.has_permissions(administrator=True)
    async def tournament_create(
        self,
        ctx: discord.ApplicationContext,
        title: str,
        sport: str = None,
        entry_fee_xp: int = 0,
        picks_required: int = 5,
        duration_hours: int = 48,
    ) -> None:
        """Create a new tournament (admin only)."""
        await ctx.defer(ephemeral=True)

        try:
            opens_at = datetime.utcnow()
            locks_at = opens_at + timedelta(hours=duration_hours)

            tournament = await self.engine.create_tournament(
                title=title,
                description=f"Prediction tournament for {sport or 'all sports'}",
                sport=sport,
                entry_fee_xp=entry_fee_xp,
                picks_required=picks_required,
                prize_pool={"1st": "Free Entry ($10)", "2nd": "Free Entry ($5)", "3rd": "Discount Code"},
                opens_at=opens_at,
                locks_at=locks_at,
                created_by=ctx.author.id,
            )

            # Auto-open immediately
            await self.engine.update_tournament_status(tournament.id, "open")

            embed = discord.Embed(
                title="✅ Tournament Created",
                description=f"**{title}** (ID: #{tournament.id})",
                color=0x10B981,
            )
            embed.add_field(name="Entry Fee", value=f"{entry_fee_xp} XP" if entry_fee_xp else "Free", inline=True)
            embed.add_field(name="Picks", value=str(picks_required), inline=True)
            embed.add_field(name="Locks", value=f"<t:{int(locks_at.timestamp())}:R>", inline=True)

            await ctx.respond(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error creating tournament: {e}")
            await ctx.respond("Failed to create tournament.", ephemeral=True)

    @tournament_group.command(name="score", description="Score a tournament (admin)")
    @discord.option(name="tournament_id", description="Tournament ID to score", required=True)
    @commands.has_permissions(administrator=True)
    async def tournament_score(self, ctx: discord.ApplicationContext, tournament_id: int) -> None:
        """Trigger tournament scoring (admin only)."""
        await ctx.defer(ephemeral=True)

        try:
            # TODO: Fetch actual results from /api/entries/results
            # For now, respond with instructions
            embed = discord.Embed(
                title="🔧 Tournament Scoring",
                description=(
                    f"Tournament #{tournament_id} scoring requires backend API integration.\n\n"
                    "**Backend team:** Implement `POST /api/entries/results` to resolve predictions.\n"
                    "Once available, scoring will be automatic."
                ),
                color=0xF59E0B,
            )
            await ctx.respond(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error scoring tournament: {e}")
            await ctx.respond("Failed to score tournament.", ephemeral=True)

    @tasks.loop(minutes=5)
    async def check_tournament_lifecycle(self) -> None:
        """Auto-open upcoming tournaments and auto-lock expired ones."""
        try:
            now = datetime.utcnow()

            # Open tournaments that should be open
            upcoming = await self.engine.list_tournaments(status="upcoming")
            for t in upcoming:
                if t["opens_at"] and datetime.fromisoformat(t["opens_at"]) <= now:
                    await self.engine.update_tournament_status(t["id"], "open")
                    logger.info(f"Auto-opened tournament #{t['id']}")

            # Lock tournaments that should be locked
            open_tournaments = await self.engine.list_tournaments(status="open")
            for t in open_tournaments:
                if t["locks_at"] and datetime.fromisoformat(t["locks_at"]) <= now:
                    await self.engine.update_tournament_status(t["id"], "locked")
                    logger.info(f"Auto-locked tournament #{t['id']}")

        except Exception as e:
            logger.error(f"Error in tournament lifecycle check: {e}")

    @check_tournament_lifecycle.before_loop
    async def before_lifecycle_check(self) -> None:
        await self.bot.wait_until_ready()


def setup(bot: commands.Bot) -> None:
    pass  # Loaded via bot.add_cog() in main.py
