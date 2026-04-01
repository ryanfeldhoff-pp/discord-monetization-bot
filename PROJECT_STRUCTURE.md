# Project Structure

## Directory Layout

```
discord-monetization-bot/
âââ src/
â   âââ __init__.py
â   âââ database.py                 # Database engine and session management
â   âââ models/
â   â   âââ __init__.py
â   â   âââ xp_models.py            # SQLAlchemy async models
â   âââ cogs/
â   â   âââ __init__.py
â   â   âââ xp_system.py            # Message XP awards and leaderboard
â   â   âââ tiered_roles.py         # Auto-assign roles based on XP tiers
â   â   âââ promo_redemption.py     # XP to promotional item redemption
â   â   âââ monthly_recap.py        # Monthly recap card generation
â   âââ services/
â   â   âââ __init__.py
â   â   âââ xp_manager.py           # Core XP operations and tier logic
â   â   âââ image_generator.py      # Recap card image generation (Pillow)
â   â   âââ prizepicks_api.py       # PrizePicks API client (template)
â   âââ utils/
â       âââ __init__.py
âââ config/
â   âââ config.py                   # Configuration management
âââ main.py                         # Bot entry point
âââ requirements.txt                # Python dependencies
âââ .env.example                    # Environment variables template
âââ README.md                       # Setup and usage guide
âââ DEPLOYMENT.md                  # Production deployment guide
