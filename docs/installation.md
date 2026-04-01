# Installation Guide

## Prerequisites

- Python 3.9 or higher
- pip package manager
- Discord bot token

## Steps

1. Clone the repository:
   ```bash
   git clone https://github.com/ryanfeldhoff-pp/discord-monetization-bot.git
   cd discord-monetization-bot
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your bot token
   ```

5. Run the bot:
   ```bash
   python main.py
   ```
