# Pillar 1: Entry & Conversion

**Objective**: Convert passive Discord members into active PrizePicks users through seamless account linking, easy entry sharing, and real-time insights.

## Features Overview

### 1.1 Account Linking (OAuth)

**FR-1.1: Account Linking OAuth Flow**

**User Story**: As a Discord user, I want to link my PrizePicks account so that I can access exclusive benefits and track my activity.

**Technical Requirements**:
- Implement OAuth 2.0 flow with PrizePicks backend
- Store user credentials securely (never plaintext)
- Generate secure authorization tokens
- Handle token refresh automatically
- Support account unlinking

**Acceptance Criteria**:
- User can initiate OAuth flow via `/link` command
- Redirect to PrizePicks auth page
- Successfully exchange auth code for access token
- Store token in encrypted format
- Return to Discord with confirmation
- Handle errors gracefully (user denies, timeout, invalid state)

**Error Handling**:
```
- Invalid auth code: Retry with new code
- Token expiration: Auto-refresh token
- User denies permissions: Allow retry
- Network timeout: Show error message
```

**API Contract**:
```
POST /api/discord/link
Request:
  {
    "discord_user_id": "123456",
    "auth_code": "...",
    "redirect_uri": "https://api.example.com/oauth/callback"
  }

Response (Success):
  {
    "status": "linked",
    "prizepicks_user_id": "789",
    "access_token": "...",
    "expires_in": 3600
  }

Response (Error):
  {
    "error": "invalid_code",
    "error_description": "..."
  }
```

---

### 1.2 Discord Role Assignment on Account Link
B
**FR-1.2: Discord Role Assignment on Link**

**User Story**: As an admin, I want linked users to automatically receive a "Linked" role so that I can distinguish them in the community.

**Tech Requirements**:
- Query Discord API to fetch roles
- Assign configured "linked" role on successful account linking
- Remove role on unlinking
- Handle permission errors
- Verify role assignment succeeded

**Acceptance Criteria**:
- After successful link, user receives "Linked" role within 5 seconds
- Role is applied to user in primary guild only
- Unlinking removes the role
- If bot lacks permissions, log error but don't block linking
- Idempotent: calling twice doesn't cause issues

---

### 1.3 Tail Bot - URL Detection

**FR-1.3: URL Detection & Tail Bot**

**User Story**: As a community member, I want the bot to automatically detect PrizePicks board URLs and provide a mobile-friendly deeplink so that I can easily jump in.

**Technical Requirements**:
- Monitor all Discord messages for PrizePicks URLs
- Extract board ID and entry data from URL
- Generate mobile deeplinks for each platform
- Cache parsed URLs for analytics
- Handle URL variations and shortened links

**Supported URL Patterns**:
```
- https://app.prizepicks.com/board/12345
- https://api.prizepicks.com/board/12345
- Shortened links: prz\'pks/board/12345
- Embedded board data in message
```

**Acceptance Criteria**:
- Bot detects 95+% of PrizePicks URLs
- Generates deeplinks within 2 seconds
- Supports iOS and Android
- Works with message edits
- Deduplicates same URL posted multiple times
- Ignores bot's own messages

**Example Deeplink Format**:
```
iOS: prizepicks://board/12345
Android: com.prizepicks/board/12345
Web: https://app.prizepicks.com/board/12345?ref=discord
```

---

### 1.4 Deeplink Generation

**FR-1.4: Deeplink Generation**

**User Story**: As a Discord user, I want to click a deeplink to jump directly to the board on mobile so that I don't have to manually navigate.

**Technical Requirements**:
- Generate platform-specific deeplinks (iOS, Android, Web)
- Include source attribution parameters
- Handle missing entry data gracefully
- Cache deeplinks to avoid regeneration
- Support QR code generation for easy scanning

**Acceptance Criteria**:
- Deeplinks open correct board on mobile devices
- Fallback to web version if app not installed
- Include `ref=discord` parameter for attribution
- QR code encodes full URL
- Response time < 500ms

---

### 1.5 Board Image OCR

**FR-1.5: Board Image OCR Parsing**

**User Story**: As a user, I want to share board screenshots and have the bot parse them for insights so that I can discuss entries without manually typing.

**Technical Requirements**:
- Detect PrizePicks board images in messages
- Use OCR (Google Vision or AWS Textract) to extract text
- Parse player names, spreads, projections, odds
- Extract confidence scores
- Cache results to avoid re-processing
- Handle image variations and qualities

**Acceptance Criteria**:
- Confidence threshold: 80%+
- Correctly extract player name 95%+ of time
- Extract spread/projection with <5% error
- Response time < 3 seconds
- Work with both screenshots and zoomed images
- Graceful failure if image too low quality

**OCR Output Example**:
```json
{
  "detected": true,
  "confidence": 0.92,
  "entries": [
    {
      "player": "Luka Doncic",
      "spread": "Points Over 28.5",
      "projection": 32,
      "odds": -110
    }
  C=
}
```

---

### 1.6 Real-time Board Alerts

**FR-1.6: Real-time Board Alerts**

**User Story**: As an engaged user, I want to be notified when my favorite boards move significantly so that I can capitalize on good odds.

**Technical Requirements**:
- Poll PrizePicks API for board changes every 5 minutes
- Detect "bumps" (significant movement)
- Filter alerts by user preferences
- Send alert to configured channels
- Include relevant board data and deeplinks
- Implement exponential backoff for failures

**Bump Detection Logic**:
```
- Threshold: 5% movement (configurable)
- Compare to previous snapshot
- Skip minor fluctuations
- Deduplicate similar alerts
```

**Alert Format**:
```
ð¢ ALERT: Basketball / NBA
Board: James Harden Points Over 24.5
Movement: -110 â -125 (5% bump)
Time: 2:30 PM EST
[Open Board] [Share]
```

**Acceptance Criteria**:
- Detect 95%+ of significant movements
- Alert latency: Ð0 10 seconds from detection
- Rate limit: max 10 alerts/hour per channel
- Prefer precision over recall (av void false positives)
- Support filtering by sport/player/threshold

---

### 1.7 Alert Filtering & Preferences

**FR-1.7: Alert Filtering & Preferences**

**User Story**: As a user, I want to customize which alerts I receive so that I'm not spammed with irrelevant notifications.

**Technical Requirements**:
- Implement user preference storage
- Support filters: sport, player, spread type, odds range
- Per-user or per-channel alert configuration
- Override global settings
- Persist preferences in database

**Filter Configuration Example**:
``a
/alert-settings
- Sports: NBA, NFL
- Players: LeBron, Giannis, Curry
- Spread Types: Points, Rebounds, Assists
- Min odds movement: 3%
- Preferred channels: #alerts
- Quiet hours: 1am-8am
```

---

### 1.8 Account Unlinking

**FR-1.8: Account Unlinking**

**User Story**: As a user, I want to unlink my account if I no longer want to use the features so that my data can be cleaned up.

**Tech Requirements**:
- Implement `/unlink` command
- Revoke OAuth tokens
- Remove user's "Linked" role
- Archive user data (optional retention)
- Send confirmation
- Allow re-linking later

**Acceptance Criteria**:
- User can unlink with single command
- Linked role removed within 5 seconds
- Cannot redeem promos after unlinking
- XP/achievements preserved for historical view
- Require confirmation to prevent accidents
- Support admin-initiated unlinks

---

## Integration Points

### Data Fow: Account Linking

```
User initiates /link
    âBot generates OAuth state token
    âRedirect to PrizePicks Auth
    âBuser grants permissions
    â
Auth server returns code
    â
Bot exchanges code for token
    â
Store token securely (encrypted)
    â
Assign "Linked" role
    âConfirm to user
    â
User now eligible for XP multiplier & alerts
```


### Data Flow: URL Detection

```
User posts message with PrizePicks URL
    â
Bot detects URL in message
    â
Extract board ID
    â
Query PrizePicks API for board data
    â
Generate deeplinks (iOS/Android/Web)
    â
Post reaction with deeplinks
    â
Cache URL for analytics
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Account link conversion | 15% of active | Daily link events |
| OAuth completion rate | 85% | Auth flow drops |
| Tail bot accuracy | 95% | URL detection errors |
| Deeplink CTR | 30% | Click tracking |
| OCR accuracy | 90% | Manual validation sampling |
| Alert delivery latency | <10s | Timestamp comparison |
| Alert relevance | 80+% helpful | User feedback |

--

## Edge Cases & Error Handling

| Case | Handling |
|--------|---------|
| User already linked | Return existing link, option to refresh |
| Token expired | Auto-refresh with stored refresh token |
| PrizePicks API down | Show cached data, retry with backoff |
| Invalid board URL | Ignore gracefully |
| User deletes message with URL | No action needed |
| Rate limit exceeded | Queue for retry, inform user |
| Image too blurry for OCR | Return confidence < threshold, skip |
| User revokes OAuth permissions | Treat as unlink, remove role |

---

## Tech Specifications

**Database Tables Required**:
- `user_links` - Discord user to PrizePicks user mapping
- `oauth_tokens` - Access tokens (encrypted)
- `parsed_urls` - Cache of parsed board URLs
- `alert_preferences` - User alert settings

**API Dependencies**:
- PrizePicks OAuth server
- PrizePicks Board API
- Google Vision API or AWS Textract
- Discord API

**Caching Strategy**:
- Token cache: 1 hour TTL
- Board data: 5 minute TTL
- OCR results: 24 hour TTL
- Deeplinks: Generate on demand

---

## Testing Requirements

- Unit tests for OAuth state validation
- Integration tests for token exchange
- E2E tests for account linking flow
- OCR accuracy tests (sample images)
- Rate limit tests
- Error scenario tests (expired token, invalid code, etc.)

---

## Dependencies

- Pillar 2 for XP multiplier application
- PrizePicks backend API team for OAuth
- PrizePicks infrastructure for board/user data APIs

