# Production Deployment Guide

## Pre-Deployment

### 1. Environment Setup

```bash
# Create production environment
python3 -m venv venv_prod
source venv_prod/bin/activate
pip install -r requirements.txt
```

### 2. Database Preparation

For production, use PostgreSQL instead of SQLite:

```bash
# Install PostgreSQL driver
pip install psycopg2-binary asyncpg

# Update .env
export DATABASE_URL=postgresql+asyncpg://user:password@prod-db.example.com/discord_bot

# Initialize database
python -c "from src.database import Database; import asyncio; \
asyncio.run(Database('postgresql+asyncpg://...').initialize())"
```

### 3. Redis Setup

Set up Redis for caching:

```bash
# Connect to Redis
export REDIS_URL=redis://redis.example.com:6379/0

# Test connection
redis-cli -h redis.example.com PING
```

### 4. Discord Bot Configuration

1. Go to Discord Developer Portal
2. Create application and get token
3. Create bot user
4. Set OAuth2 scopes: `bot`
5. Set permissions:
   - Manage Roles
   - Manage Channels
   - Send Messages
   - Embed Links
   - Attach Files
   - Read Message History
   - Manage Guild

6. Add bot to guild: `https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=268435456&scope=bot`

### 5. Security

- Use secrets manager for API keys (AWS Secrets Manager, HashiCorp Vault, etc.)
- Enable HTTPS for all API calls
- Rotate API keys monthly
- Enable audit logging
- Set up VPC/network isolation

## Deployment Methods

### Option A: Docker Container

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

Build and run:

```bash
docker build -t prizepicks-bot:latest .
docker run -d \
  --env-file .env.prod \
  --name prizepicks-bot \
  prizepicks-bot:latest
```

### Option B: Systemd Service

Create `/etc/systemd/system/prizepicks-bot.service`:

```ini
[Unit]
Description=PrizePicks Discord Bot
After=network.target

[Service]
Type=simple
User=discord-bot
WorkingDirectory=/opt/prizepicks-bot
EnvironmentFile=/opt/prizepicks-bot/.env.prod
ExecStart=/opt/prizepicks-bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Start service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable prizepicks-bot
sudo systemctl start prizepicks-bot
```

### Option C: AWS Lambda (with Docker)

```bash
# Create Lambda container image
aws ecr create-repository --repository-name prizepicks-bot

# Build and push
docker build -t prizepicks-bot:latest .
docker tag prizepicks-bot:latest \
  ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/prizepicks-bot:latest
docker push ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/prizepicks-bot:latest

# Create Lambda function from container image
aws lambda create-function \
  --function-name prizepicks-bot \
  --role arn:aws:iam::ACMENT_ID:role/lambda-role \
  --code ImageUri=ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/prizepicks-bot:latest \
  --timeout 900 \
  --memory-size 1024
```

Note: Lambda isn't ideal for long-running bots. Use EC2 or ECS instead.

### Option D: AWS ECS

```bash
# Create ECS cluster
aws ecs create-cluster --cluster-name prizepicks

# Register task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json

# Create service
aws ecs create-service \
  --cluster prizepicks \
  --service-name prizepicks-bot \
  --task-definition prizepicks-bot:1 \
  --desired-count 1
```

## Post-Deployment

### 1. Verify Bot Status

```bash
# Check logs
tail -f bot.log

# Verify database connection
python -c "from src.database import Database; \
import asyncio; asyncio.run(Database('...').health_check())"

# Check Redis
redis-cli PING

# Test bot in Discord
# Run: /xp command, should return user's XP
```

### 2. Monitor Performance

Set up monitoring for:

- Bot uptime
- Database connection pool
- Redis latency
- API error rates
- XP processing latency
- Leaderboard cache hit rates

Example Prometheus metrics:

```python
from prometheus_client import Counter, Histogram, Gauge

xp_awarded = Counter('xp_awarded_total', 'Total XP awarded', ['source'])
redemption_errors = Counter('redemptions_failed_total', 'Failed redemptions')
db_latency = Histogram('db_operation_seconds', 'Database operation latency')
active_users = Gauge('active_users', 'Active users in bot')
```

### 3. Set Up Alerts

Configure alerts for:

- Bot offline (no heartbeat for 5 minutes)
- Database connection failures
- API error rate > 5%
- XP decay job failure
- Monthly recap distribution failure

Example PagerDuty integration:

```python
import logging
from pythonjsonlogger import jsonlogger

handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
handler.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler(handler)
```

### 4. Backup Strategy

Database backups:

```bash
# Daily automated backup
pg_dump discord_bot > backup_$(date +\%Y%m%d).sql

# Store in S3
aws s3 cp backup_*.sql s3://prizepicks-backups/

# Test restore monthly
pg_restore < backup_$(date +%Y%m%d).sql
```

### 5. Scaling Considerations

**Current Limits:**
- Single bot instance: ~100,000 users
- SQLite: NOT suitable for >1,000 concurrent connections

**For Scaling:**

1. **Horizontal:** Deploy multiple bot instances with shared database
   - Use message queue (RabbitMQ, SQS) for XP awards
   - Implement distributed locking for tier updates

2. **Database:** Upgrade to PostgreSQL with read replicas
   - Leaderboard queries on read replica
   - Write XP transactions to primary

3. **Caching:** Redis cluster for leaderboard caching
   - Horizontal autoscaling for recap card generation

Example architecture at scale:

```
Load Balancer
âââ Bot Instance 1
âââ Bot Instance 2
âââ Bot Instance 3
    â
RabbitMQ (Message Queue for XP)
    â
PostgreSQL Primary (Write)
    âââ Read Replica 1
    âââ Read Replica 2
    â
Redis Cluster (Caching)
```

## Troubleshooting

### Bot Not Responding

```bash
# Check bot process
ps aux | grep main.py

# Check logs
tail -100 bot.log

# Check Discord connection
curl https://discord.com/api/users/@me -H "Authorization: Bearer TOKEN"

# Restart bot
systemctl restart prizepicks-bot
```

### Database Connection Issues

```bash
# Test database
psql -h localhost -U user -d discord_bot -c "SELECT 1"

# Check connection pool
# In bot logs, look for "PostgreSQL pool size"

# Increase pool size if needed
# Edit src/database.py:
# engine = create_async_engine(..., pool_size=20, max_overflow=10)
```

### XP Awards Not Processing

```bash
# Check buffer status in logs
grep "Flushed XP" bot.log

# Check XPTransaction table
psql discord_bot -c "SELECT COUNT(*) FROM xp_transactions WHERE DATE(timestamp) = TODAY();"

# Manually flush buffer
# In bot code:
# await xp_manager.flush_xp_buffer()
```

### Leaderboard Slow

```bash
# Check Redis
redis-cli INFO stats

# Invalidate cache
redis-cli DEL "leaderboard:*"

# Add database index
psql discord_bot -c "CREATE INDEX idx_xp_balance_desc ON xp_ledger(xp_balance DESC);"
```

## Rollback Procedure

1. Stop current bot
2. Restore database from backup
3. Deploy previous version
4. Verify functionality

```bash
systemctl stop prizepicks_bot
pg_restore < backup_latest.sql
git checkout v1.0.0
python main.py
```

## Version Control

Tag releases:

```bash
git tag -a v1.0.0 -m "Production release 1.0.0"
git push origin v1.0.0
```

## Documentation

Maintain:
- API integration docs (update as backend APIs change)
- Deployment runbook
- Incident response procedures
- Bot command documentation

## Regular Maintenance

### Weekly
- Review error logs
- Check bot performance metrics
- Verify database backups

### Monthly
- Test database restore
- Review and update API documentation
- Security audit of credentials
- Test failover procedures

### Quarterly
- Load testing
- Disaster recovery drill
- Security review
- Performance optimization review
