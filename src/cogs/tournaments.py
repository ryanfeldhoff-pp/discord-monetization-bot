"""
Community Tournaments Cog

Manages weekly prediction tournaments with leaderboards, scoring, and XP rewards.
Features slash commands for tournament management, prediction submission, and
leaderboard viewing, plus background tasks for tournament lifecycle automation.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict

import discord
from discord.ext import commands, tasks
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.event_models import Tournament, TournamentEntry
from src.services.xp_manager import XPManager
from src.utils.colors import PRIZEPICKS_PRIMARY
from src.utils.embeds import success_embed, error_embed, info_embed, empty_state_embed, loading_embed, leaderboard_embed
from src.utils.pagination import PaginatedView
from src.utils.validation import validate_length, validate_range, validate_datetime
from src.utils.views import ConfirmView

logger = logging.getLogger(__name__)

# Medal emojis for top 3
MEDALS = ["🥇", "🥈", "🥉"]


class TournamentListView(discord.ui.View):
    """Paginated view for tournament listings."""

    def __init__(self, tournaments: List[Tournament], cog: "TournamentsCog"):
        """
        Initialize tournament list view.

        Args:
            tournaments: List of tournament records
            cog: Reference to TournamentsCog
        """
        super().__init__(timeout=300)
        self.tournaments = tournaments
        self.cog = cog
        self.current_page = 0
        self.page_size = 5

        self.update_buttons()

    def update_buttons(self) -> None:
        """Update button states based on current page."""
        self.previous_button.disabled = self.current_page == 0
        max_page = (len(self.tournaments) - 1) // self.page_size
        self.next_button.disabled = self.current_page >= max_page

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.blurple)
    async def previous_button(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        """Navigate to previous page."""
        self.current_page = max(0, self.current_page - 1)
        self.update_buttons()
        await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple)
    async def next_button(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        """Navigate to next page."""
        max_page = (len(self.tournaments) - 1) // self.page_size
        self.current_page = min(max_page, self.current_page + 1)
        self.update_buttons()
        await interaction.response.defer()


class TournamentEntryView(discord.ui.View):
    """Confirmation view for tournament entry."""

    def __init__(self, tournament: Tournament, cog: "TournamentsCog"):
        """
        Initialize tournament entry confirmation view.

        Args:
            tournament: Tournament record
            cog: Reference to TournamentsCog
        """
        super().__init__(timeout=300)
        self.tournament = tournament
        self.cog = cog
        self.user_id: Optional[int] = None
        self.confirmed = False

    @discord.ui.button(label="Confirm Entry", style=discord.ButtonStyle.green)
    async def confirm_button(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        """Confirm tournament entry."""
        self.user_id = interaction.user.id
        self.confirmed = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel_button(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        """Cancel tournament entry."""
        self.confirmed = False
        await interaction.response.defer()
        self.stop()


class TournamentsCog(commands.Cog):
    """
    Community Tournaments cog.

    Manages tournament lifecycle, predictions, scoring, and leaderboards.
    """

    def __init__(
        self,
        bot: commands.Bot,
        tournament_engine: Optional[object] = None,
        xp_manager: Optional[XPManager] = None,
    ):
        """
        Initialize Tournaments cog.

        Args:
            bot: Discord bot instance
            tournament_engine: Optional tournament engine for advanced scoring
            xp_manager: XP manager for awarding tournament XP
        """
        self.bot = bot
        self.db = bot.db
        self.tournament_engine = tournament_engine
        self.xp_manager = xp_manager or bot.xp_manager

        self.auto_start_tournaments.start()
        self.auto_close_tournaments.start()
        self.weekly_tournament_creator.start()

    def cog_unload(self) -> None:
        """Clean up background tasks."""
        self.auto_start_tournaments.cancel()
        self.auto_close_tournaments.cancel()
        self.weekly_tournament_creator.cancel()

    @commands.slash_command(
        name="tournament",
        description="Manage and view community tournaments",
    )
    async def tournament_group(self, ctx: discord.ApplicationContext) -> None:
        """Slash command group for tournaments."""
        pass

    @tournament_group.command(
        name="list",
        description="Show active and upcoming tournaments",
    )
    async def list_tournaments(self, ctx: discord.ApplicationContext) -> None:
        """
        List all active and upcoming tournaments.

        Args:
            ctx: Discord application context
        """
        await ctx.defer()

        try:
            stmt = select(Tournament).where(
                and_(
                    Tournament.guild_id == ctx.guild_id,
                    Tournament.status.in_(["upcoming", "active"]),
                )
            )
            result = await self.db.execute(stmt)
            tournaments = result.scalars().all()

            if not tournaments:
                embed = empty_state_embed(
                    "Tournaments",
                    "No tournaments active",
                    ["/tournament list"]
                )
                await ctx.followup.send(embed=embed)
                return

            # Create paginated embeds (10 per page)
            page_size = 10
            embeds = []
            for page_num in range((len(tournaments) + page_size - 1) // page_size):
                embed = self._build_tournament_list_embed(
                    tournaments,
                    page_num,
                    page_size,
                    len(tournaments),
                )
                embeds.append(embed)

            if len(embeds) == 1:
                await ctx.followup.send(embed=embeds[0])
            else:
                view = PaginatedView(embeds)
                await ctx.followup.send(embed=embeds[0], view=view)

        except Exception as e:
            logger.exception("Error listing tournaments")
            await ctx.followup.send(
                embed=error_embed(
                    "List Failed",
                    "Could not retrieve tournaments",
                    recovery_hint="Try again",
                    error_code="TOURNAMENT_LIST_ERROR"
                ),
                ephemeral=True,
            )

    def _build_tournament_list_embed(
        self,
        tournaments: List[Tournament],
        page: int,
        page_size: int,
        total: int,
    ) -> discord.Embed:
        """Build tournament list embed for given page."""
        start = page * page_size
        end = start + page_size
        page_tournaments = tournaments[start:end]

        embed = info_embed(
            "Active Tournaments",
            f"Page {page + 1} of {(total + page_size - 1) // page_size}"
        )

        for t in page_tournaments:
            status_emoji = "🟢" if t.status == "active" else "⏳"
            embed.add_field(
                name=f"{status_emoji} {t.title[:40]}",
                value=(
                    f"Type: {t.tournament_type}\n"
                    f"Entry: {t.entry_fee_xp} XP\n"
                    f"Starts: {t.starts_at.strftime('%Y-%m-%d %H:%M')}\n"
                    f"**ID: `{t.id}`**"
                ),
                inline=False,
            )

        return embed

    @tournament_group.command(
        name="enter",
        description="Enter a tournament",
    )
    async def enter_tournament(
        self,
        ctx: discord.ApplicationContext,
        tournament_id: int,
    ) -> None:
        """
        Enter a tournament (deducts entry fee XP).

        Args:
            ctx: Discord application context
            tournament_id: ID of tournament to enter
        """
        await ctx.defer()

        try:
            # Fetch tournament
            stmt = select(Tournament).where(Tournament.id == tournament_id)
            result = await self.db.execute(stmt)
            tournament = result.scalars().first()

            if not tournament:
                await ctx.followup.send(
                    embed=error_embed(
                        "Not Found",
                        f"No tournament with ID: {tournament_id}",
                        recovery_hint="Check the ID with `/tournament list`"
                    ),
                    ephemeral=True,
                )
                return

            if tournament.status != "upcoming":
                await ctx.followup.send(
                    embed=error_embed(
                        "Cannot Enter",
                        f"Tournament is {tournament.status} - entries closed",
                        recovery_hint="Look for upcoming tournaments"
                    ),
                    ephemeral=True,
                )
                return

            # Show confirmation
            embed = info_embed(
                f"Enter Tournament {tournament_id}?",
                tournament.title[:60],
                fields=[
                    ("Entry Fee", f"{tournament.entry_fee_xp} XP", True),
                    ("Participants", str(tournament.max_participants or "∞"), True),
                ]
            )

            view = TournamentEntryView(tournament, self)
            await ctx.followup.send(embed=embed, view=view, ephemeral=True)

            # Wait for confirmation
            await view.wait()
            if view.confirmed:
                # Deduct entry fee and create entry
                await self.xp_manager.deduct_xp(
                    ctx.author.id,
                    tournament.entry_fee_xp,
                    "tournament_entry",
                )

                entry = TournamentEntry(
                    tournament_id=tournament_id,
                    discord_user_id=ctx.author.id,
                    predictions_json=json.dumps([]),
                    entered_at=datetime.utcnow(),
                )
                self.db.add(entry)
                await self.db.commit()

                await ctx.followup.send(
                    embed=success_embed(
                        "Entered",
                        tournament.title[:50]
                    ),
                    ephemeral=True,
                )

        except Exception as e:
            logger.exception("Error entering tournament")
            await ctx.followup.send(
                embed=error_embed(
                    "Entry Failed",
                    "Could not enter tournament",
                    recovery_hint="Try again",
                    error_code="TOURNAMENT_ENTER_ERROR"
                ),
                ephemeral=True,
            )

    @tournament_group.command(
        name="predict",
        description="Submit or update tournament predictions",
    )
    async def submit_predictions(
        self,
        ctx: discord.ApplicationContext,
        tournament_id: int,
        picks: str,
    ) -> None:
        """
        Submit predictions for a tournament.

        Args:
            ctx: Discord application context
            tournament_id: ID of tournament
            picks: Comma-separated predictions (e.g., "more,less,more,more")
        """
        await ctx.defer()

        try:
            # Parse picks
            prediction_list = [p.strip().lower() for p in picks.split(",")]
            if not all(p in ["more", "less"] for p in prediction_list):
                await ctx.followup.send(
                    embed=error_embed(
                        "Invalid Format",
                        'Predictions must be "more" or "less" (comma-separated)',
                        recovery_hint='Example: more,less,more,more'
                    ),
                    ephemeral=True,
                )
                return

            # Fetch tournament entry
            stmt = select(TournamentEntry).where(
                and_(
                    TournamentEntry.tournament_id == tournament_id,
                    TournamentEntry.discord_user_id == ctx.author.id,
                )
            )
            result = await self.db.execute(stmt)
            entry = result.scalars().first()

            if not entry:
                await ctx.followup.send(
                    embed=error_embed(
                        "Not Entered",
                        "You must enter the tournament first",
                        recovery_hint=f"/tournament enter {tournament_id}"
                    ),
                    ephemeral=True,
                )
                return

            # Update predictions
            entry.predictions_json = json.dumps(prediction_list)
            await self.db.commit()

            await ctx.followup.send(
                embed=success_embed(
                    "Predictions Set",
                    f"Picks: {', '.join(prediction_list)}"
                ),
                ephemeral=True,
            )

        except Exception as e:
            logger.exception("Error submitting predictions")
            await ctx.followup.send(
                embed=error_embed(
                    "Submission Failed",
                    "Could not save predictions",
                    recovery_hint="Try again",
                    error_code="TOURNAMENT_PREDICT_ERROR"
                ),
                ephemeral=True,
            )

    @tournament_group.command(
        name="leaderboard",
        description="View tournament leaderboard with pagination",
    )
    async def tournament_leaderboard(
        self,
        ctx: discord.ApplicationContext,
        tournament_id: int,
    ) -> None:
        """
        Show tournament leaderboard with pagination (10 per page).

        Args:
            ctx: Discord application context
            tournament_id: ID of tournament
        """
        await ctx.defer()

        try:
            # Fetch tournament entries sorted by score
            stmt = (
                select(TournamentEntry)
                .where(TournamentEntry.tournament_id == tournament_id)
                .order_by(desc(TournamentEntry.score))
            )
            result = await self.db.execute(stmt)
            entries = result.scalars().all()

            if not entries:
                embed = empty_state_embed(
                    "Tournament Leaderboard",
                    "No entries yet",
                    [f"/tournament enter {tournament_id}"]
                )
                await ctx.followup.send(embed=embed)
                return

            # Create paginated embeds (10 per page)
            page_size = 10
            embeds = []
            user_rank = None

            for page_num in range((len(entries) + page_size - 1) // page_size):
                start_idx = page_num * page_size
                end_idx = start_idx + page_size
                page_entries = entries[start_idx:end_idx]

                # Check if current user is on this page
                for idx, entry in enumerate(page_entries, start_idx + 1):
                    if entry.discord_user_id == ctx.author.id:
                        user_rank = idx

                # Build entries list for leaderboard_embed
                entry_dicts = []
                for idx, entry in enumerate(page_entries, start_idx + 1):
                    user = self.bot.get_user(entry.discord_user_id)
                    username = user.name if user else f"User {entry.discord_user_id}"
                    entry_dicts.append({
                        "rank": idx,
                        "username": username,
                        "value": entry.score or 0,
                    })

                embed = leaderboard_embed(
                    f"Tournament {tournament_id} Leaderboard",
                    entry_dicts,
                    page_num + 1,
                    (len(entries) + page_size - 1) // page_size,
                    user_rank,
                )
                embeds.append(embed)

            if len(embeds) == 1:
                await ctx.followup.send(embed=embeds[0])
            else:
                view = PaginatedView(
                    embeds,
                    on_jump_to_rank=lambda interaction: self._jump_to_rank(
                        interaction, entries, ctx.author.id, page_size
                    ) if user_rank else None,
                )
                await ctx.followup.send(embed=embeds[0], view=view)

        except Exception as e:
            logger.exception("Error fetching leaderboard")
            await ctx.followup.send(
                embed=error_embed(
                    "Leaderboard Failed",
                    "Could not retrieve leaderboard",
                    recovery_hint="Try again",
                    error_code="TOURNAMENT_LEADERBOARD_ERROR"
                ),
                ephemeral=True,
            )

    async def _jump_to_rank(
        self,
        interaction: discord.Interaction,
        entries: List[TournamentEntry],
        user_id: int,
        page_size: int,
    ) -> None:
        """Jump to user's rank on leaderboard."""
        for idx, entry in enumerate(entries, 1):
            if entry.discord_user_id == user_id:
                page = (idx - 1) // page_size
                await interaction.response.defer()
                return
        await interaction.response.defer()

    @tournament_group.command(
        name="create",
        description="Create a new tournament (admin only)",
    )
    @commands.has_permissions(administrator=True)
    async def create_tournament(
        self,
        ctx: discord.ApplicationContext,
        title: str,
        starts: str,
        ends: str,
        entry_fee_xp: int = 0,
    ) -> None:
        """
        Create a new tournament.

        Args:
            ctx: Discord application context
            title: Tournament title
            starts: Start datetime (ISO format: YYYY-MM-DD HH:MM)
            ends: End datetime (ISO format: YYYY-MM-DD HH:MM)
            entry_fee_xp: XP cost to enter (default 0)
        """
        await ctx.defer()

        try:
            # Validate title length
            is_valid, error_msg = validate_length(title, 1, 100, "Tournament title")
            if not is_valid:
                await ctx.followup.send(
                    embed=error_embed("Invalid Title", error_msg),
                    ephemeral=True,
                )
                return

            # Validate entry fee
            is_valid, error_msg = validate_range(entry_fee_xp, 0, 10000, "Entry fee")
            if not is_valid:
                await ctx.followup.send(
                    embed=error_embed("Invalid Entry Fee", error_msg),
                    ephemeral=True,
                )
                return

            # Parse dates
            starts_dt, error_msg = validate_datetime(starts, "Start time")
            if error_msg:
                await ctx.followup.send(
                    embed=error_embed("Invalid Start Time", error_msg),
                    ephemeral=True,
                )
                return

            ends_dt, error_msg = validate_datetime(ends, "End time")
            if error_msg:
                await ctx.followup.send(
                    embed=error_embed("Invalid End Time", error_msg),
                    ephemeral=True,
                )
                return

            # Validate end > start
            if ends_dt <= starts_dt:
                await ctx.followup.send(
                    embed=error_embed(
                        "Invalid Date Range",
                        "End time must be after start time"
                    ),
                    ephemeral=True,
                )
                return

            tournament = Tournament(
                guild_id=ctx.guild_id,
                title=title,
                tournament_type="weekly_prediction",
                status="upcoming",
                entry_fee_xp=entry_fee_xp,
                prize_config_json=json.dumps({}),
                scoring_config_json=json.dumps({}),
                starts_at=starts_dt,
                ends_at=ends_dt,
            )

            self.db.add(tournament)
            await self.db.flush()
            await self.db.commit()

            embed = success_embed(
                "Tournament Created",
                f"**{title}**",
                fields=[
                    ("Tournament ID", f"`{tournament.id}`", True),
                    ("Entry Fee", f"{entry_fee_xp} XP", True),
                    ("Starts", starts_dt.strftime("%Y-%m-%d %H:%M"), True),
                    ("Ends", ends_dt.strftime("%Y-%m-%d %H:%M"), True),
                ]
            )

            await ctx.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.exception("Error creating tournament")
            await ctx.followup.send(
                embed=error_embed(
                    "Creation Failed",
                    "Could not create tournament",
                    recovery_hint="Try again",
                    error_code="TOURNAMENT_CREATE_ERROR"
                ),
                ephemeral=True,
            )

    @tournament_group.command(
        name="score",
        description="Trigger tournament scoring (admin only)",
    )
    @commands.has_permissions(administrator=True)
    async def score_tournament(
        self,
        ctx: discord.ApplicationContext,
        tournament_id: int,
    ) -> None:
        """
        Trigger manual scoring for a tournament.

        Args:
            ctx: Discord application context
            tournament_id: ID of tournament to score
        """
        await ctx.defer()

        try:
            stmt = select(Tournament).where(Tournament.id == tournament_id)
            result = await self.db.execute(stmt)
            tournament = result.scalars().first()

            if not tournament:
                await ctx.followup.send(
                    embed=error_embed(
                        "Not Found",
                        f"No tournament with ID: {tournament_id}",
                        recovery_hint="Check the ID and try again"
                    ),
                    ephemeral=True,
                )
                return

            # Ask for confirmation
            view = ConfirmView()
            confirm_embed = info_embed(
                "Score Tournament?",
                f"Score \"{tournament.title[:40]}\"? This cannot be undone.",
            )
            await ctx.followup.send(embed=confirm_embed, view=view, ephemeral=True)

            await view.wait()
            if view.result:
                tournament.status = "scoring"
                await self.db.commit()

                # Send loading state
                loading = loading_embed(f"Scoring tournament {tournament_id}... Processing entries")
                await ctx.followup.send(embed=loading, ephemeral=True)

                await ctx.followup.send(
                    embed=success_embed("Scoring Started", f"Tournament {tournament_id}"),
                    ephemeral=True,
                )

        except Exception as e:
            logger.exception("Error triggering tournament scoring")
            await ctx.followup.send(
                embed=error_embed(
                    "Scoring Failed",
                    "Could not start scoring",
                    recovery_hint="Try again",
                    error_code="TOURNAMENT_SCORE_ERROR"
                ),
                ephemeral=True,
            )

    @tasks.loop(minutes=5)
    async def auto_start_tournaments(self) -> None:
        """
        Every 5 minutes, check for tournaments to start.

        Moves tournaments from 'upcoming' to 'active' when start time is reached.
        """
        try:
            stmt = select(Tournament).where(
                and_(
                    Tournament.status == "upcoming",
                    Tournament.starts_at <= datetime.utcnow(),
                )
            )
            result = await self.db.execute(stmt)
            tournaments = result.scalars().all()

            for tournament in tournaments:
                tournament.status = "active"

            if tournaments:
                await self.db.commit()
                logger.info(f"Auto-started {len(tournaments)} tournaments")

        except Exception as e:
            logger.exception("Error in auto_start_tournaments background task")

    @auto_start_tournaments.before_loop
    async def before_auto_start(self) -> None:
        """Wait for bot to be ready."""
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=5)
    async def auto_close_tournaments(self) -> None:
        """
        Every 5 minutes, check for tournaments to close.

        Moves tournaments from 'active' to 'completed' when end time is reached.
        """
        try:
            stmt = select(Tournament).where(
                and_(
                    Tournament.status == "active",
                    Tournament.ends_at <= datetime.utcnow(),
                )
            )
            result = await self.db.execute(stmt)
            tournaments = result.scalars().all()

            for tournament in tournaments:
                tournament.status = "completed"
                tournament.completed_at = datetime.utcnow()

            if tournaments:
                await self.db.commit()
                logger.info(f"Auto-closed {len(tournaments)} tournaments")

        except Exception as e:
            logger.exception("Error in auto_close_tournaments background task")

    @auto_close_tournaments.before_loop
    async def before_auto_close(self) -> None:
        """Wait for bot to be ready."""
        await self.bot.wait_until_ready()

    @tasks.loop(days=1)
    async def weekly_tournament_creator(self) -> None:
        """
        Every Monday at 9am ET, create a new weekly prediction tournament.

        Automatically creates tournaments with standardized settings.
        """
        try:
            now = datetime.utcnow()
            # Check if it's Monday (weekday 0) and around 1pm UTC (9am ET)
            if now.weekday() == 0 and 13 <= now.hour < 14:
                guild = self.bot.get_guild(
                    int(self.bot.config.get("MAIN_GUILD_ID", 0))
                    if hasattr(self.bot, "config")
                    else 0
                )
                if guild:
                    tournament = Tournament(
                        guild_id=guild.id,
                        title="Weekly Prediction Tournament",
                        tournament_type="weekly_prediction",
                        status="upcoming",
                        entry_fee_xp=50,
                        prize_config_json=json.dumps({}),
                        scoring_config_json=json.dumps({}),
                        starts_at=now + timedelta(hours=1),
                        ends_at=now + timedelta(days=7),
                    )
                    self.db.add(tournament)
                    await self.db.commit()
                    logger.info(f"Created weekly tournament {tournament.id}")

        except Exception as e:
            logger.exception("Error in weekly_tournament_creator background task")

    @weekly_tournament_creator.before_loop
    async def before_weekly_creator(self) -> None:
        """Wait for bot to be ready."""
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    """Load the Tournaments cog."""
    await bot.add_cog(TournamentsCog(bot))
