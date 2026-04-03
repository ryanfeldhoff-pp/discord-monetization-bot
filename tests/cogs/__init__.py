"""
Test package for Discord monetization bot cogs.

Contains comprehensive end-to-end tests for all 14 cog modules:
- XP System: Message-based XP earning and leaderboards
- Account Linking: OAuth authentication and PrizePicks integration
- Tiered Roles: Auto-role assignment based on XP progression
- Polls: Community polling with voting and auto-closure
- Tournaments: Weekly prediction tournaments with leaderboards
- Game-Day Channels: Dynamic channel creation and archival
- Referral Tracking: Referral code generation and conversion tracking
- Referral Challenges: Community-wide FTD milestone challenges
- Win Sharing: Post-win notifications with referral CTAs
- Board Alerts: Real-time PrizePicks board monitoring and alerts
- Monthly Recap: Monthly stats cards and distribution
- OCR Bot: Screenshot detection and entry link generation
- Promo Redemption: XP-to-promo code redemptions with tier limits
- Tail Bot: PrizePicks entry URL detection and formatting

Each test file implements specific named test functions with precise
verification of cog behavior, command handlers, views, and background
task functionality.

Testing patterns:
- AsyncMock for async Discord API methods
- MagicMock for sync attributes and standard methods
- pytest.mark.asyncio for async test functions
- No shared state between tests
- No actual bot instantiation
"""
