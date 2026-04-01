# Deployment Guide

## Production Setup

1. Set environment variables
2. Install dependencies: pip install -r requirements.txt
3. Run migrations: python scripts/migrate_db.py
4. Start the bot: python main.py

## Docker Deployment

FROM python:3.11
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]

## Monitoring

- Check logs in logs/ directory
- Monitor Discord.py debug logs
- Set up error tracking with Sentry (optional)
