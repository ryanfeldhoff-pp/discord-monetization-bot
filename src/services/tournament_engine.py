"""
Tournament Engine Service (Pillar 3)

Manages tournament lifecycle: creation, entry, prediction submission,
scoring, and prize distribution.
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, List, Tuple

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
    - Create and configure tournaments
    - Handle entries with XP fee collection
    - Accept and validate predictions
    - Score predictions against results
    - Distribute prizes and XP rewards
    - Redis-cached leaderboards
    """

    # Scoring: 1 point per correct pick, 0.5 for partial (over/under within 5%)
    SCORING = {
        "correct": 1.0,
        "partial": 0.5,
        "incorrect": 0.0,
    }

    # Prize XP awards (on top of promo prizes)
    PRIZE_XP = {
        1: 500,
        2: 300,
        3: 150,
    }

    def __init__(
        self,
        db_session: AsyncSession,
        xp_manager: XPManager,
        redis_client: Optional[redis.Redis] = None,
        config: Optional[Dict] = None,
    ):
        self.db = db_session
        self.xp_manager = xp_manager
        self.redis = redis_client
        self.config = config or {}

    async def create_tournament(
        self,
        title: str,
        description: str,
        sport: Optional[str],
        entry_fee_xp: int,
        picks_required: int,
        prize_pool: Dict[str, str],
        opens_at: datetime,
        locks_at: datetime,
        created_by: int,
        tournament_type: str = "weekly",
        max_participants: int = 0,
    ) -> Tournament:
        """Create a new tournament."""
        tournament = Tournament(
            title=title,
            description=description,
            tournament_type=tournament_type,
            sport=sport,
            entry_fee_xp=entry_fee_xp,
            max_participants=max_participants,
            picks_required=picks_required,
            prize_pool_json=json.dumps(prize_pool),
            status="upcoming",
            created_by=created_by,
            opens_at=opens_at,
            locks_at=locks_at,
        )
        self.db.add(tournament)
        await self.db.flush()
        logger.info(f"Created tournament '{title}' (id={tournament.id})")
        return tournament

    async def enter_tournament(
        self, tournament_id: int, user_id: int
    ) -> Tuple[bool, str]:
        """Register a user for a tournament, collecting XP fee if applicable."""
        try:
            # Get tournament
            stmt = select(Tournament).where(Tournament.id == tournament_id)
            result = await self.db.execute(stmt)
            tournament = result.scalar_one_or_none()

            if not tournament:
                return False, "Tournament not found"
            if tournament.status != "open":
                return False, f"Tournament is {tournament.status}, not accepting entries"

            # Check if already entered
            stmt = select(TournamentEntry).where(
                and_(
                    TournamentEntry.tournament_id == tournament_id,
                    TournamentEntry.discord_user_id == user_id,
                )
            )
            result = await self.db.execute(stmt)
            if result.scalar_one_or_none():
                return False, "You're already entered in this tournament"

            # Check max participants
            if tournament.max_participants > 0:
                stmt = select(func.count()).select_from(TournamentEntry).where(
                    TournamentEntry.tournament_id == tournament_id
                )
                result = await self.db.execute(stmt)
                count = result.scalar()
                if count >= tournament.max_participants:
                    return False, "Tournament is full"

            # Collect XP entry fee
            if tournament.entry_fee_xp > 0:
                success, msg = await self.xp_manager.deduct_xp(
                    user_id, tournament.entry_fee_xp, f"tournament_entry_{tournament_id}"
                )
                if not success:
                    return False, f"Cannot pay entry fee: {msg}"

            # Create entry
            entry = TournamentEntry(
                tournament_id=tournament_id,
                discord_user_id=user_id,
                xp_paid=tournament.entry_fee_xp,
            )
            self.db.add(entry)
            await self.db.flush()

            # Award participation XP
            await self.xp_manager.award_xp(
                user_id, self.xp_manager.XP_VALUES["tournament_participation"],
                "tournament_participation",
                metadata={"tournament_id": tournament_id},
                ignore_daily_cap=True,
            )

            logger.info(f"User {user_id} entered tournament {tournament_id}")
            return True, "Successfully entered tournament!"

        except Exception as e:
            logger.error(f"Error entering tournament: {e}")
            return False, "Error entering tournament"

    async def submit_predictions(
        self, tournament_id: int, user_id: int, predictions: List[Dict]
    ) -> Tuple[bool, str]:
        """Submit or update predictions for a tournament entry."""
        try:
            stmt = select(TournamentEntry).where(
                and_(
                    TournamentEntry.tournament_id == tournament_id,
                    TournamentEntry.discord_user_id == user_id,
                )
            )
            result = await self.db.execute(stmt)
            entry = result.scalar_one_or_none()

            if not entry:
                return False, "You're not entered in this tournament"

            # Validate tournament is still accepting predictions
            stmt = select(Tournament).where(Tournament.id == tournament_id)
            result = await self.db.execute(stmt)
            tournament = result.scalar_one_or_none()

            if tournament.status not in ("open",):
                return False, "Tournament is no longer accepting predictions"

            if len(predictions) != tournament.picks_required:
                return False, f"Exactly {tournament.picks_required} picks required"

            entry.predictions_json = json.dumps(predictions)
            await self.db.flush()

            logger.info(f"User {user_id} submitted predictions for tournament {tournament_id}")
            return True, f"Submitted {len(predictions)} predictions!"

        except Exception as e:
            logger.error(f"Error submitting predictions: {e}")
            return False, "Error submitting predictions"

    async def score_tournament(
        self, tournament_id: int, results: List[Dict]
    ) -> Tuple[bool, str]:
        """Score all entries in a tournament against actual results."""
        try:
            stmt = select(Tournament).where(Tournament.id == tournament_id)
            result = await self.db.execute(stmt)
            tournament = result.scalar_one_or_none()

            if not tournament:
                return False, "Tournament not found"

            tournament.status = "scoring"
            await self.db.flush()

            # Get all entries with predictions
            stmt = select(TournamentEntry).where(
                and_(
                    TournamentEntry.tournament_id == tournament_id,
                    TournamentEntry.predictions_json.isnot(None),
                )
            )
            result = await self.db.execute(stmt)
            entries = result.scalars().all()

            results_map = {r["projection_id"]: r for r in results}

            for entry in entries:
                predictions = json.loads(entry.predictions_json)
                total_score = 0.0

                for pick in predictions:
                    proj_id = pick.get("projection_id")
                    direction = pick.get("direction")  # "more" or "less"

                    if proj_id in results_map:
                        actual = results_map[proj_id]
                        if actual.get("result") == direction:
                            total_score += self.SCORING["correct"]
                        elif actual.get("result") == "push":
                            total_score += self.SCORING["partial"]

                entry.score = total_score
                entry.scored_at = datetime.utcnow()

            # Rank entries by score DESC
            scored = sorted(entries, key=lambda e: e.score, reverse=True)
            for i, entry in enumerate(scored):
                entry.rank = i + 1

            # Award prizes for top 3
            for entry in scored[:3]:
                if entry.rank in self.PRIZE_XP:
                    await self.xp_manager.award_xp(
                        entry.discord_user_id,
                        self.PRIZE_XP[entry.rank],
                        "tournament_win",
                        metadata={"tournament_id": tournament_id, "rank": entry.rank},
                        ignore_daily_cap=True,
                    )

            tournament.status = "completed"
            tournament.completed_at = datetime.utcnow()
            await self.db.commit()

            # Invalidate cache
            if self.redis:
                await self.redis.delete(f"tournament_lb:{tournament_id}")

            logger.info(f"Scored tournament {tournament_id}: {len(entries)} entries ranked")
            return True, f"Tournament scored! {len(entries)} entries ranked."

        except Exception as e:
            logger.error(f"Error scoring tournament: {e}")
            await self.db.rollback()
            return False, "Error scoring tournament"

    async def get_tournament(self, tournament_id: int) -> Optional[Dict]:
        """Get tournament details."""
        try:
            stmt = select(Tournament).where(Tournament.id == tournament_id)
            result = await self.db.execute(stmt)
            t = result.scalar_one_or_none()
            if not t:
                return None

            # Get participant count
            stmt = select(func.count()).select_from(TournamentEntry).where(
                TournamentEntry.tournament_id == tournament_id
            )
            result = await self.db.execute(stmt)
            participant_count = result.scalar()

            return {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "type": t.tournament_type,
                "sport": t.sport,
                "entry_fee_xp": t.entry_fee_xp,
                "picks_required": t.picks_required,
                "prize_pool": json.loads(t.prize_pool_json),
                "status": t.status,
                "participants": participant_count,
                "max_participants": t.max_participants,
                "opens_at": t.opens_at.isoformat() if t.opens_at else None,
                "locks_at": t.locks_at.isoformat() if t.locks_at else None,
            }
        except Exception as e:
            logger.error(f"Error getting tournament {tournament_id}: {e}")
            return None

    async def get_leaderboard(self, tournament_id: int, limit: int = 10) -> List[Dict]:
        """Get tournament leaderboard."""
        try:
            if self.redis:
                cached = await self.redis.get(f"tournament_lb:{tournament_id}")
                if cached:
                    return json.loads(cached)

            stmt = (
                select(TournamentEntry)
                .where(TournamentEntry.tournament_id == tournament_id)
                .order_by(TournamentEntry.score.desc())
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            entries = result.scalars().all()

            lb = [
                {
                    "rank": entry.rank or i + 1,
                    "user_id": entry.discord_user_id,
                    "score": entry.score,
                    "predictions_count": len(json.loads(entry.predictions_json)) if entry.predictions_json else 0,
                }
                for i, entry in enumerate(entries)
            ]

            if self.redis:
                await self.redis.setex(f"tournament_lb:{tournament_id}", 300, json.dumps(lb))

            return lb
        except Exception as e:
            logger.error(f"Error getting tournament leaderboard: {e}")
            return []

    async def list_tournaments(self, status: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """List tournaments, optionally filtered by status."""
        try:
            stmt = select(Tournament).order_by(Tournament.opens_at.desc()).limit(limit)
            if status:
                stmt = stmt.where(Tournament.status == status)

            result = await self.db.execute(stmt)
            tournaments = result.scalars().all()

            return [
                {
                    "id": t.id,
                    "title": t.title,
                    "status": t.status,
                    "sport": t.sport,
                    "entry_fee_xp": t.entry_fee_xp,
                    "opens_at": t.opens_at.isoformat() if t.opens_at else None,
                    "locks_at": t.locks_at.isoformat() if t.locks_at else None,
                }
                for t in tournaments
            ]
        except Exception as e:
            logger.error(f"Error listing tournaments: {e}")
            return []

    async def update_tournament_status(self, tournament_id: int, new_status: str) -> bool:
        """Update tournament status (lifecycle transitions)."""
        try:
            stmt = select(Tournament).where(Tournament.id == tournament_id)
            result = await self.db.execute(stmt)
            tournament = result.scalar_one_or_none()
            if not tournament:
                return False

            valid_transitions = {
                "upcoming": ["open", "cancelled"],
                "open": ["locked", "cancelled"],
                "locked": ["scoring"],
                "scoring": ["completed"],
            }

            if new_status not in valid_transitions.get(tournament.status, []):
                logger.warning(f"Invalid transition: {tournament.status} → {new_status}")
                return False

            tournament.status = new_status
            if new_status == "completed":
                tournament.completed_at = datetime.utcnow()
            await self.db.flush()

            logger.info(f"Tournament {tournament_id}: {tournament.status} → {new_status}")
            return True
        except Exception as e:
            logger.error(f"Error updating tournament status: {e}")
            return False
