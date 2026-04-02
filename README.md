# PrizePicks Discord Monetization Bot

A production-ready Discord bot implementing all four monetization pillars for the PrizePicks community (654K+ members).

## Architecture Overview

```
Pillar 1: Entry Conversion     → account_linking, tail_bot, ocr_bot, board_alerts
Pillar 2: Loyalty & Rewards    → xp_system, tiered_roles, promo_redemption, monthly_recap
Pillar 3: Community Events     → polls, tournaments, gameday_channels
Pillar 4: Referral Amplifier   → referral_tracking, referral_challenges, win_sharing
```

**Stack:** Python 3.11+ · py-cord 2.4 · SQLAlchemy 2.0 (async) · Redis · Pillow · aiohttp

---

## Quick Start

```bash
cd discord-monetization-bot
pip install -r requirements.txt
cp .env.example .env   # then fill in credentials
python main.py
```

---

## Pillar 2: Loyalty & Rewards

### Features
- **XP System** — Message-based XP (5 XP/msg, 500/day cap), event XP (25-200 XP), 1.5x multiplier for linked accounts
- **Tiered Roles** — Bronze → Silver → Gold → Diamond, auto-assigned by XP with 7-day grace period on tier-down
- **Promo Redemption** — Spend XP on discount codes (1K XP), free entries (2K XP), deposit matches (5K XP)
- **Monthly Recap** — Auto-generated PNG cards with stats, QR referral link, shareable to channel/social

### Commands
```
/xp                    Show XP balance and rank
/leaderboard [period]  View leaderboard (daily, weekly, monthly, all-time)
/tier                  Show tier progress bar
/redeem                Browse and redeem XP for promos
/redeem_history        View past redemptions
/recap                 Generate monthly recap card
/recap_opt [on|off]    Toggle automatic recaps
```

---

## Pillar 3: Community Events

### Features
- **Polls** — Taco Tuesday weekly polls ("best stat line this week"), custom polls with up to 4 options, bar-chart results
- **Prediction Tournaments** — Weekly free-to-enter tournaments, bracket scoring, XP entry fees, promo prizes for top 3
- **Game-Day Channels** — Auto-created 4hrs before kickoff (#nfl-chiefs-vs-bills), auto-archived 2hrs after end

### Commands
```
/poll create [title] [options]   Create a poll (admin)
/poll taco_tuesday               Launch weekly Taco Tuesday poll (admin)
/poll results [id]               Show poll results
/poll close [id]                 Close poll early (admin)

/tournament list                 Active and upcoming tournaments
/tournament enter [id]           Enter a tournament
/tournament predict [id] [picks] Submit predictions
/tournament leaderboard [id]     Tournament leaderboard
/tournament create               Create tournament (admin)
/tournament score [id]           Trigger scoring (admin)

/gameday list                    Today's game-day channels
/gameday create [sport] [name]   Create channel manually (admin)
/gameday archive [channel]       Archive channel (admin)
```

---

## Pillar 4: Referral Amplifier

### Features
- **Referral Tracking** — Auto-generates referral codes (PP-XXXXXX) on account link, tracks attribution from tails/shares
- **Community Challenges** — "500 FTDs this month → everyone gets a free entry" with real-time progress bar
- **Ambassador Program** — Top 50 by XP/referrals get elevated bonuses ($35-$50 vs $25), three tiers (Rising Star → Veteran → Elite)
- **Win Sharing** — "Share Win" button auto-attaches referral deeplink, post-win DMs with referral CTA
- **Fraud Prevention** — Self-referral detection, velocity limits (10 refs/hr), shared IP flagging

### Commands
```
/referral code                   Generate or view your referral code
/referral stats                  View referral performance
/referral leaderboard            Top referrers
/referral link                   Get shareable referral link

/challenge active                Active challenges with progress
/challenge history               Past challenges
/challenge create                Create challenge (admin)

/share win                       Share your latest win
/share stats                     Win sharing performance
/share settings [dm on|off]      Toggle post-win DMs
```

---

## Backend API Dependencies — NEEDS ALIGNMENT

**These endpoints must be built/confirmed by the backend team before production deployment.** Each entry shows the expected contract. The bot codebase has template implementations in `src/services/prizepicks_api.py` that match these specs.

### Pillar 1 (Existing — needs confirmation)

| # | Endpoint | Method | Purpose | Input | Output |
|---|----------|--------|---------|-------|--------|
| 1 | `/api/account-links/verify` | POST | Verify Discord-PP account link | `{discord_user_id, pp_user_id}` | `{verified: bool, email: str}` |
| 2 | `/api/projections` | GET | Live projections for board alerts, OCR matching | `?sport=NFL&limit=50` | `[{id, player_name, sport, stat_type, line, start_time}]` |
| 3 | `/api/entries/details` | GET | Entry details for tail bot | `?entry_id=xxx` | `{entry_id, legs: [{player, stat, line}], user_id}` |
| 4 | **OCR Provider** | — | Screenshot processing (Google Vision or AWS Textract) | Image bytes | Extracted text |

### Pillar 2 (Existing — needs confirmation)

| # | Endpoint | Method | Purpose | Input | Output |
|---|----------|--------|---------|-------|--------|
| 5 | `/api/promos/generate` | POST | Generate promo codes for XP redemptions | `{type, value, discord_user_id}` | `{promo_code: str}` |
| 6 | `/api/users/{pp_user_id}/stats` | GET | User stats for monthly recaps | — | `{entries_placed, win_rate, biggest_win, most_played}` |
| 7 | `/api/referrals/generate` | POST | Generate referral link for recap cards | `{discord_user_id}` | `{referral_url: str}` |
| 8 | `/api/entries/credit` | POST | Credit free entries to user accounts | `{pp_user_id, amount, reason}` | `{success: bool}` |

### Pillar 3 (NEW — needs to be built)

| # | Endpoint | Method | Purpose | Input | Output |
|---|----------|--------|---------|-------|--------|
| 9 | `/api/projections` | GET | Projections for Taco Tuesday polls and tournament picks | `?sport=&limit=` | `[{id, player_name, sport, stat_type, line, start_time}]` |
| 10 | `/api/schedule` | GET | Sports schedule for game-day channel creation | `?date=YYYY-MM-DD&sport=` | `[{event_id, sport, home_team, away_team, start_time, venue}]` |
| 11 | `/api/entries/results` | POST | Resolve tournament scoring | `{entry_ids: []}` | `[{entry_id, status, legs: [{player, stat, line, actual, result}]}]` |

### Pillar 4 (NEW — needs to be built)

| # | Endpoint | Method | Purpose | Input | Output |
|---|----------|--------|---------|-------|--------|
| 12 | `/api/referrals/discord-map` | POST | Map Discord user to referral code | `{discord_user_id}` | `{referral_code, referral_url}` |
| 13 | `/api/referrals/conversions` | POST | Report a referral conversion (signup/FTD) | `{referral_code, referred_user_id, conversion_type}` | `{success: bool, reward_amount_cents}` |
| 14 | `/api/users/{pp_user_id}/wins` | GET | Recent wins for win-sharing feature | `?since=ISO_datetime` | `[{entry_id, win_amount_cents, picks: [], settled_at}]` |
| 15 | `/api/analytics/ftd-count` | GET | Discord-attributed FTD count for challenges | `?since=&until=` | `{count, discord_attributed}` |

### Authentication

All endpoints use Bearer token auth: `Authorization: Bearer {PRIZEPICKS_API_KEY}`

### Rate Limits Required
- `/api/projections`: 100 req/min (polled for board alerts)
- `/api/schedule`: 10 req/min (polled every 30 min)
- `/api/referrals/*`: 50 req/min
- All others: 1000 req/min per key

### Webhook (Pillar 4)

The bot also needs a **Win Event Webhook** from the PrizePicks backend:
```
POST https://{bot_host}/webhooks/win-event
Headers: X-Webhook-Secret: {WIN_WEBHOOK_SECRET}
Body: {
    "pp_user_id": "user_123",
    "entry_id": "entry_789",
    "win_amount_cents": 15000,
    "picks": [{"player": "LeBron James", "stat": "Points", "result": "more"}],
    "settled_at": "2026-04-02T22:00:00Z"
}
```
This triggers post-win DMs and win-sharing prompts.

---

## Database Schema

### Pillar 2 Tables
- `xp_ledger` — XP balances and tiers
- `xp_transactions` — XP audit trail
- `redemptions` — Promo redemption history
- `redemption_counter` — Monthly limits
- `recap_preference` — Recap opt-in/out
- `account_links` — Discord to PP mapping

### Pillar 3 Tables (NEW)
- `polls` — Community polls
- `tournaments` — Prediction tournaments
- `tournament_entries` — User entries and scores
- `gameday_channels` — Auto-generated channels
- `scheduled_events` — AMAs and special events

### Pillar 4 Tables (NEW)
- `referral_codes` — User referral codes
- `referral_conversions` — Conversion tracking
- `referral_challenges` — Community challenges
- `ambassadors` — Ambassador program
- `win_share_logs` — Win sharing events
- `fraud_flags` — Fraud detection records

All tables auto-created on first run via SQLAlchemy `create_all`.

---

## Environment Variables

```bash
# Required
DISCORD_TOKEN=             # Discord bot token
DISCORD_GUILD_ID=          # Main guild ID
PRIZEPICKS_API_KEY=        # PrizePicks backend API key

# Database
DATABASE_URL=sqlite+aiosqlite:///./discord_bot.db   # Use PostgreSQL in prod

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_ENABLED=true

# PrizePicks API
PRIZEPICKS_API_BASE=https://api.prizepicks.com

# Pillar 3: Community Events
TACO_TUESDAY_CHANNEL_ID=   # Channel for Taco Tuesday polls
TOURNAMENT_CHANNEL_ID=     # Channel for tournament announcements
GAMEDAY_CATEGORY_ID=       # Category for game-day channels
ARCHIVE_CATEGORY_ID=       # Category for archived game-day channels

# Pillar 4: Referral Amplifier
REFERRAL_CHANNEL_ID=       # Channel for referral announcements
CHALLENGES_CHANNEL_ID=     # Channel for challenge progress updates
WIN_SHARING_CHANNEL_ID=    # Channel for win shares
AMBASSADOR_ROLE_ID=        # Discord role for ambassadors
WIN_WEBHOOK_SECRET=        # Secret for win event webhook verification
RESTRICTED_STATES=["NY","NV","ID","WA","MT"]  # States where referral bonuses blocked

# Logging
LOG_LEVEL=INFO
```

---

## Project Structure

```
discord-monetization-bot/
├── main.py                          # Bot entry point — loads all 10 cogs
├── config/
│   └── config.py                    # Env-based configuration
├── src/
│   ├── database.py                  # Async SQLAlchemy engine
│   ├── models/
│   │   ├── xp_models.py            # Pillar 2 models (XP, redemptions, account links)
│   │   ├── event_models.py         # Pillar 3 models (polls, tournaments, channels)
│   │   └── referral_models.py      # Pillar 4 models (referrals, challenges, fraud)
│   ├── services/
│   │   ├── xp_manager.py           # XP operations (award, deduct, decay, leaderboard)
│   │   ├── tournament_engine.py    # Tournament lifecycle (create, enter, score, rank)
│   │   ├── referral_manager.py     # Referral system (codes, conversions, fraud, ambassadors)
│   │   ├── prizepicks_api.py       # PrizePicks API client (all 15 endpoints)
│   │   └── image_generator.py      # Recap card PNG generation
│   └── cogs/
│       ├── xp_system.py            # Pillar 2: XP awards and leaderboard
│       ├── tiered_roles.py         # Pillar 2: Auto-assign Discord roles
│       ├── promo_redemption.py     # Pillar 2: XP-to-promo redemption
│       ├── monthly_recap.py        # Pillar 2: Monthly recap cards
│       ├── polls.py                # Pillar 3: Taco Tuesday and community polls
│       ├── tournaments.py          # Pillar 3: Weekly prediction tournaments
│       ├── gameday_channels.py     # Pillar 3: Auto game-day channels
│       ├── referral_tracking.py    # Pillar 4: Referral code management
│       ├── referral_challenges.py  # Pillar 4: Community referral challenges
│       └── win_sharing.py          # Pillar 4: Win sharing with referral CTA
├── tests/
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Production Checklist

- [ ] Backend team confirms/builds all 15 API endpoints (see table above)
- [ ] Win Event Webhook set up from PrizePicks backend to bot host
- [ ] PostgreSQL configured for DATABASE_URL
- [ ] Redis deployed for leaderboard/tournament caching
- [ ] Bot permissions: message content, guild members, manage roles, manage channels
- [ ] All channel/category/role IDs configured in env
- [ ] State compliance: restricted states list confirmed with legal
- [ ] OCR provider set up (Google Vision or AWS Textract)
- [ ] Error monitoring (Sentry/Datadog)
- [ ] Load test with simulated 50K concurrent users
- [ ] Legal review of all bot messaging
- [ ] CI/CD pipeline for bot deployments

---

## License

Proprietary — PrizePicks
