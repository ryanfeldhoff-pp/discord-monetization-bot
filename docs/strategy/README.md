# PrizePicks Discord Strategy Overview

## Vision

Transform the PrizePicks Discord community (654K+ members) into a powerful user acquisition and retention engine through gamified engagement, exclusive rewards, and community-driven initiatives.

## Four-Pillar Strategy

The monetization bot is built on four interconnected pillars that work together to drive user conversion, engagement, and loyalty.

### Pillar 1: Entry & Conversion

**Goal**: Convert passive Discord members into active PrizePicks users.

**Key Components**:
- **Account Linking**: Secure OAuth integration allowing users to link their Discord and PrizePicks accounts
- **Tail Bot**: Automatic detection of PrizePicks board URLs with deeplink generation for easy mobile access
- **Board OCR**: Extract data from board screenshots for insights and engagement
- **Board Alerts**: Real-time notifications on board movement and high-probability entries

**Success Metrics**:
- Account link conversion rate
- Unique tails per day
- Click-through rate on alerts
- Mobile conversion rate

---

### Pillar 2: Loyalty & Rewards

**Goal**: Retain users through gamification and tangible rewards.

**Key Components**:
- **XP System**: Multi-action point system rewarding:
  - Regular messaging (5 XP)
  - Sharing tails (15 XP)
  - Linking accounts (25 XP + 50 XP bonus)
  - Daily participation multiplier
  - Linked account bonus (2x multiplier)

- **Tiered Roles**: Dynamic role progression (Broze â Silver â Gold â Diamond)
  - Bronze: 500 XP
  - Silver: 2,U00 XP
  - Gold: 7,500 XP
  - Diamond: 15,000 XP

- **Promo Redemption**: Redeemable rewards catalog:
  - Discord Nitro boosts (high-tier ecclusive)
  - PrizePicks cashback credits
  - Exclusive badges and roles
  - Early access to features

- **Monthly Recaps**: Personalized achievement summaries featuring:
  - XP earned this month
  - Rank progression
  - Top contributors leaderboard
  - Personal milestones

**Success Metrics**:
- Monthly active users
- Average XP per user
- Tier distribution
- Redemption rate
- Month-over-month retention

---

### Pillar 3: Community Events

**Goal**: Drive engagement spikes and viral moments.

**Key Components**:
- Seasonal contests and challenges
- Community voting mechanisms
- Event-specific reward multipliers
- Leaderboard competitions

**Success Metrics**:
- Event participation rate
- Peak concurrent users
- Social sharing metrics

---


### Pillar 4: Referral Amplifier

**Goal**: Enable organic growth through community advocacy.

**Key Components**:
- Referral codes and tracking
- Tiered referral bonuses
- Attribution and rewards distribution
- Viral growth mechanics

**Success Metrics**:
- Referral conversion rate
- Cost per acquisition
- Viral coefficient
- Lifetime value per referred user

---

## Integration & Synergies

```
ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
â        ENTRY & CONVERSION (Pillar 1)                        â
â        Get users in the door, linked and engaged             â
âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
â        LOYALTY & REWARDS (Pillar 2)                         â
â        Keep users coming back, reward engagement             â
âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
â        COMMUNITY EVENTS (Pillar 3)                          â
â        Create moments of excitement and viral sharing        â
âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
â        REFERRAL AMPLIFIER (Pillar 4)                        â
â        Turn engaged users into growth engines                â
âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
```

## Product Roadmap

### Phase 1: Foundation (Month 1-2)
- Account linking infrastructure
- Basic XP system and tier assignment
- Tail bot with URL detection
- Simple board alerts

**Success Criteria**:
- 10K+ account links
- 50K+ daily active users
- Stable bot uptime (99.5%)

### Phase 2: Engagement (Month 3-4)
- Full promo redemption catalog
- Monthly recap generation
- OCR integration for board parsing
- Advanced alert filtering

**Success Criteria**:
- 50% of active users have linked accounts
- 100K monthly redemptions
- 30% increase in daily engagement

### Phase 3: Community (Month 5-6)
- Community event framework
- Seasonal contests
- Leaderboard tournaments
- Voting mechanisms

**Success Criteria**:
- 3+ major community events
- 200K+ event participants
- 10% increase in monthly active users

### Phase 4: Growth (Month 7+)
- Referral program launch
- Advanced analytics and insights
- Mobile app integration
- International expansion

**Success Criteria**:
- 20K+ referrals per month
- 40% growth in active users
- Viral coefficient > 1.2

---

## Key Metrics & KPIs

### Conversion Metrics
| Metric | Target | Current |
|--------|--------|---------|
| Account Link Rate | 15% | TBD |
| Linked User Daily Active | 40% | TBD |
| Mobile Conversion (Tail Click) | 35% | TBD |

### Engagement Metrics
| Metric | Target | Current |
|--------|--------|---------|
| Avg XP per User/Month | 250 | TBD |
| Monthly Active Users | 300K | TBD |
| Tier 2+ Penetration | 25% | TBD |
| Promo Redemption Rate | 8% | TBD |

### Retention Metrics
| Metric | Target | Current |
|--------|--------|---------|
| 30-Day Retention | 40% | TBD |
| 90-Day Retention | 25% | TBD |
| Churn Rate | < 5% | TBD |

### Growth Metrics
| Metric | Target | Current |
|--------|--------|---------|
| Referral Signups | 20K/month | TBD |
| Viral Coefficient | 1.2+ | TBD |
| CAC (via Referrals) | $5 | TBD |

---

## Technical Architecture

The bot uses a modern, scalable architecture:

- **Discord.py**: Async Python Discord bot framework
- **PostgreSQL**: Persistent data storage
- **Redis**: Real-time cache and leaderboards
- **Async/Await**: Non-blocking I/O throughout
- **Structured Logging**: Comprehensive observability

See [System Design](../architecture/system-design.md) for detailed technical overview.

---

## Success Factors

1. **Seamless Account Linking**: Make it frictionless for users to connect their accounts
2. **Transparent XP System**: Users should understand how they earn points
3. **Valuable Rewards**: Redemption options that users actually want
4. **Community Feeling**: Celebrate achievements and foster belonging
5. **Data-Driven**: Use analytics to continuously optimize engagement
6. **Reliability**: 99%+ uptime is non-negotiable
7. **Fast Response**: Low-latency interactions keep users engaged

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Low engagement adoption | High | Strong onboarding, clear value prop |
| Bot downtime | Critical | Redundancy, monitoring, alerting |
| Spam/abuse | Medium | Rate limiting, moderation tools |
| Data privacy | Critical | Secure OAuth, no PII storage |
| Reward manipulation | Medium | Fraud detection, rate limits |

---

## Related Documentation

- [Functional Requirements](../brd/README.md)
- [System Design](../architecture/system-design.md)
- [API Contracts](../architecture/api-contracts.md)
- [Pillar 1 Details](../brd/pillar-1-entry-conversion.md)
- [Pillar 2 Details](../brd/pillar-2-loyalty-rewards.md)
