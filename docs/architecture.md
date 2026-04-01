# Architecture

## Project Structure

discord-monetization-bot/
src/
  __init__.py
  bot.py
  cogs.py
  database.py
  utils.py
  cogs/
  models/
  events/
  commands/
  middleware/
config/
tests/
docs/
scripts/
main.py
requirements.txt
Makefile
README.md

## Design Patterns

- Cog Pattern: Modular command/event structure
- Middleware: Authentication and error handling
- Models: Data classes for type safety
- Services: Database and utility services
