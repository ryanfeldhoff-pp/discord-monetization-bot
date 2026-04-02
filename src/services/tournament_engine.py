"""
Tournament Engine Service

Core service for managing prediction tournaments: creation, entry validation,
prediction submission, scoring, leaderboard generation, and prize distribution.
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from src.models.event_models import Tournament, TournamentEntry
from src.services.xp_manager import XPManager

logger = logging.getLogger(__name__)


class TournamentEngine:
    """
    Service for managing prediction tournaments.

    Features:
    - Create and configure tournaments with custom prizes and scoring
    - Validate and manage tournament entries
    - Track predictions and updates
    - Score tournaments with configurable rules
    - Award prizes and XP to winners
    - Generate leaderboards with Redis caching
    - Auto-start/close tournaments based on schedules
    """

    # Default prize configuration
    DEFAULT_PRIZE_CONFIG = {
        "1st": "promo_code_50",
        "2nd": "promo_code_25",
        "3rd": "promo_code_10",
        "xp_awards": {
            "1st": 500,
            "2nd": 300,
            "3rd": 200,
            "participation": 50,
        },
    }

    # Default scoring configuration
    DEFAULT_SCORING_CONFIG = {
        "correct_pick": 10,
        "correct_spread": 5,
        "bonus_sweep": 50,
    }

    def __init__(
        self,
        db_session: AsyncSession,
        xp_manager: XPManager,
        redis_client: Optional[redis.Redis] = None,
        config: Optional[Dict] = None,
    ):
        """
        Initialize Tournament Engine.

        Args:
            db_session: AsyncSession for database operations
            xp_manager: XPManager instance for XP operations
            redis_client: Optional Redis client for caching
            config: Optional config dict with overrides
        """
        self.db = db_session
        self.xp_manager = xp_manager
        self.redis = redis_client
        self.config = config or {}

    async def create_tournament(
        self,
        guild_id: int,
        title: str,
        description: Optional[str],
        tournament_type: str,
        starts_at: datetime,
        ends_at: datetime,
        entry_fee_xp: int = 0,
        max_participants: Optional[int] = None,
        prize_config: Optional[Dict] = None,
        scoring_config: Optional[Dict] = None,
    ) -> Tournament:
        """
        Create a new tournament record in the database.

        Args:
            guild_id: Discord guild ID
            title: Tournament title
            description: Tournament description
            tournament_type: Type of tournament (e.g., "weekly_prediction")
            starts_at: Tournament start datetime
            ends_at: Tournament end datetime
            entry_fee_xp: XP cost to enter (0 for free)
            max_participants: Max participants (None for unlimited)
            prize_config: Prize configuration dict (uses defaults if not provided)
            scoring_config: Scoring configuration dict (uses defaults if not provided)

        Returns:
            Created Tournament object

        Raises:
            ValueError: If dates are invalid
        """
        try:
            if starts_at >= ends_at:
                raise ValueError("Tournament start_at must be before end_at")

            # Use default configs if not provided
            prize_config = prize_config or self.DEFAULT_PRIZE_CONFIG
            scoring_config = scoring_config or self.DEFAULT_SCORING_CONFIG

            tournament = Tournament(
                guild_id=guild_id,
                title=title,
                description=description,
                tournament_type=tournament_type,
                status="upcoming",
                entry_fee_xp=entry_fee_xp,
                max_participants=max_participants,
                prize_config_json=json.dumps(prize_config),
                scoring_config_json=json.dumps(scoring_config),
                starts_at=starts_at,
                ends_at=ends_at,
            )
            self.db.add(tournament)
            await self.db.flush()

            logger.info(
                f"Created tournament {tournament.id} '{title}' in guild {guild_id}"
            )
            return tournament

        except Exception as e:
            logger.error(f"Error creating tournament: {e}")
            await self.db.rollback()
            raise

    async def enter_tournament(
        self,
        tournament_id: int,
        discord_user_id: int,
        predictions: Dict[str, Any],
    ) -> TournamentEntry:
        """
        Register a user for a tournament entry.

        Args:
            tournament_id: Tournament ID
            discord_user_id: Discord user ID
            predictions: Initial predictions dict

        Returns:
            Created TournamentEntry object

        Raises:
            ValueError: If tournament is not active, full, or user lacks XP
        """
        try:
            # Fetch tournament
            stmt = select(Tournament).where(Tournament.id == tournament_id)
            result = await self.db.execute(stmt)
            tournament = result.scalar_one_or_none()

            if not tournament:
                raise ValueError(f"Tournament {tournament_id} not found")

            # Check if tournament is active or upcoming
            if tournament.status not in ("upcoming", "active"):
                raise ValueError(
                    f"Tournament status is '{tournament.status}', "
                    "not accepting new entries"
                )

            # Check max participants
            if tournament.max_participants:
                stmt = select(func.count()).select_from(TournamentEntry).where(
                    TournamentEntry.tournament_id == tournament_id
                )
                result = await self.db.execute(stmt)
                entry_count = result.scalar() or 0
                if entry_count >= tournament.max_participants:
                    raise ValueError("Tournament is full")

            # Check for duplicate entry
            stmt = select(TournamentEntry).where(
                and_(
                    TournamentEntry.tournament_id == tournament_id,
                    TournamentEntry.discord_user_id == discord_user_id,
                )
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing:
                raise ValueError(
                    f"User {discord_user_id} already entered tournament {tournament_id}"
                )

            # Deduct entry fee if applicable
            if tournament.entry_fee_xp > 0:
                success, msg = await self.xp_manager.deduct_xp(
                    discord_user_id,
                    tournament.entry_fee_xp,
                    f"tournament_entry_{tournament_id}",
                )
                if not success:
                    raise ValueError(f"Cannot deduct entry fee: {msg}")

            # Create entry
            entry = TournamentEntry(
                tournament_id=tournament_id,
                discord_user_id=discord_user_id,
                predictions_json=json.dumps(predictions),
                score=0,
            )
            self.db.add(entry)
            await self.db.flush()

            logger.info(
                f"User {discord_user_id} entered tournament {tournament_id}"
            )
            return entry

        except Exception as e:
            logger.error(f"Error entering tournament: {e}")
            await self.db.rollback()
            raise

    async def submit_predictions(
        self,
        tournament_id: int,
        discord_user_id: int,
        predictions: Dict[str, Any],
    ) -> bool:
        """
        Update predictions for a tournament entry.

        Args:
            tournament_id: Tournament ID
            discord_user_id: Discord user ID
            predictions: Updated predictions dict

        Returns:
            True if successful

        Raises:
            ValueError: If tournament not active or entry not found
        """
        try:
            # Fetch tournament
            stmt = select(Tournament).where(Tournament.id == tournament_id)
            result = await self.db.execute(stmt)
            tournament = result.scalar_one_or_none()

            if not tournament:
                raise ValueError(f"Tournament {tournament_id} not found")

            if tournament.status != "active":
                raise ValueError(
                    f"Tournament is not active (status: {tournament.status})"
                )

            # Fetch entry
            stmt = select(TournamentEntry).where(
                and_(
                    TournamentEntry.tournament_id == tournament_id,
                    TournamentEntry.discord_user_id == discord_user_id,
                )
            )
            result = await self.db.execute(stmt)
            entry = result.scalar_one_or_none()

            if not entry:
                raise ValueError(
                    f"No entry found for user {discord_user_id} in "
                    f"tournament {tournament_id}"
                )

            # Update predictions
            entry.predictions_json = json.dumps(predictions)
            await self.db.flush()

            logger.info(
                f"Updated predictions for user {discord_user_id} "
                f"in tournament {tournament_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error submitting predictions: {e}")
            await self.db.rollback()
            raise

    async def score_tournament(
        self,
        tournament_id: int,
        results: Dict[str, Any],
    ) -> List[TournamentEntry]:
        """
        Score all entries in a tournament and award prizes.

        Args:
            tournament_id: Tournament ID
            results: Actual results dict with answers

        Returns:
            Sorted list of TournamentEntry objects (ranked)

        Raises:
            ValueError: If tournament not found
        """
        try:
            # Fetch tournament
            stmt = select(Tournament).where(Tournament.id == tournament_id)
            result = await self.db.execute(stmt)
            tournament = result.scalar_one_or_none()

            if not tournament:
                raise ValueError(f"Tournament {tournament_id} not found")

            # Parse configs
            prize_config = json.loads(tournament.prize_config_json)
            scoring_config = json.loads(tournament.scoring_config_json)

            # Fetch all entries
            stmt = select(TournamentEntry).where(
                TournamentEntry.tournament_id == tournament_id
            )
            result = await self.db.execute(stmt)
            entries = result.scalars().all()

            # Score each entry
            for entry in entries:
                predictions = json.loads(entry.predictions_json)
                score = self._calculate_score(
                    predictions, results, scoring_config
                )
                entry.score = score
                entry.scored_at = datetime.utcnow()

            # Sort by score (descending), then by entry time (ascending)
            ranked_entries = sorted(
                entries,
                key=lambda e: (-e.score, e.entered_at),
            )

            # Assign ranks
            for rank, entry in enumerate(ranked_entries, start=1):
                entry.rank = rank

            # Award prizes and XP to top finishers
            await self._award_prizes(
                tournament_id, ranked_entries, prize_config
            )

            # Award participation XP
            participation_xp = prize_config.get("xp_awards", {}).get(
                "participation", 50
            )
            if participation_xp > 0:
                for entry in entries:
                    await self.xp_manager.award_xp(
                        entry.discord_user_id,
                        participation_xp,
                        "tournament_participation",
                        {"tournament_id": tournament_id},
                        ignore_daily_cap=True,
                    )

            # Update tournament status
            tournament.status = "completed"
            tournament.completed_at = datetime.utcnow()

            await self.db.commit()

            logger.info(
                f"Scored tournament {tournament_id} with {len(entries)} entries"
            )
            return ranked_entries

        except Exception as e:
            logger.error(f"Error scoring tournament: {e}")
            await self.db.rollback()
            raise

    async def get_leaderboard(
        self,
        tournament_id: int,
        limit: int = 25,
    ) -> List[Dict]:
        """
        Get tournament leaderboard with optional Redis caching.

        Args:
            tournament_id: Tournament ID
            limit: Max results to return

        Returns:
            List of dicts with user_id, rank, score, predictions
        """
        try:
            # Try Redis cache first
            if self.redis:
                cached = await self._get_cached_leaderboard(tournament_id)
                if cached:
                    return cached[:limit]

            # Query from database
            stmt = (
                select(TournamentEntry)
                .where(TournamentEntry.tournament_id == tournament_id)
                .order_by(TournamentEntry.rank.asc())
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            entries = result.scalars().all()

            leaderboard = [
                {
                    "user_id": entry.discord_user_id,
                    "rank": entry.rank,
                    "score": entry.score,
                    "predictions": json.loads(entry.predictions_json),
                    "prize": entry.prize_awarded,
                }
                for entry in entries
            ]

            # Cache in Redis
            if self.redis:
                await self._cache_leaderboard(tournament_id, leaderboard)

            return leaderboard

        except Exception as e:
            logger.error(f"Error getting leaderboard for tournament {tournament_id}: {e}")
            return []

    async def get_active_tournaments(
        self,
        guild_id: int,
    ) -> List[Tournament]:
        """
        Get all active tournaments for a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            List of active Tournament objects
        """
        try:
            stmt = select(Tournament).where(
                and_(
                    Tournament.guild_id == guild_id,
                    Tournament.status == "active",
                )
            )
            result = await self.db.execute(stmt)
            tournaments = result.scalars().all()

            return tournaments

        except Exception as e:
            logger.error(f"Error getting active tournaments for guild {guild_id}: {e}")
            return []

    async def get_tournament_stats(
        self,
        tournament_id: int,
    ) -> Dict:
        """
        Get statistics for a tournament.

        Args:
            tournament_id: Tournament ID

        Returns:
            Dict with stats: participant_count, avg_score, top_scorer, etc.
        """
        try:
            # Count participants
            stmt = select(func.count()).select_from(TournamentEntry).where(
                TournamentEntry.tournament_id == tournament_id
            )
            result = await self.db.execute(stmt)
            participant_count = result.scalar() or 0

            # Get scores if tournament is scored
            stmt = select(TournamentEntry).where(
                TournamentEntry.tournament_id == tournament_id
            )
            result = await self.db.execute(stmt)
            entries = result.scalars().all()

            if entries and entries[0].score is not None:
                scores = [e.score for e in entries if e.score is not None]
                avg_score = sum(scores) / len(scores) if scores else 0
                top_entry = max(entries, key=lambda e: e.score)
                top_scorer = top_entry.discord_user_id
            else:
                avg_score = 0
                top_scorer = None

            return {
                "participant_count": participant_count,
                "avg_score": round(avg_score, 2) if avg_score else 0,
                "top_scorer": top_scorer,
                "tournament_id": tournament_id,
            }

        except Exception as e:
            logger.error(f"Error getting stats for tournament {tournament_id}: {e}")
            return {
                "participant_count": 0,
                "avg_score": 0,
                "top_scorer": None,
                "tournament_id": tournament_id,
            }

    async def auto_start_tournaments(self) -> List[Tournament]:
        """
        Check for upcoming tournaments past start time and activate them.

        Returns:
            List of tournaments that were started
        """
        try:
            now = datetime.utcnow()
            stmt = select(Tournament).where(
                and_(
                    Tournament.status == "upcoming",
                    Tournament.starts_at <= now,
                )
            )
            result = await self.db.execute(stmt)
            tournaments = result.scalars().all()

            for tournament in tournaments:
                tournament.status = "active"
                logger.info(f"Auto-started tournament {tournament.id}")

            if tournaments:
                await self.db.commit()

            return tournaments

        except Exception as e:
            logger.error(f"Error in auto_start_tournaments: {e}")
            await self.db.rollback()
            return []

    async def auto_close_tournaments(self) -> List[Tournament]:
        """
        Check for active tournaments past end time and close them for scoring.

        Returns:
            List of tournaments that were closed
        """
        try:
            now = datetime.utcnow()
            stmt = select(Tournament).where(
                and_(
                    Tournament.status == "active",
                    Tournament.ends_at <= now,
                )
            )
            result = await self.db.execute(stmt)
            tournaments = result.scalars().all()

            for tournament in tournaments:
                tournament.status = "scoring"
                logger.info(f"Auto-closed tournament {tournament.id} for scoring")

            if tournaments:
                await self.db.commit()

            return tournaments

        except Exception as e:
            logger.error(f"Error in auto_close_tournaments: {e}")
            await self.db.rollback()
            return []

    def _calculate_score(
        self,
        predictions: Dict[str, Any],
        results: Dict[str, Any],
        scoring_config: Dict[str, int],
    ) -> int:
        """
        Calculate score for predictions against actual results.

        Args:
            predictions: User's prediction dict
            results: Actual results dict
            scoring_config: Scoring rules dict

        Returns:
            Total score for the predictions
        """
        score = 0

        try:
            # Score each prediction item
            for prediction_key, prediction_value in predictions.items():
                result_value = results.get(prediction_key)

                if result_value is None:
                    continue

                # Correct pick (full points)
                if prediction_value == result_value:
                    score += scoring_config.get("correct_pick", 10)

                # Correct spread/direction (partial points)
                elif isinstance(prediction_value, dict) and isinstance(
                    result_value, dict
                ):
                    if (
                        prediction_value.get("direction")
                        == result_value.get("direction")
                    ):
                        score += scoring_config.get("correct_spread", 5)

            # Bonus for sweeping (all picks correct)
            all_correct = all(
                predictions.get(k) == results.get(k)
                for k in predictions.keys()
                if k in results
            )
            if all_correct and len(predictions) > 0:
                score += scoring_config.get("bonus_sweep", 50)

            return score

        except Exception as e:
            logger.error(f"Error calculating score: {e}")
            return 0

    async def _award_prizes(
        self,
        tournament_id: int,
        ranked_entries: List[TournamentEntry],
        prize_config: Dict[str, Any],
    ) -> None:
        """
        Award prizes and XP to top finishers.

        Args:
            tournament_id: Tournament ID
            ranked_entries: Sorted list of TournamentEntry objects
            prize_config: Prize configuration dict
        """
        try:
            xp_awards = prize_config.get("xp_awards", {})

            # Award XP to top 3
            rank_keys = ["1st", "2nd", "3rd"]
            for rank_idx, rank_key in enumerate(rank_keys):
                if rank_idx < len(ranked_entries):
                    entry = ranked_entries[rank_idx]
                    xp_amount = xp_awards.get(rank_key, 0)

                    if xp_amount > 0:
                        await self.xp_manager.award_xp(
                            entry.discord_user_id,
                            xp_amount,
                            f"tournament_{rank_key}",
                            {"tournament_id": tournament_id},
                            ignore_daily_cap=True,
                        )

                    # Set prize code
                    prize_key = prize_config.get(rank_key, "")
                    if prize_key:
                        entry.prize_awarded = prize_key

            logger.info(f"Awarded prizes for tournament {tournament_id}")

        except Exception as e:
            logger.error(f"Error awarding prizes for tournament {tournament_id}: {e}")

    async def _cache_leaderboard(
        self,
        tournament_id: int,
        leaderboard: List[Dict],
    ) -> None:
        """
        Cache leaderboard in Redis.

        Args:
            tournament_id: Tournament ID
            leaderboard: Leaderboard list
        """
        try:
            if not self.redis:
                return

            cache_key = f"tournament_leaderboard:{tournament_id}"
            await self.redis.setex(
                cache_key,
                300,  # 5 minute TTL
                json.dumps(leaderboard),
            )

        except Exception as e:
            logger.error(f"Error caching leaderboard: {e}")

    async def _get_cached_leaderboard(
        self,
        tournament_id: int,
    ) -> Optional[List[Dict]]:
        """
        Get leaderboard from Redis cache.

        Args:
            tournament_id: Tournament ID

        Returns:
            Cached leaderboard or None if not found
        """
        try:
            if not self.redis:
                return None

            cache_key = f"tournament_leaderboard:{tournament_id}"
            cached = await self.redis.get(cache_key)

            if cached:
                return json.loads(cached)

            return None

        except Exception as e:
            logger.error(f"Error retrieving cached leaderboard: {e}")
            return None
