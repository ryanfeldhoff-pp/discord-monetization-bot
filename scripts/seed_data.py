#!/usr/bin/env python3
"""
Development seed data script.

Populates the database with sample data for local development and testing.
Run this after setup_db.py if you want sample data.
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed_data():
    """Seed development database with sample data."""

    try:
        import aiosqlite
        from config.settings import get_settings

        settings = get_settings()
        db_url = settings.database.database_url

        if "sqlite" in db_url:
            db_path = "monetization_bot.db"
            db = await aiosqlite.connect(db_path)
        else:
            import asyncpg
            conn_str = db_url.replace("+asyncpg", "")
            db = await asyncpg.connect(conn_str)

        # Sample users
        sample_users = [
            (123456789, "alice"),
            (234567890, "bob"),
            (345678901, "charlie"),
            (456789012, "diana"),
            (567890123, "eve"),
        ]

        logger.info("Seeding users...")
        for discord_id, username in sample_users:
            if "sqlite" in db_url:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO users (discord_id, username)
                    VALUES (?, ?)
                    """,
                    (discord_id, username),
                )
            else:
                await db.execute(
                    """
                    INSERT INTO users (discord_id, username)
                    VALUES ($1, $2)
                    ON CONFLICT DO NOTHING
                    """,
                    discord_id,
                    username,
                )

        # Sample XP data
        logger.info("Seeding XP ledger...")
        xp_data = [
            (123456789, 5000, 8500, 8500, "gold"),
            (234567890, 2500, 3200, 3500, "silver"),
            (345678901, 1000, 1500, 2000, "silver"),
            (456789012, 500, 750, 800, "bronze"),
            (567890123, 250, 400, 500, "bronze"),
        ]

        for discord_id, current_xp, lifetime_xp, peak_xp, tier in xp_data:
            if "sqlite" in db_url:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO xp_ledger
                    (discord_id, current_xp, lifetime_xp, peak_xp, current_tier, last_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        discord_id,
                        current_xp,
                        lifetime_xp,
                        peak_xp,
                        tier,
                        datetime.utcnow(),
                    ),
                )
            else:
                await db.execute(
                    """
                    INSERT INTO xp_ledger
                    (discord_id, current_xp, lifetime_xp, peak_xp, current_tier, last_active)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT DO NOTHING
                    """,
                    discord_id,
                    current_xp,
                    lifetime_xp,
                    peak_xp,
                    tier,
                    datetime.utcnow(),
                )

        # Sample account links
        logger.info("Seeding account links...")
        links = [
            (123456789, "pp_user_001"),
            (234567890, "pp_user_002"),
            (345678901, "pp_user_003"),
        ]

        for discord_id, pp_user_id in links:
            if "sqlite" in db_url:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO account_links
                    (discord_id, prizepicks_user_id, linked_at, last_verified)
                    VALUES (?, ?, ?, ?)
                    """,
                    (discord_id, pp_user_id, datetime.utcnow(), datetime.utcnow()),
                )
            else:
                await db.execute(
                    """
                    INSERT INTO account_links
                    (discord_id, prizepicks_user_id, linked_at, last_verified)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT DO NOTHING
                    """,
                    discord_id,
                    pp_user_id,
                    datetime.utcnow(),
                    datetime.utcnow(),
                )

        # Sample redemptions
        logger.info("Seeding redemptions...")
        redemptions = [
            (123456789, "cashback_10", 1500, "CODE_001", "claimed"),
            (123456789, "nitro_boost", 2000, "CODE_002", "claimed"),
            (234567890, "badge", 500, "CODE_003", "generated"),
        ]

        for discord_id, item_id, xp_cost, code, status in redemptions:
            if "sqlite" in db_url:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO redemptions
                    (discord_id, item_id, xp_cost, promo_code, status, redeemed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (discord_id, item_id, xp_cost, code, status, datetime.utcnow()),
                )
            else:
                await db.execute(
                    """
                    INSERT INTO redemptions
                    (discord_id, item_id, xp_cost, promo_code, status, redeemed_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT DO NOTHING
                    """,
                    discord_id,
                    item_id,
                    xp_cost,
                    code,
                    status,
                    datetime.utcnow(),
                )

        # Sample referrals
        logger.info("Seeding referrals...")
        referrals = [
            (123456789, 234567890, "USER001-ABC123", "discord", "confirmed"),
            (123456789, 345678901, "USER001-ABC123", "discord", "pending"),
            (234567890, 456789012, "USER002-DEF456", "web", "confirmed"),
        ]

        for referrer_id, referred_id, code, source, status in referrals:
            confirmed_at = datetime.utcnow() if status == "confirmed" else None
            if "sqlite" in db_url:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO referrals
                    (referrer_id, referred_user_id, code_used, source, status, created_at, confirmed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (referrer_id, referred_id, code, source, status, datetime.utcnow(), confirmed_at),
                )
            else:
                await db.execute(
                    """
                    INSERT INTO referrals
                    (referrer_id, referred_user_id, code_used, source, status, created_at, confirmed_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT DO NOTHING
                    """,
                    referrer_id,
                    referred_id,
                    code,
                    source,
                    status,
                    datetime.utcnow(),
                    confirmed_at,
                )

        # Commit changes
        if "sqlite" in db_url:
            await db.commit()
        else:
            pass  # asyncpg auto-commits

        await db.close()

        logger.info("\nâ Database seeded successfully!")
        logger.info(f"â Created {len(sample_users)} sample users")
        logger.info(f"â Created {len(xp_data)} XP ledger entries")
        logger.info(f"â Created {len(links)} account links")
        logger.info(f"â Created {len(redemptions)} redemptions")
        logger.info(f"â Created {len(referrals)} referrals")

    except Exception as e:
        logger.error(f"â Failed to seed data: {e}")
        raise


def main():
    """Main entry point."""
    logger.info("Starting database seed...")
    asyncio.run(seed_data())


if __name__ == "__main__":
    main()
