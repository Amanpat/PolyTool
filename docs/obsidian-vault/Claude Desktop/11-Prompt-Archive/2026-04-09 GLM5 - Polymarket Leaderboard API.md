---
tags: [prompt-archive]
date: 2026-04-09
status: complete
model: GLM-5-Turbo
---
# Polymarket Leaderboard API Research

## Key Findings

**The official leaderboard endpoint exists and is public:**
- `GET https://data-api.polymarket.com/v1/leaderboard`
- No auth required
- Returns: rank, proxyWallet (0x address), userName, vol, pnl, profileImage, xUsername, verifiedBadge

**Parameters:**
- `category`: OVERALL, POLITICS, SPORTS, CRYPTO, CULTURE, MENTIONS, WEATHER, ECONOMICS, TECH, FINANCE
- `timePeriod`: DAY, WEEK, MONTH, ALL
- `orderBy`: PNL, VOL
- `limit`: 1-50 (max 50 per request)
- `offset`: 0-1000
- `user`: optional 0x address filter
- `userName`: optional username filter

**Pagination:** Loop with limit=50, offset=0,50,100...450 to get top 500. Rate limit: 1000 req/10s (Data API general).

**What doesn't have leaderboard:**
- Gamma API — profiles only (no PnL/rank)
- CLOB API — trading only
- py-clob-client — no leaderboard methods
- No official GraphQL leaderboard (unofficial PnL subgraph exists on The Graph)

## Implementation Pattern

```python
import requests, time
BASE = "https://data-api.polymarket.com/v1/leaderboard"
def fetch_leaderboard(order_by="PNL", time_period="ALL", category="OVERALL", limit=50, max_pages=10):
    rows = []
    for page in range(max_pages):
        r = requests.get(BASE, params={"category": category, "timePeriod": time_period,
            "orderBy": order_by, "limit": limit, "offset": page * limit})
        r.raise_for_status()
        batch = r.json()
        if not batch: break
        rows.extend(batch)
        if len(batch) < limit: break
        time.sleep(0.15)
    return rows
```

## Impact on Pipeline Design
- Loop A can now fully automate leaderboard discovery
- Fetch top 500 by PNL + top 500 by VOL per category = comprehensive coverage
- Compare DAY vs WEEK vs ALL to detect leaderboard churn (new entrants)
- proxyWallet field gives us the address needed for wallet-scan
