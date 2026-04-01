# Business Requirements Document (BRD)

## Overview

This document contains the detailed functional and non-functional requirements for the PrizePicks Discord Monetization Bot across all four pillars.

## Document Structure

- **[Pillar 1: Entry & Conversion](pillar-1-entry-conversion.md)** - Account linking, tail bot, OCR, board alerts
- **[Pillar 2: Loyalty & Rewards](pillar-2-loyalty-rewards.md)** - XP system, tiered roles, promo redemption, recaps
- **[Pillar 3: Community Events](pillar-3-community-events.md)** - Seasonal contests, voting, leaderboards
- **[Pillar 4: Referral Amplifier](pillar-4-referral-amplifier.md)** - Referral codes, bonuses, tracking

## Functional Requirements Summary

### Pillar 1: Entry & Conversion

| FR ID | Feature | Priority | Status |
|-------|---------|----------|--------|
| FR-1.1 | Account Linking OAuth Flow | P0 | Planned |
| FR-1.2 | Discord Role Assignment on Link | P0 | Planned |
| FR-1.3 | URL Detection (Tail Bot) | P0 | Planned |
| FR-1.4 | Deeplink Generation | P1 | Planned |
| FR-1.5 | Board Image OCR Parsing | P1 | Planned |
| FR-1.6 | Real-time Board Alerts | P0 | Planned |
| FR-1.7 | Alert Filtering & Preferences | P2 | Planned |
| FR-1.8 | Account Unlinking | P1 | Planned |

### Pillar 2: Loyalty & Rewards

| FR ID | Feature | Priority | Status |
|-------|---------|----------|--------|
| FR-2.1 | XP Award on Message | P0 | Planned |
| FR-2.2 | XP Award on Share | P0 | Planned |
| FR-2.3 | XP Award on Account Link | P1 | Planned |
| FR-2.4 | Anti-Spam Rate Limiting | P0 | Planned |
| FR-2.5 | XP Decay for Inactive Users | P1 | Planned |
| FR-2.6 | Tier Assignment (Bronze/Silver/Gold/Diamond) | P0 | Planned |
| FR-2.7 | Tier Role Management | P0 | Planned |
| FR-2.8 | Promo Redemption Catalog | P0 | Planned |
| FR-2.9 | Monthly Recap Generation | P1 | Planned |
| FR-2.10 | Leaderboard Rankings | P1 | Planned |

### Pillar 3: Community Events

| FR ID | Feature | Priority | Status |
|-------|---------|----------|--------|
| FR-3.1 | Event Template System | P1 | Planned |
| FR-3.2 | Seasonal Contest Framework | P1 | Planned |
| FR-3.3 | Voting Mechanisms | P2 | Planned |
| FR-3.4 | Event-based Multipliers | P2 | Planned |

### Pillar 4: Referral Amplifier

| FR ID | Feature | Priority | Status |
|-------|---------|----------|--------|
| FR-4.1 | Referral Code Generation | P1 | Planned |
| FR-4.2 | Referral Attribution Tracking | P1 | Planned |
| FR-4.3 | Referral Bonus Distribution | P1 | Planned |
| FR-4.4 | Tiered Referral Rewards | P2 | Planned |

## Non-Functional Requirements

### Performance
- API response time: < 500ms (p95)
- Daily message throughput: 10M+ messages
- Leaderboard update: < 2 seconds
- Alert delivery: < 10 seconds

### Reliability
- Bot uptime: 99.5% SLA
- Database failover: < 30 seconds
- Graceful degradation on PrizePicks API outage
- Automatic retry with exponential backoff

### Security
- OAuth 2.0 for account linking
- No plaintext token storage
- Rate limiting on all endpoints
- Input validation and sanitization
- Fraud detection for XP farming

### Scalability
- Support 654K+ Discord members
- Handle 300K+ monthly active users
- PostgreSQL connection pooling
- Redis caching for hot data
- Horizontal scaling ready

### Compliance
- GDPR compliant data handling
- Privacy policy on OAuth redirect
- User data retention limits
- Audit logging for sensitive operations

## Detailed Documentation

See individual pillar documents for:
- Detailed use cases
- Technical specifications
- Acceptance criteria
- Edge cases and error handling

---

## Document Conventions

- **P0**: Critical, must have for MVP
- **P1**: Important, should have for launch
- **P2**: Nice to have, future iterations
- **FR**: Functional Requirement
- **NFR**: Non-Functional Requirement
