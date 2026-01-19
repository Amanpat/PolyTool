# Public Data Blueprint (Public-Only)

This blueprint documents the exact public endpoints needed for PolyTool.
Every data field referenced below is tied to a specific endpoint and is used
in polybot's ingestion or ClickHouse extraction.

Base URLs:
- Gamma API: `https://gamma-api.polymarket.com`
- Data API: `https://data-api.polymarket.com`
- CLOB API: `https://clob.polymarket.com`

## Identity resolution (username -> proxy wallet)

Goal: Resolve a user input (username or wallet) to the proxy wallet, which is
the stable query key for trades and positions.

1) Search by username
- Endpoint: `GET /public-search?q=<username>&search_profiles=true`
- Example:
  - `https://gamma-api.polymarket.com/public-search?q=gabagool22&search_profiles=true`
- Required fields:
  - `profiles[].username`
  - `profiles[].proxyWallet` (stated by user; used as the proxy wallet)

2) Validate and expand identity by address
- Endpoint: `GET /public-profile?address=<wallet_or_proxy>`
- Example:
  - `https://gamma-api.polymarket.com/public-profile?address=0xabc...`
- Required fields:
  - `proxyWallet` (if provided in this profile response)
  - `address` (the address you queried)
  - `username` (if returned; used for display)

Identity model:
- Username: display handle; may change and is not a stable key.
- Proxy wallet: holds USDC and positions; stable query key for Data API.
- EOA or base address: metadata; may not directly hold positions.

## User history endpoints (Data API)

These are public endpoints used in polybot's ingestion client
(`ingestor-service/.../PolymarketDataApiClient.java` and
`polybot-core/.../PolymarketDataApiClient.java`).

1) Trades
- Endpoint: `GET /trades?user=<proxy_wallet>&limit=<n>&offset=<n>`
- Example:
  - `https://data-api.polymarket.com/trades?user=0xabc...&limit=100&offset=0`
- Fields extracted in ClickHouse (`analytics-service/clickhouse/init/002_canonical.sql`):
  - `trade.slug`
  - `trade.title`
  - `trade.asset` (token_id)
  - `trade.conditionId`
  - `trade.side`
  - `trade.outcome`
  - `trade.outcomeIndex`
  - `trade.price`
  - `trade.size`
  - `trade.timestamp`
  - `trade.transactionHash`
  - `trade.proxyWallet`

2) Positions
- Endpoint: `GET /positions?user=<proxy_wallet>&limit=<n>&offset=<n>`
- Example:
  - `https://data-api.polymarket.com/positions?user=0xabc...&limit=100&offset=0`
- Response is a JSON array; store raw entries and normalize only the fields
  that are explicitly needed by the detectors.

3) Activity
- Endpoint: `GET /activity?user=<proxy_wallet>&limit=<n>&offset=<n>`
- Example:
  - `https://data-api.polymarket.com/activity?user=0xabc...&limit=100&offset=0`
- Response is a JSON array; store raw entries for later use.

Pagination strategy:
- Polybot uses `limit <= 500` and `offset <= 1000` as safe bounds
  (`PolymarketUserIngestor.DATA_API_MAX_LIMIT` and `DATA_API_MAX_OFFSET`).
- Empirical (public) tests on 2026-01-19 for `/trades?user=`:
  - `limit=1000` returns 1000 rows.
  - `limit=2000` returns 1000 rows (suggests server cap around 1000).
  - `offset=1000`, `offset=2000`, and `offset=5000` returned non-empty pages.
  - Treat these as point-in-time; caps can change.
- For backfill:
  - Start at `offset=0`, request `limit=N`, increment by response size.
  - Stop on empty response or when a page signature repeats
    (polybot uses `(count, firstTx, firstTs, lastTx, lastTs)`).
- For polling:
  - Always read `offset=0` with a small `limit` and dedupe by
    `transactionHash + asset + side` (fallback: `proxy + timestamp + asset + side`).

## Market metadata and token mapping (Gamma API)

These endpoints provide market metadata and token/outcome mapping.
Polybot uses `GET /events?slug=<slug>` in `PolymarketGammaApiClient`.

1) Market by slug
- Endpoint: `GET /events?slug=<market_slug>&limit=1`
- Example:
  - `https://gamma-api.polymarket.com/events?slug=btc-updown-15m-1734684000&limit=1`
- Fields referenced in `PolymarketMarketContextIngestor`:
  - `event.id`
  - `event.slug`
  - `event.title`
  - `market.id`
  - `market.slug`
  - `market.conditionId`
  - `market.endDate` or `market.endDateIso`
  - `market.closed`
  - `market.resolved`
  - `market.resolution`
  - `market.umaResolutionStatus`
  - `market.outcomes`
  - `market.outcomePrices`
  - `market.clobTokenIds`
  - `market.bestBid`
  - `market.bestAsk`
  - `market.lastTradePrice`
  - `market.volumeNum`
  - `market.liquidityNum`

2) Live markets
- Endpoints (as requested):
  - `GET /events?active=true&closed=false`
  - `GET /markets?active=true&closed=false`
- Use `market.outcomes` and `market.clobTokenIds` to map token IDs to outcome names.

Token mapping logic (from `PolymarketMarketContextIngestor`):
- `clobTokenIds[i]` corresponds to `outcomes[i]`.
- Gamma often returns `outcomes` and `clobTokenIds` as JSON-encoded strings, not arrays.
  Parse them before alignment.
- Use this to pair opposite outcomes in detectors.

## Order book and price context (CLOB API)

1) Order book
- Endpoint: `GET /book?token_id=<token_id>`
- Example:
  - `https://clob.polymarket.com/book?token_id=123456`
- Fields referenced in `PolymarketClobApiClient`:
  - `book.bids[].price`, `book.bids[].size`
  - `book.asks[].price`, `book.asks[].size`
  - `book.asset_id`
  - `book.timestamp`
  - `book.hash`

Use:
- Best bid/ask from the first level of `bids` and `asks`.
- Mid = `(bestBid + bestAsk) / 2`.
- Complete-set edge: `1 - (bid_up + bid_down)` or `1 - (ask_up + ask_down)`
  using token IDs from Gamma.

## Rate limits and caching plan

Rate limit posture (conservative, based on polybot defaults):
- Data API: 1 request every 250 ms per user (`requestDelayMillis=250`).
- Gamma API: 1 request every 100 ms (`requestDelayMillis=100`).
- CLOB `/book`: no faster than 1 request per second per token for MVP.

Caching (recommended):
- Username -> proxy wallet: 24h TTL (Gamma `public-search` + `public-profile`).
- Market metadata (`/events` or `/markets`): 60s TTL for active markets; 1h for closed.
- CLOB order book: 1s TTL per token (higher refresh only when needed by a detector).
- Trades pages: store `offset`, page signature, and last seen `transactionHash` to avoid re-fetching.

Backoff:
- Exponential backoff on HTTP 429 or 5xx.
- Reduce page size and increase delay if repeated throttling is observed.

## Known limitations

- Trade fills do not reveal resting orders or cancels.
- Without WS order book, TOB may be stale; use CLOB `/book` at ingestion time
  or Gamma bestBid/bestAsk as a fallback.
- Proxy wallet is the query key; EOAs may show no positions or trades.
