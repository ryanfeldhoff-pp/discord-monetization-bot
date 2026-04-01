#!/usr/bin/env python3
"""
Database initialization script.

Creates all required tables and initializes the database schema.
Run this once during initial setup.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_settings
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# SQL Schema Definition
SCHEMA = """
-- Users table
CREATE TABLE IF NOT EXISTS users (
  discord_id BIGINT PRIMARY KEY,
  username VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- XP Ledger
CREATE TABLE IF NOT EXISTS xp_ledger (
  id SERIAL PRIMARY KEY,
  discord_id BIGINT UNIQUE NOT NULL,
  current_xp INT DEFAULT 0,
  lifetime_xp INT DEFAULT 0,
  peak_xp INT DEFAULT 0,
  current_tier VARCHAR(20) DEFAULT 'bronze',
  last_active TIMESTAMP,
  last_decay_applied TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (discord_id) REFERENCES users(discord_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_xp_current ON xp_ledger(current_xp DESC);
CREATE INDEX IF NOT EXISTS idx_xp_tier ON xp_ledger(current_tier);

-- XP Transactions (Audit Trail)
CREATE TABLE IF NOT EXISTS xp_transactions (
  id SERIAL PRIMARY KEY,
  discord_id BIGINT NOT NULL,
  amount INT NOT NULL,
  source VARCHAR(50),
  transaction_type VARCHAR(20),
  metadata JSONB,
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (discord_id) REFERENCES users(discord_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transactions_user ON xp_transactions(discord_id);
CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON xp_transactions(timestamp DESC);

-- Account Links
CREATE TABLE IF NOT EXISTS account_links (
  id SERIAL PRIMARY KEY,
  discord_id BIGINT UNIQUE NOT NULL,
  prizepicks_user_id VARCHAR(255) NOT NULL,
  access_token VARCHAR(500),
  refresh_token VARCHAR(500),
  token_expires_at TIMESTAMP,
  linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_verified TIMESTAMP,
  FOREIGN KEY (discord_id) REFERENCES users(discord_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_links_pp_user ON account_links(prizepicks_user_id);

-- Redemptions
CREATE TABLE IF NOT EXISTS redemptions (
  id SERIAL PRIMARY KEY,
  discord_id BIGINT NOT NULL,
  item_id VARCHAR(100) NOT NULL,
  xp_cost INT NOT NULL,
  promo_code VARCHAR(255) NOT NULL UNIQUE,
  status VARCHAR(20) DEFAULT 'generated',
  redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  metadata JSONB,
  FOREIGN KEY (discord_id) REFERENCES users(discord_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_redemptions_user ON redemptions(discord_id);
CREATE INDEX IF NOT EXISTS idx_redemptions_code ON redemptions(promo_code);

-- Redemption Counter (Monthly tracking)
CREATE TABLE IF NOT EXISTS redemption_counters (
  id SERIAL PRIMARY KEY,
  discord_id BIGINT NOT NULL,
  year INT NOT NULL,
  month INT NOT NULL,
  count INT DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(discord_id, year, month),
  FOREIGN KEY (discord_id) REFERENCES users(discord_id) ON DELETE CASCADE
);

-- Alert Preferences
CREATE TABLE IF NOT EXISTS alert_preferences (
  id SERIAL PRIMARY KEY,
  discord_id BIGINT UNIQUE NOT NULL,
  enabled BOOLEAN DEFAULT TRUE,
  sport_filter JSONB,
  player_filter JSONB,
  min_movement_percent FLOAT DEFAULT 5.0,
  quiet_hours_start INT,
  quiet_hours_end INT,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (discord_id) REFERENCES users(discord_id) ON DELETE CASCADE
);

-- Board Snapshots (For alert comparison)
CREATE TABLE IF NOT EXISTS board_snapshots (
  id SERIAL PRIMARY KEY,
  snapshot_id VARCHAR(100) UNIQUE NOT NULL,
  data JSONB,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  expires_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON board_snapshots(created_at DESC);

-- Referrals
CREATE TABLE IF NOT EXISTS referrals (
  id SERIAL PRIMARY KEY,
  referrer_id BIGINT NOT NULL,
  referred_user_id BIGINT UNIQUE NOT NULL,
  code_used VARCHAR(50) NOT NULL,
  source VARCHAR(20),
  status VARCHAR(20) DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  confirmed_at TIMESTAMP,
  FOREIGN KEY (referrer_id) REFERENCES users(discord_id) ON DELETE CASCADE,
  FOREIGN KEY (referred_user_id) REFERENCES users(discord_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id);
CREATE INDEX IF NOT EXISTS idx_referrals_referred ON referrals(referred_user_id);

-- Referral Codes
CREATE TABLE IF NOT EXISTS referral_codes (
  id SERIAL PRIMARY KEY,
  discord_id BIGINT UNIQUE NOT NULL,
  code VARCHAR(50) UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_used TIMESTAMP,
  use_count INT DEFAULT 0,
  FOREIGN KEY (discord_id) REFERENCES users(discord_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_referral_codes_code ON referral_codes(code);

-- Events (for analytics)
CREATE TABLE IF NOT EXISTS events (
  id SERIAL PRIMARY KEY,
  discord_user_id BIGINT,
  event_type VARCHAR(100) NOT NULL,
  properties JSONB,
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);
"""


def setup_postgresql():
    """Setup PostgreSQL database."""
    settings = get_settings()

    # Parse connection string
    db_url = settings.database.database_url
    logger.info(f"Setting up PostgreSQL database from URL...")

    # Create synchronous engine for setup
    engine = create_engine(db_url.replace("+asyncpg", ""))

    try:
        with engine.connect() as conn:
            # Execute schema
            for statement in SCHEMA.split(';'):
                statement = statement.strip()
                if statement:
                    logger.info(f"Executing: {statement[:80]}...")
                    conn.execute(text(statement))

            conn.commit()
            logger.info("â PostgreSQL database setup complete")

    except Exception as e:
        logger.error(f"â Failed to setup PostgreSQL: {e}")
        raise

    finally:
        engine.dispose()


def setup_sqlite():
    """Setup SQLite database."""
    try:
        import aiosqlite
        import asyncio

        async def _setup():
            db_path = "monetization_bot.db"
            logger.info(f"Setting up SQLite database at {db_path}...")

            async with aiosqlite.connect(db_path) as db:
                await db.executescript(SCHEMA)
                await db.commit()
                logger.info("â SQLite database setup complete")

        asyncio.run(_setup())

    except Exception as e:
        logger.error(f"â Failed to setup SQLite: {e}")
        raise


def main():
    """Main entry point."""
    settings = get_settings()
    db_url = settings.database.database_url

    logger.info("Starting database setup...")
    logger.info(f"Database URL: {db_url[:50]}...")

    if "postgresql" in db_url:
        setup_postgresql()
    elif "sqlite" in db_url:
        setup_sqlite()
    else:
        logger.error(f"Unsupported database: {db_url}")
        sys.exit(1)

    logger.info("\nâ Database setup completed successfully!")
    logger.info("You can now run the bot with: python -m bot.main")


if __name__ == "__main__":
    main()
