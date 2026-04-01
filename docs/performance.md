# Performance Guide

## Optimization Tips

### Database
- Use indexes for frequently queried columns
- Cache user balances in memory
- Batch database operations

### Discord API
- Rate limit awareness
- Use slash commands instead of prefix commands
- Cache guild data

### Code
- Use async/await properly
- Minimize blocking operations
- Use connection pooling

## Monitoring

Monitor these metrics:
- Command response time
- Database query time
- Discord API latency
- Memory usage
- CPU usage

## Profiling

Use cProfile for CPU profiling:
python -m cProfile -s cumulative main.py

Use memory_profiler for memory profiling:
python -m memory_profiler main.py
