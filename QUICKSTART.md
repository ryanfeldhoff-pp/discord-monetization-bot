# Quick Start Guide

Get the PrizePicks Discord bot running in 5 minutes.

## Prerequisites

- Python 3.9+
- PostgreSQL or SQLite (default)
- Redis (optional, for caching)
- Discord Bot Token
- Discord Guild ID

## Step 1: Clone and Install

```bash
cd /mnt/Monetize\ Discord\"Channel/discord-monetization-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Step 2: Configure

```bash
cp .env.example .env
```

Edit `.env` with your values:

```bash
DISCORD_TOKEN=your_bot_token_here
DISCORD_GUILD_ID=your_guild_id_here
PRIZEPICKS_API_KEY=your_api_key_here
```

## Step 3: Initialize Database

```bash
python3 << 'PYTHON'
import asyncio
from src.database import Database

async def init():
    db = Database("cqlite+aiosqlite:///./discord_bot.db")
    await db.initialize()
    print("Database initialized!")

asyncio.run(init())
PYTHON
```

## Step 4: Run Bot

```bash
python main.py
```

Expected output:

```
2024-01-15 14:32:10 - root - INFO - ============================================================
2024-01-15 14:32:10 - root - INFO - PrizePicks Discord Monetization Bot
2024-01-15 14:32:10 - root - INFO - ============================================================
2024-01-15 14:32:10 - root - INFO - Initializing bot...
2024-01-15 14:32:10 - root - INFO - Initializing database...
2024-01-15 14:32:10 - root - INFO - Database initialized successfully
2024-01-15 14:32:11 - root - INFO - Loading cogs...
